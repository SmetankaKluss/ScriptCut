"""Transcription service with normalized word-level output."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Literal, Optional

from utils.cache import load_from_cache, save_to_cache

logger = logging.getLogger(__name__)

_model_cache: dict = {}
_model_cache_lock = threading.RLock()
TranscriptionEngine = Literal["faster-whisper", "whisperx", "whisper", "parakeet", "auto"]
PARAKEET_DEFAULT_MODEL = "nvidia/parakeet-tdt-0.6b-v3"
SMART_MODEL_NAME = "smart"
WHISPER_MODEL_NAMES = {
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v3",
    "large-v3-turbo",
    "turbo",
    SMART_MODEL_NAME,
}

# Whisper occasionally replaces or drops profanity because the acoustic signal is
# short, clipped, or masked by game audio. Faster Whisper's hotword support is a
# decoding hint, not a post-processing replacement: the audio still has to support
# the word. Keeping the list compact reduces unrelated hallucinations.
RUSSIAN_PROFANITY_HOTWORDS = (
    "блядь блять бля сука сучка хуй хуево хуёво хуевый охуеть охуенно "
    "нахуй похуй пизда пиздец пиздеть пиздатый ебать ебаный ёбаный "
    "ебучий заебал заебись наебал проебал уебок долбоеб мудак мудила "
    "гандон гондон пидор пидорас"
)
RUSSIAN_CONTEXT_PROMPT = (
    "Разговорный стрим на русском языке. Сохраняй разговорную лексику дословно, "
    "включая обсценные слова, имена, игровые термины и самокоррекции."
)

try:
    import torch
    from utils.gpu_utils import get_optimal_device
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    get_optimal_device = None
    TORCH_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model as download_faster_whisper_model
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    download_faster_whisper_model = None
    FASTER_WHISPER_AVAILABLE = False

try:
    import whisperx
    WHISPERX_AVAILABLE = True
except ImportError:
    whisperx = None
    WHISPERX_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    whisper = None
    WHISPER_AVAILABLE = False

try:
    import nemo.collections.asr as nemo_asr
    NEMO_AVAILABLE = True
except ImportError:
    nemo_asr = None
    NEMO_AVAILABLE = False

try:
    HF_TOKEN = None
    import os
    HF_TOKEN = os.environ.get("HF_TOKEN")
except Exception:
    pass


def _get_device(use_gpu: bool = True) -> str:
    if use_gpu and FASTER_WHISPER_AVAILABLE:
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except (ImportError, RuntimeError):
            pass
    if use_gpu and TORCH_AVAILABLE and get_optimal_device:
        return str(get_optimal_device())
    return "cpu"


class ModelDownloadError(RuntimeError):
    """A safe, localized error for the first speech-model download."""


def _resolve_faster_whisper_model_source(
    model_name: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> str:
    """Prefer a complete local snapshot, then retry the resumable Hub download."""
    if download_faster_whisper_model is None:
        return model_name

    try:
        local_path = download_faster_whisper_model(model_name, local_files_only=True)
        if progress_callback:
            progress_callback(8, "Локальная модель речи готова")
        return str(local_path)
    except Exception:
        # A missing local snapshot is normal on first use. The online attempts
        # below reuse any partial Hugging Face blobs instead of starting over.
        pass

    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        if progress_callback:
            progress_callback(
                8 + attempt,
                f"Скачиваем модель речи: попытка {attempt} из 3. "
                "Прерванная загрузка продолжится автоматически.",
            )
        try:
            return str(download_faster_whisper_model(model_name))
        except ValueError:
            raise
        except Exception as error:
            last_error = error
            logger.warning(
                "Faster Whisper model download attempt %s/3 failed: %s",
                attempt,
                error,
            )
            if attempt < 3:
                time.sleep(attempt)

    raise ModelDownloadError(
        "Не удалось скачать локальную модель речи после трёх попыток. "
        "Проверьте подключение к интернету и нажмите «Повторить расшифровку». "
        "Уже загруженная часть сохранена — скачивание продолжится с неё. "
        "API-ключ для этого не нужен."
    ) from last_error


def _load_model(
    model_name: str,
    device: str,
    engine: TranscriptionEngine,
    progress_callback: Optional[Callable[[int, str], None]] = None,
):
    cache_key = f"{engine}_{model_name}_{device}"
    with _model_cache_lock:
        if cache_key in _model_cache:
            return _model_cache[cache_key]

        logger.info(f"Loading {engine} model: {model_name} on {device}")
        if engine == "parakeet":
            model = _load_parakeet_model(model_name, device)
        elif engine == "faster-whisper" and FASTER_WHISPER_AVAILABLE:
            faster_device = "cuda" if device.startswith("cuda") else "cpu"
            compute_type = _select_faster_whisper_compute_type(faster_device)
            model_source = _resolve_faster_whisper_model_source(model_name, progress_callback)
            try:
                model = WhisperModel(model_source, device=faster_device, compute_type=compute_type)
            except (RuntimeError, ValueError) as error:
                if faster_device != "cuda":
                    raise
                logger.warning("CUDA Faster Whisper initialization failed; falling back to CPU: %s", error)
                model = WhisperModel(
                    model_source,
                    device="cpu",
                    compute_type=_select_faster_whisper_compute_type("cpu"),
                )
        elif engine == "whisperx" and WHISPERX_AVAILABLE:
            whisperx_device = "cuda" if device.startswith("cuda") else "cpu"
            compute_type = "float16" if whisperx_device == "cuda" else "int8"
            model = whisperx.load_model(
                model_name,
                device=whisperx_device,
                compute_type=compute_type,
            )
        elif engine in {"whisper", "auto"} and WHISPER_AVAILABLE:
            model = whisper.load_model(model_name, device=device)
        else:
            raise RuntimeError(
                "No requested transcription backend is installed. Install faster-whisper, WhisperX, openai-whisper, or Parakeet dependencies."
            )

        _model_cache[cache_key] = model
        return model


def _select_faster_whisper_compute_type(device: str) -> str:
    """Choose a compute type that CTranslate2 reports as usable on this device."""
    priorities = (
        ("float16", "int8_float16", "int8_float32", "int8", "float32")
        if device == "cuda"
        else ("int8", "int8_float32", "float32")
    )
    try:
        import ctranslate2

        supported = ctranslate2.get_supported_compute_types(device)
        for compute_type in priorities:
            if compute_type in supported:
                return compute_type
        logger.warning(
            "CTranslate2 reported no preferred Faster Whisper compute type for %s: %s",
            device,
            sorted(supported),
        )
    except (ImportError, RuntimeError, ValueError) as error:
        logger.warning("Could not inspect CTranslate2 %s compute types: %s", device, error)
    return "float16" if device == "cuda" else "int8"


def _is_faster_whisper_acceleration_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "float16 compute type",
            "cuda",
            "cudnn",
            "cublas",
            "compute type",
            "out of memory",
        )
    )


def _resolve_engine(engine: TranscriptionEngine) -> TranscriptionEngine:
    if engine != "auto":
        if engine not in {"faster-whisper", "whisperx", "whisper", "parakeet"}:
            raise RuntimeError(f"Unknown transcription engine: {engine}")
        if engine == "parakeet" and not NEMO_AVAILABLE:
            raise RuntimeError(
                "Parakeet TDT v3 is not included in this ScriptCut build. "
                "Choose Faster Whisper; its speech model downloads automatically on first use."
            )
        if engine == "faster-whisper" and not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper is not installed. Run the standard backend setup.")
        if engine == "whisperx" and not WHISPERX_AVAILABLE:
            raise RuntimeError(
                "WhisperX is not included in this ScriptCut build. Downloading a Whisper model "
                "manually will not install WhisperX. Choose Faster Whisper; its selected model "
                "downloads automatically on first use."
            )
        if engine == "whisper" and not WHISPER_AVAILABLE:
            raise RuntimeError(
                "Legacy Whisper is not included in this ScriptCut build. Choose Faster Whisper; "
                "its selected model downloads automatically on first use."
            )
        return engine
    if FASTER_WHISPER_AVAILABLE:
        return "faster-whisper"
    if NEMO_AVAILABLE:
        return "parakeet"
    if WHISPERX_AVAILABLE:
        return "whisperx"
    if WHISPER_AVAILABLE:
        return "whisper"
    raise RuntimeError(
        "No transcription backend is installed. Install faster-whisper, NVIDIA NeMo ASR, WhisperX, or openai-whisper."
    )


def _load_parakeet_model(model_name: str, device: str):
    if NEMO_AVAILABLE:
        model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
        if hasattr(model, "to"):
            model = model.to(device)
        if hasattr(model, "eval"):
            model.eval()
        return ("nemo", model)

    raise RuntimeError(
        "Parakeet TDT v3 is selected but NVIDIA NeMo ASR is not installed. "
        "Install them with `pip install -U nemo_toolkit['asr']`."
    )


def get_transcription_engine_status() -> dict:
    return {
        "default_engine": (
            "faster-whisper"
            if FASTER_WHISPER_AVAILABLE
            else "parakeet"
            if NEMO_AVAILABLE
            else "whisperx"
            if WHISPERX_AVAILABLE
            else "whisper"
            if WHISPER_AVAILABLE
            else None
        ),
        "default_model": SMART_MODEL_NAME if FASTER_WHISPER_AVAILABLE else (
            PARAKEET_DEFAULT_MODEL if NEMO_AVAILABLE else "base"
        ),
        "recommended_language": "ru",
        "engines": {
            "faster-whisper": {
                "available": FASTER_WHISPER_AVAILABLE,
                "selectable": FASTER_WHISPER_AVAILABLE,
                "default_model": SMART_MODEL_NAME,
                "label": "ScriptCut Smart Transcript",
                "first_class": True,
                "profiles": {
                    "smart": "large-v3-turbo on NVIDIA GPU, small on CPU",
                    "base": "fastest practical local draft",
                    "large-v3-turbo": "maximum speed/accuracy balance on a capable GPU",
                    "large-v3": "maximum accuracy, slowest and largest",
                },
                "download_behavior": "Selected speech model downloads automatically on first use.",
                "unavailable_reason": (
                    None
                    if FASTER_WHISPER_AVAILABLE
                    else "The core transcription package is missing from this installation."
                ),
            },
            "parakeet": {
                "available": NEMO_AVAILABLE,
                "selectable": NEMO_AVAILABLE,
                "default_model": PARAKEET_DEFAULT_MODEL,
                "label": "Parakeet TDT v3 multilingual",
                "first_class": True,
                "languages": 25,
                "install_hint": "pip install -U nemo_toolkit['asr']",
                "download_behavior": "Optional engine; not installed by downloading a speech model.",
                "unavailable_reason": (
                    None
                    if NEMO_AVAILABLE
                    else "Not included in this desktop build. Use Faster Whisper."
                ),
            },
            "whisperx": {
                "available": WHISPERX_AVAILABLE,
                "selectable": WHISPERX_AVAILABLE,
                "default_model": "base",
                "label": "WhisperX aligned",
                "first_class": True,
                "download_behavior": "Optional engine; not installed by downloading a Whisper model.",
                "unavailable_reason": (
                    None
                    if WHISPERX_AVAILABLE
                    else "Not included in this desktop build. Use Faster Whisper."
                ),
            },
            "whisper": {
                "available": WHISPER_AVAILABLE,
                "selectable": WHISPER_AVAILABLE,
                "default_model": "base",
                "label": "Whisper fallback",
                "first_class": True,
                "download_behavior": "Optional legacy engine.",
                "unavailable_reason": (
                    None
                    if WHISPER_AVAILABLE
                    else "Not included in this desktop build. Use Faster Whisper."
                ),
            },
        },
    }


def _select_smart_faster_whisper_model(device: str) -> str:
    override = os.environ.get("SCRIPTCUT_SMART_TRANSCRIPTION_MODEL", "").strip()
    if override:
        return override
    # large-v3-turbo is the strongest practical long-form default when
    # CTranslate2 can use an NVIDIA GPU. On CPU, small is a meaningful accuracy
    # upgrade over the old base default without making hour-long VODs unusable.
    return "large-v3-turbo" if device.startswith("cuda") else "small"


def _normalize_model_for_engine(
    model_name: str,
    engine: TranscriptionEngine,
    device: str = "cpu",
) -> str:
    if engine == "parakeet" and model_name in WHISPER_MODEL_NAMES:
        return PARAKEET_DEFAULT_MODEL
    if engine == "faster-whisper" and model_name == SMART_MODEL_NAME:
        return _select_smart_faster_whisper_model(device)
    return model_name


def transcribe_audio(
    file_path: str,
    model_name: str = SMART_MODEL_NAME,
    engine: TranscriptionEngine = "auto",
    use_gpu: bool = True,
    use_cache: bool = True,
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> dict:
    """
    Transcribe audio/video file and return word-level timestamps.

    Returns:
        dict with keys: words, segments, language
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))

    resolved_engine = _resolve_engine(engine)
    requested_model = model_name
    device = _get_device(use_gpu)
    model_name = _normalize_model_for_engine(model_name, resolved_engine, device)
    cache_operation = f"transcribe_v3_{resolved_engine}_{language or 'auto'}"

    if use_cache:
        cached = load_from_cache(file_path, model_name, cache_operation)
        if cached:
            logger.info("Using cached transcription")
            return cached

    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    audio_path = file_path
    temporary_audio_path = None
    if resolved_engine == "parakeet" and file_path.suffix.lower() in video_extensions:
        from utils.audio_processing import extract_audio

        temporary_audio_path = extract_audio(file_path)
        audio_path = temporary_audio_path

    try:
        model = _load_model(model_name, device, resolved_engine, progress_callback)

        logger.info(f"Transcribing with {resolved_engine}: {file_path}")

        if resolved_engine == "parakeet":
            result = _transcribe_parakeet(model, str(audio_path))
        elif resolved_engine == "faster-whisper":
            try:
                result = _transcribe_faster_whisper(
                    model,
                    str(audio_path),
                    language,
                    progress_callback,
                )
            except (RuntimeError, ValueError) as error:
                if not device.startswith("cuda") or not _is_faster_whisper_acceleration_error(error):
                    raise
                logger.warning(
                    "CUDA Faster Whisper inference failed; retrying safely on CPU: %s",
                    error,
                )
                _model_cache.pop(f"{resolved_engine}_{model_name}_{device}", None)
                cpu_model_name = (
                    _select_smart_faster_whisper_model("cpu")
                    if requested_model == SMART_MODEL_NAME
                    else model_name
                )
                cpu_model = _load_model(
                    cpu_model_name,
                    "cpu",
                    resolved_engine,
                    progress_callback,
                )
                result = _transcribe_faster_whisper(
                    cpu_model,
                    str(audio_path),
                    language,
                    progress_callback,
                )
                model_name = cpu_model_name
        elif resolved_engine == "whisperx":
            result = _transcribe_whisperx(model, str(audio_path), device, language)
        else:
            result = _transcribe_standard(model, str(audio_path), language)
    finally:
        if temporary_audio_path is not None:
            from utils.audio_processing import cleanup_temp_audio_file

            cleanup_temp_audio_file(temporary_audio_path)

    result["engine"] = resolved_engine
    result["model"] = model_name
    result["requested_model"] = requested_model
    result["quality_profile"] = "smart" if requested_model == SMART_MODEL_NAME else "custom"

    if use_cache:
        save_to_cache(file_path, result, model_name, cache_operation)

    return result


def _transcribe_faster_whisper(
    model,
    audio_path: str,
    language: Optional[str],
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> dict:
    is_russian = language in {"ru", "russian", "Русский"}
    options = {
        "word_timestamps": True,
        "vad_filter": True,
        "vad_parameters": {
            "threshold": 0.45,
            "min_speech_duration_ms": 120,
            "min_silence_duration_ms": 280,
            "speech_pad_ms": 240,
        },
        "beam_size": 5,
        "best_of": 5,
        "patience": 1.0,
        "temperature": [0.0, 0.2, 0.4],
        "condition_on_previous_text": True,
        "hallucination_silence_threshold": 2.0,
        "language_detection_segments": 3,
    }
    if language:
        options["language"] = language
    if is_russian:
        options["initial_prompt"] = RUSSIAN_CONTEXT_PROMPT
        options["hotwords"] = RUSSIAN_PROFANITY_HOTWORDS

    segment_iterator, info = model.transcribe(audio_path, **options)
    words = []
    segments = []
    duration = max(float(getattr(info, "duration", 0) or 0), 0.001)
    last_reported_progress = -1
    for segment_id, segment in enumerate(segment_iterator):
        segment_words = []
        for item in segment.words or []:
            word = {
                "word": str(item.word or "").strip(),
                "start": round(float(item.start or 0), 3),
                "end": round(float(item.end or item.start or 0), 3),
                "confidence": round(float(item.probability or 0), 3),
            }
            if not word["word"]:
                continue
            words.append(word)
            segment_words.append(word)
        segments.append({
            "id": segment_id,
            "start": round(float(segment.start or 0), 3),
            "end": round(float(segment.end or segment.start or 0), 3),
            "text": str(segment.text or "").strip(),
            "words": segment_words,
        })
        if progress_callback:
            percent = min(72, max(10, int(10 + (float(segment.end or 0) / duration) * 62)))
            if percent > last_reported_progress:
                progress_callback(percent, f"Расшифровка: {percent}% · точные тайминги слов")
                last_reported_progress = percent

    return {
        "words": words,
        "segments": segments,
        "language": str(getattr(info, "language", None) or language or "auto"),
        "language_probability": round(float(getattr(info, "language_probability", 0) or 0), 3),
        "duration_after_vad": round(float(getattr(info, "duration_after_vad", duration) or duration), 3),
    }


def _transcribe_parakeet(model_bundle, audio_path: str) -> dict:
    backend = model_bundle[0]
    if backend == "nemo":
        asr_model = model_bundle[1]
        output = asr_model.transcribe([audio_path], timestamps=True)[0]
        if isinstance(output, dict):
            text = output.get("text", "") or ""
            timestamp = output.get("timestamp", {}) or {}
        else:
            text = getattr(output, "text", "") or ""
            timestamp = getattr(output, "timestamp", {}) or {}
        word_stamps = timestamp.get("word") or []
        segment_stamps = timestamp.get("segment") or []
    words = [_normalize_parakeet_word(stamp) for stamp in word_stamps]
    words = [word for word in words if word["word"] and word["end"] >= word["start"]]
    segments = _normalize_parakeet_segments(segment_stamps, words, text)
    return {
        "words": words,
        "segments": segments,
        "language": "auto",
    }


def _normalize_parakeet_word(stamp: dict) -> dict:
    word = stamp.get("word") or stamp.get("text") or stamp.get("segment") or ""
    return {
        "word": str(word).strip(),
        "start": round(float(stamp.get("start", 0) or 0), 3),
        "end": round(float(stamp.get("end", 0) or 0), 3),
        "confidence": round(float(stamp.get("confidence", stamp.get("score", 0.9)) or 0.9), 3),
    }


def _normalize_parakeet_segments(segment_stamps: list, words: list, fallback_text: str) -> list:
    if not segment_stamps:
        return [{
            "id": 0,
            "start": words[0]["start"] if words else 0,
            "end": words[-1]["end"] if words else 0,
            "text": fallback_text,
            "words": words,
        }]

    segments = []
    for i, stamp in enumerate(segment_stamps):
        start = float(stamp.get("start", 0) or 0)
        end = float(stamp.get("end", start) or start)
        segment_words = [word for word in words if word["start"] >= start and word["end"] <= end]
        segments.append({
            "id": i,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": str(stamp.get("segment") or stamp.get("text") or " ".join(word["word"] for word in segment_words)).strip(),
            "words": segment_words,
        })
    return segments


def _transcribe_whisperx(model, audio_path: str, device: str, language: Optional[str]) -> dict:
    audio = whisperx.load_audio(audio_path)
    transcribe_opts = {}
    if language:
        transcribe_opts["language"] = language

    result = model.transcribe(audio, batch_size=16, **transcribe_opts)
    detected_language = result.get("language", "en")

    align_model, align_metadata = whisperx.load_align_model(
        language_code=detected_language,
        device=device,
    )
    aligned = whisperx.align(
        result["segments"],
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    words = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            words.append({
                "word": w.get("word", ""),
                "start": round(w.get("start", 0), 3),
                "end": round(w.get("end", 0), 3),
                "confidence": round(w.get("score", 0), 3),
            })

    segments = []
    for i, seg in enumerate(aligned.get("segments", [])):
        seg_words = []
        for w in seg.get("words", []):
            seg_words.append({
                "word": w.get("word", ""),
                "start": round(w.get("start", 0), 3),
                "end": round(w.get("end", 0), 3),
                "confidence": round(w.get("score", 0), 3),
            })
        segments.append({
            "id": i,
            "start": round(seg.get("start", 0), 3),
            "end": round(seg.get("end", 0), 3),
            "text": seg.get("text", "").strip(),
            "words": seg_words,
        })

    return {
        "words": words,
        "segments": segments,
        "language": detected_language,
    }


def _transcribe_standard(model, audio_path: str, language: Optional[str]) -> dict:
    """Fallback: standard Whisper (segment-level only, synthesized word timestamps)."""
    opts = {}
    if language:
        opts["language"] = language

    result = model.transcribe(audio_path, **opts)
    detected_language = result.get("language", "en")

    words = []
    segments = []

    for i, seg in enumerate(result.get("segments", [])):
        text = seg.get("text", "").strip()
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)
        seg_words_text = text.split()
        duration = seg_end - seg_start

        seg_words = []
        for j, w_text in enumerate(seg_words_text):
            w_start = seg_start + (j / max(len(seg_words_text), 1)) * duration
            w_end = seg_start + ((j + 1) / max(len(seg_words_text), 1)) * duration
            word_obj = {
                "word": w_text,
                "start": round(w_start, 3),
                "end": round(w_end, 3),
                "confidence": 0.5,
            }
            words.append(word_obj)
            seg_words.append(word_obj)

        segments.append({
            "id": i,
            "start": round(seg_start, 3),
            "end": round(seg_end, 3),
            "text": text,
            "words": seg_words,
        })

    return {
        "words": words,
        "segments": segments,
        "language": detected_language,
    }
