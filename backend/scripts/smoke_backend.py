"""Fast backend smoke checks for export, captions, and job lifecycle behavior."""

from __future__ import annotations

import time
import unittest
import subprocess
from array import array
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from routers import export as export_router
from routers import ai as ai_router
from routers import system as system_router
from local_api_auth import is_authorized_local_api_request
from services import video_editor
from services import ai_provider
from services import transcription
from services import waveform
from services.caption_generator import generate_srt
from services.job_manager import JobManager


class BackendSmokeTests(unittest.TestCase):
    def test_modern_ffmpeg_ass_filter_is_detected(self) -> None:
        result = subprocess.CompletedProcess(
            ["ffmpeg", "-filters"],
            0,
            stdout="Filters:\n ... ass               V->V       Render ASS subtitles\n",
            stderr="",
        )
        video_editor.supports_ass_subtitles.cache_clear()
        try:
            with (
                patch.object(video_editor, "_find_ffmpeg", return_value="ffmpeg"),
                patch.object(video_editor.subprocess, "run", return_value=result),
            ):
                self.assertTrue(video_editor.supports_ass_subtitles())
        finally:
            video_editor.supports_ass_subtitles.cache_clear()

    def test_ffmpeg_ass_detection_ignores_capability_column_count(self) -> None:
        result = subprocess.CompletedProcess(
            ["ffmpeg", "-filters"],
            0,
            stdout="Filters:\n TSC. ass               V->V       Render ASS subtitles\n",
            stderr="",
        )
        video_editor.supports_ass_subtitles.cache_clear()
        try:
            with (
                patch.object(video_editor, "_find_ffmpeg", return_value="ffmpeg"),
                patch.object(video_editor.subprocess, "run", return_value=result),
            ):
                self.assertTrue(video_editor.supports_ass_subtitles())
        finally:
            video_editor.supports_ass_subtitles.cache_clear()

    def test_ffprobe_frame_rate_is_parsed_without_eval(self) -> None:
        self.assertAlmostEqual(video_editor._parse_frame_rate("30000/1001"), 29.97002997)
        self.assertEqual(video_editor._parse_frame_rate("0/0"), 0)
        self.assertEqual(video_editor._parse_frame_rate("__import__('os').system('false')/1"), 0)

    def test_faster_whisper_cuda_failure_falls_back_to_cpu(self) -> None:
        transcription._model_cache.clear()
        fake_model = object()
        try:
            with (
                patch.object(transcription, "FASTER_WHISPER_AVAILABLE", True),
                patch.object(
                    transcription,
                    "WhisperModel",
                    side_effect=[RuntimeError("missing CUDA runtime"), fake_model],
                ) as model_factory,
            ):
                self.assertIs(
                    transcription._load_model("base", "cuda", "faster-whisper"),
                    fake_model,
                )
                self.assertEqual(model_factory.call_args_list[1].kwargs["device"], "cpu")
                self.assertEqual(model_factory.call_args_list[1].kwargs["compute_type"], "int8")
        finally:
            transcription._model_cache.clear()

    def test_faster_whisper_uses_supported_cuda_compute_type(self) -> None:
        transcription._model_cache.clear()
        fake_model = object()
        fake_ctranslate2 = SimpleNamespace(
            get_supported_compute_types=lambda device: {"int8_float32", "float32"},
        )
        try:
            with (
                patch.dict(sys.modules, {"ctranslate2": fake_ctranslate2}),
                patch.object(transcription, "FASTER_WHISPER_AVAILABLE", True),
                patch.object(transcription, "WhisperModel", return_value=fake_model) as model_factory,
            ):
                self.assertIs(
                    transcription._load_model("base", "cuda", "faster-whisper"),
                    fake_model,
                )
                self.assertEqual(model_factory.call_args.kwargs["device"], "cuda")
                self.assertEqual(model_factory.call_args.kwargs["compute_type"], "int8_float32")
        finally:
            transcription._model_cache.clear()

    def test_faster_whisper_inference_float16_failure_retries_original_video_on_cpu(self) -> None:
        class FailingGpuModel:
            def transcribe(self, _audio_path, **_options):
                raise RuntimeError(
                    "Requested float16 compute type, but the target device or backend "
                    "do not support efficient float16 computation."
                )

        seen_paths: list[str] = []

        class WorkingCpuModel:
            def transcribe(self, audio_path, **_options):
                seen_paths.append(audio_path)
                segment = SimpleNamespace(
                    start=0,
                    end=1,
                    text="hello",
                    words=[
                        SimpleNamespace(
                            word="hello",
                            start=0,
                            end=1,
                            probability=0.9,
                        )
                    ],
                )
                return iter([segment]), SimpleNamespace(language="en")

        with TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "long-stream.mp4"
            video_path.write_bytes(b"placeholder")
            with (
                patch.object(transcription, "FASTER_WHISPER_AVAILABLE", True),
                patch.object(transcription, "_get_device", return_value="cuda"),
                patch.object(
                    transcription,
                    "_load_model",
                    side_effect=[FailingGpuModel(), WorkingCpuModel()],
                ) as load_model,
            ):
                result = transcription.transcribe_audio(
                    str(video_path),
                    engine="faster-whisper",
                    use_cache=False,
                )

        self.assertEqual(result["words"][0]["word"], "hello")
        self.assertEqual(seen_paths, [str(video_path)])
        self.assertEqual(load_model.call_args_list[1].args, ("base", "cpu", "faster-whisper"))

    def test_waveform_reduces_media_to_bounded_peak_count(self) -> None:
        pcm = array("h", [-32768, -12000, 0, 8000, 32767, -4000, 2000, 0]).tobytes()
        completed = subprocess.CompletedProcess(
            ["ffmpeg"],
            0,
            stdout=pcm,
            stderr=b"",
        )
        with TemporaryDirectory() as tmp:
            media_path = Path(tmp) / "stream.mp4"
            media_path.write_bytes(b"placeholder")
            with (
                patch.object(waveform, "_probe_duration", return_value=4 * 60 * 60),
                patch.object(waveform, "find_ffmpeg", return_value="ffmpeg"),
                patch.object(waveform.subprocess, "run", return_value=completed) as run,
            ):
                result = waveform.generate_waveform(str(media_path), points=4000)

        self.assertEqual(result["sample_rate"], 8)
        self.assertEqual(result["points"], 8)
        self.assertEqual(result["peaks"][0], [-1.0, -1.0])
        self.assertIn("pipe:1", run.call_args.args[0])

    def test_packaged_backend_requires_local_api_token(self) -> None:
        self.assertTrue(is_authorized_local_api_request("", None))
        self.assertFalse(is_authorized_local_api_request("smoke-token", None))
        self.assertFalse(is_authorized_local_api_request("smoke-token", "wrong-token"))
        self.assertTrue(is_authorized_local_api_request("smoke-token", "smoke-token"))

    def test_sidecar_export_uses_caption_line_length(self) -> None:
        captured: dict[str, str] = {}

        def fake_stream_copy(input_path, output_path, segments, progress_callback=None):
            Path(output_path).write_text("video", encoding="utf-8")
            return output_path

        def fake_save_captions(content: str, output_path: str):
            captured["content"] = content
            Path(output_path).write_text(content, encoding="utf-8")
            return output_path

        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            output_path = str(Path(tmp) / "edited.mp4")
            request = export_router.ExportRequest(
                input_path=str(input_path),
                output_path=output_path,
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
                captions="sidecar",
                captionStyle=export_router.CaptionStyleModel(wordsPerLine=2),
                words=[
                    export_router.ExportWordModel(word="one", start=0, end=0.5),
                    export_router.ExportWordModel(word="two", start=0.5, end=1),
                    export_router.ExportWordModel(word="three", start=1, end=1.5),
                ],
            )

            with (
                patch.object(export_router, "export_stream_copy", fake_stream_copy),
                patch.object(export_router, "save_captions", fake_save_captions),
            ):
                result = export_router.run_export(request)

        self.assertTrue(result["srt_path"].endswith(".srt"))
        self.assertIn("one two", captured["content"])
        self.assertIn("three", captured["content"])
        self.assertEqual(captured["content"].count("-->"), 2)

    def test_burn_in_caption_falls_back_to_sidecar_without_ass_filter(self) -> None:
        captured: dict[str, str] = {}

        def fake_reencode(input_path, output_path, segments, **_kwargs):
            Path(output_path).write_text("video", encoding="utf-8")
            return output_path

        def fake_save_captions(content: str, output_path: str):
            captured["content"] = content
            Path(output_path).write_text(content, encoding="utf-8")
            return output_path

        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            output_path = str(Path(tmp) / "clip.mp4")
            request = export_router.ExportRequest(
                input_path=str(input_path),
                output_path=output_path,
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
                aspectRatio="vertical",
                captions="burn-in",
                words=[export_router.ExportWordModel(word="caption", start=0, end=0.5)],
            )

            with (
                patch.object(export_router, "supports_ass_subtitles", return_value=False),
                patch.object(export_router, "export_reencode", fake_reencode),
                patch.object(export_router, "save_captions", fake_save_captions),
            ):
                result = export_router.run_export(request)

        self.assertTrue(result["srt_path"].endswith(".srt"))
        self.assertIn("Burn-in captions are unavailable", result["warnings"][0])
        self.assertIn("caption", captured["content"])

    def test_export_without_output_path_uses_backend_temp_file(self) -> None:
        captured: dict[str, str] = {}

        def fake_stream_copy(input_path, output_path, segments, progress_callback=None):
            captured["output_path"] = output_path
            Path(output_path).write_text("video", encoding="utf-8")
            return output_path

        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input clip.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            request = export_router.ExportRequest(
                input_path=str(input_path),
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
                format="mp4",
            )

            with patch.object(export_router, "export_stream_copy", fake_stream_copy):
                result = export_router.run_export(request)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output_path"], captured["output_path"])
        self.assertTrue(result["output_path"].endswith(".mp4"))
        self.assertIn("scriptcut_exports", result["output_path"])

    def test_export_preflight_rejects_missing_input_file(self) -> None:
        with TemporaryDirectory() as tmp:
            request = export_router.ExportRequest(
                input_path=str(Path(tmp) / "missing.mp4"),
                output_path=str(Path(tmp) / "edited.mp4"),
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
            )

            with self.assertRaisesRegex(ValueError, "Input media file was not found"):
                export_router.run_export(request)

    def test_export_preflight_rejects_bad_destination_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            request = export_router.ExportRequest(
                input_path=str(input_path),
                output_path=str(Path(tmp) / "missing-folder" / "edited.mp4"),
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
            )

            with self.assertRaisesRegex(ValueError, "Export destination folder does not exist"):
                export_router.run_export(request)

    def test_export_preflight_rejects_source_overwrite(self) -> None:
        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            request = export_router.ExportRequest(
                input_path=str(input_path),
                output_path=str(input_path),
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
            )

            with self.assertRaisesRegex(ValueError, "cannot overwrite"):
                export_router.run_export(request)

    def test_reencode_video_only_does_not_map_audio(self) -> None:
        captured: dict[str, list[str]] = {}

        def fake_run_ffmpeg(cmd, progress_callback=None):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with TemporaryDirectory() as tmp:
            input_path = str(Path(tmp) / "input.mp4")
            output_path = str(Path(tmp) / "output.mp4")
            Path(input_path).write_text("placeholder", encoding="utf-8")

            with (
                patch.object(video_editor, "_find_ffmpeg", return_value="ffmpeg"),
                patch.object(video_editor, "_has_audio_stream", return_value=False),
                patch.object(video_editor, "_run_ffmpeg", fake_run_ffmpeg),
            ):
                result = video_editor.export_reencode(
                    input_path,
                    output_path,
                    [{"start": 0, "end": 2}],
                )

        self.assertEqual(Path(result).resolve(), Path(output_path).resolve())
        command_text = " ".join(captured["cmd"])
        self.assertNotIn("[outa]", command_text)
        self.assertIn("concat=n=1:v=1:a=0[outv]", command_text)

    def test_ffmpeg_runner_drains_large_stderr_without_deadlock(self) -> None:
        result = video_editor._run_ffmpeg([
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('x' * 262144)",
        ])

        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stderr), 64 * 1024)

    def test_subtitle_export_uses_explicit_ass_filename_option(self) -> None:
        captured: dict[str, list[str]] = {}

        def fake_run_ffmpeg(cmd, progress_callback=None):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with TemporaryDirectory() as tmp:
            input_path = str(Path(tmp) / "input.mp4")
            output_path = str(Path(tmp) / "output.mp4")
            subtitle_path = str(Path(tmp) / "captions.ass")
            Path(input_path).write_text("placeholder", encoding="utf-8")
            Path(subtitle_path).write_text("[Script Info]", encoding="utf-8")

            with (
                patch.object(video_editor, "_find_ffmpeg", return_value="ffmpeg"),
                patch.object(video_editor, "_has_audio_stream", return_value=False),
                patch.object(video_editor, "_run_ffmpeg", fake_run_ffmpeg),
            ):
                video_editor.export_reencode_with_subs(
                    input_path,
                    output_path,
                    [{"start": 0, "end": 2}],
                    subtitle_path,
                )

        filter_complex = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
        self.assertIn("ass=filename='", filter_complex)
        self.assertNotIn("ass='/", filter_complex)

    def test_bleep_audio_layer_mutes_source_and_adds_tone(self) -> None:
        filter_graph = video_editor._build_audio_trim_filter(
            0,
            {"start": 10.0, "end": 14.0},
            [{"start": 11.0, "end": 11.8, "kind": "bleep"}],
        )

        self.assertIn("volume=0:enable='between(t,1.000,1.800)'", filter_graph)
        self.assertIn("sine=frequency=1000", filter_graph)
        self.assertIn("amix=inputs=2", filter_graph)

    def test_captions_hide_deleted_words(self) -> None:
        srt = generate_srt(
            [
                {"word": "keep", "start": 0, "end": 0.5},
                {"word": "hide", "start": 0.5, "end": 1},
                {"word": "also-keep", "start": 1, "end": 1.5},
            ],
            deleted_indices={1},
            words_per_line=8,
        )

        self.assertIn("keep also-keep", srt)
        self.assertNotIn("hide", srt)

    def test_parakeet_timestamps_normalize_to_editor_contract(self) -> None:
        transcription = self._load_transcription_service_or_skip()
        words = [
            {"word": "Hello", "start": 0, "end": 0.4, "score": 0.92},
            {"word": "world", "start": 0.4, "end": 0.9},
        ]
        segments = [
            {"segment": "Hello world", "start": 0, "end": 0.9},
        ]

        normalized_words = [transcription._normalize_parakeet_word(stamp) for stamp in words]
        normalized_segments = transcription._normalize_parakeet_segments(segments, normalized_words, "Hello world")

        self.assertEqual(
            normalized_words,
            [
                {"word": "Hello", "start": 0.0, "end": 0.4, "confidence": 0.92},
                {"word": "world", "start": 0.4, "end": 0.9, "confidence": 0.9},
            ],
        )
        self.assertEqual(normalized_segments[0]["words"], normalized_words)
        self.assertEqual(normalized_segments[0]["text"], "Hello world")

    def test_unknown_transcription_engine_fails_clearly(self) -> None:
        transcription = self._load_transcription_service_or_skip()
        with self.assertRaisesRegex(RuntimeError, "Unknown transcription engine"):
            transcription._resolve_engine("not-real")

    def test_parakeet_auto_resolution_and_model_normalization(self) -> None:
        transcription = self._load_transcription_service_or_skip()
        original_nemo = transcription.NEMO_AVAILABLE
        original_whisperx = transcription.WHISPERX_AVAILABLE
        try:
            transcription.NEMO_AVAILABLE = True
            transcription.WHISPERX_AVAILABLE = True
            self.assertEqual(transcription._resolve_engine("auto"), "parakeet")
            self.assertEqual(
                transcription._normalize_model_for_engine("base", "parakeet"),
                transcription.PARAKEET_DEFAULT_MODEL,
            )
            self.assertEqual(
                transcription._normalize_model_for_engine(transcription.PARAKEET_DEFAULT_MODEL, "parakeet"),
                transcription.PARAKEET_DEFAULT_MODEL,
            )
        finally:
            transcription.NEMO_AVAILABLE = original_nemo
            transcription.WHISPERX_AVAILABLE = original_whisperx

    def test_transcription_engine_status_includes_parakeet(self) -> None:
        transcription = self._load_transcription_service_or_skip()
        status = transcription.get_transcription_engine_status()
        self.assertIn("faster-whisper", status["engines"])
        self.assertTrue(status["engines"]["faster-whisper"]["first_class"])
        self.assertIn("downloads automatically", status["engines"]["faster-whisper"]["download_behavior"])
        self.assertIn("parakeet", status["engines"])
        self.assertTrue(status["engines"]["parakeet"]["first_class"])
        self.assertEqual(status["engines"]["parakeet"]["default_model"], transcription.PARAKEET_DEFAULT_MODEL)
        if not status["engines"]["whisperx"]["available"]:
            self.assertFalse(status["engines"]["whisperx"]["selectable"])
            self.assertIn("desktop build", status["engines"]["whisperx"]["unavailable_reason"])

    def test_unavailable_whisperx_explains_that_manual_model_download_is_not_enough(self) -> None:
        transcription = self._load_transcription_service_or_skip()
        original_available = transcription.WHISPERX_AVAILABLE
        try:
            transcription.WHISPERX_AVAILABLE = False
            with self.assertRaisesRegex(RuntimeError, "Downloading a Whisper model manually"):
                transcription._resolve_engine("whisperx")
        finally:
            transcription.WHISPERX_AVAILABLE = original_available

    def test_faster_whisper_normalizes_word_timestamps(self) -> None:
        transcription = self._load_transcription_service_or_skip()

        class FakeWord:
            word = " привет "
            start = 0.25
            end = 0.75
            probability = 0.93

        class FakeSegment:
            start = 0.2
            end = 0.8
            text = " Привет "
            words = [FakeWord()]

        class FakeInfo:
            language = "ru"

        class FakeModel:
            def transcribe(self, audio_path, **options):
                self.audio_path = audio_path
                self.options = options
                return iter([FakeSegment()]), FakeInfo()

        model = FakeModel()
        result = transcription._transcribe_faster_whisper(model, "sample.wav", "ru")

        self.assertEqual(result["language"], "ru")
        self.assertEqual(
            result["words"],
            [{"word": "привет", "start": 0.25, "end": 0.75, "confidence": 0.93}],
        )
        self.assertTrue(model.options["word_timestamps"])
        self.assertTrue(model.options["vad_filter"])

    def test_system_checks_payload_covers_onboarding_requirements(self) -> None:
        import asyncio

        result = asyncio.run(system_router.system_checks())
        self.assertEqual(result["status"], "ok")
        for key in ("backend", "python", "ffmpeg", "transcription", "audio", "background"):
            self.assertIn(key, result["checks"])
            self.assertIn("ok", result["checks"][key])
            self.assertIn("detail", result["checks"][key])

    def test_system_diagnostics_is_report_safe(self) -> None:
        import asyncio

        with (
            patch.object(
                system_router,
                "_ffmpeg_status",
                return_value={
                    "ok": True,
                    "detail": "System: /Users/fernando/bin/ffmpeg",
                },
            ),
            patch.object(system_router, "supports_ass_subtitles", return_value=False),
        ):
            result = asyncio.run(system_router.system_diagnostics())

        self.assertEqual(result["backend"]["status"], "ready")
        self.assertEqual(result["ffmpeg"]["version"], "available")
        self.assertEqual(result["ffmpeg"]["captionFallback"], "sidecar-srt")
        self.assertNotIn("/Users/fernando", str(result))

    def test_recent_jobs_filters_and_bounds_logs(self) -> None:
        manager = JobManager()

        def target(progress):
            for index in range(16):
                progress(index * 6, f"progress {index}")

        export_job_id = manager.create("export", target)
        manager.create("transcribe", target)
        time.sleep(0.08)

        jobs = manager.recent(kind="export", limit=1)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], export_job_id)
        self.assertEqual(jobs[0]["kind"], "export")
        self.assertLessEqual(len(jobs[0]["logs"]), 12)
        self.assertNotIn("_target", jobs[0])

    def _load_transcription_service_or_skip(self):
        try:
            from services import transcription
            return transcription
        except ModuleNotFoundError as exc:
            self.skipTest(f"transcription stack unavailable in lean smoke environment: {exc}")

    def test_canceling_job_finalizes_as_canceled(self) -> None:
        manager = JobManager()

        def target(progress):
            time.sleep(0.05)
            progress(50, "halfway")

        job_id = manager.create("smoke", target)
        time.sleep(0.01)
        cancel_response = manager.cancel(job_id)
        self.assertIsNotNone(cancel_response)
        self.assertEqual(cancel_response["status"], "canceling")

        time.sleep(0.12)
        final = manager.get(job_id)
        self.assertIsNotNone(final)
        self.assertEqual(final["status"], "canceled")

    def test_retry_failed_job_tracks_original_and_attempt(self) -> None:
        manager = JobManager()

        def target(progress):
            progress(20, "about to fail")
            raise RuntimeError("expected failure")

        job_id = manager.create("smoke", target)
        time.sleep(0.08)
        failed = manager.get(job_id)
        self.assertIsNotNone(failed)
        self.assertEqual(failed["status"], "failed")

        retry_job_id = manager.retry(job_id)
        self.assertIsNotNone(retry_job_id)
        time.sleep(0.08)
        retried = manager.get(retry_job_id)
        self.assertIsNotNone(retried)
        self.assertEqual(retried["status"], "failed")
        self.assertEqual(retried["originalJobId"], job_id)
        self.assertEqual(retried["attempt"], 2)

    def test_background_failure_cleans_temporary_export_artifact(self) -> None:
        def fake_stream_copy(input_path, output_path, segments, progress_callback=None):
            Path(output_path).write_text("video", encoding="utf-8")
            return output_path

        def fake_remove_background(input_path, output_path, replacement, replacement_value, progress_callback=None):
            Path(output_path).write_text("partial background render", encoding="utf-8")
            raise RuntimeError("background removal failed")

        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            output_path = str(Path(tmp) / "edited.mp4")
            background_path = output_path + ".bg.mp4"
            request = export_router.ExportRequest(
                input_path=str(input_path),
                output_path=output_path,
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
                backgroundRemoval=export_router.BackgroundRemovalModel(enabled=True),
            )

            with (
                patch.object(export_router, "export_stream_copy", fake_stream_copy),
                patch.object(export_router, "remove_background_on_export", fake_remove_background),
            ):
                with self.assertRaises(RuntimeError):
                    export_router.run_export(request)

        self.assertFalse(Path(background_path).exists())

    def test_audio_enhancement_failure_cleans_temporary_mux_artifact(self) -> None:
        def fake_stream_copy(input_path, output_path, segments, progress_callback=None):
            Path(output_path).write_text("video", encoding="utf-8")
            return output_path

        def fake_clean_audio(input_path, output_path):
            Path(output_path).write_text("audio", encoding="utf-8")

        def fake_mux_audio(video_path, audio_path, output_path):
            Path(output_path).write_text("partial mux", encoding="utf-8")
            raise RuntimeError("mux failed")

        with TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mp4"
            input_path.write_text("placeholder", encoding="utf-8")
            output_path = str(Path(tmp) / "edited.mp4")
            muxed_path = output_path + ".muxed.mp4"
            request = export_router.ExportRequest(
                input_path=str(input_path),
                output_path=output_path,
                keep_segments=[export_router.SegmentModel(start=0, end=4)],
                enhanceAudio=True,
            )

            with (
                patch.object(export_router, "export_stream_copy", fake_stream_copy),
                patch.object(export_router, "clean_audio", fake_clean_audio),
                patch.object(export_router, "_mux_audio", fake_mux_audio),
            ):
                result = export_router.run_export(request)

        self.assertEqual(result["status"], "ok")
        self.assertIn("warnings", result)
        self.assertFalse(Path(muxed_path).exists())

    def test_edit_plan_normalizes_safe_delete_ranges(self) -> None:
        words = [
            {"index": 0, "word": "Well", "start": 0.0, "end": 0.2},
            {"index": 1, "word": "I", "start": 0.2, "end": 0.4},
            {"index": 2, "word": "think", "start": 0.4, "end": 0.8},
        ]
        response = """
        {
          "summary": "Tighten the opening.",
          "suggestions": [
            {"action": "delete", "startWordIndex": 0, "endWordIndex": 0, "reason": "Filler opener", "confidence": 0.91},
            {"action": "replace", "startWordIndex": 1, "endWordIndex": 2, "reason": "Unsupported action", "confidence": 0.8},
            {"action": "delete", "startWordIndex": 9, "endWordIndex": 10, "reason": "Out of range", "confidence": 0.8}
          ]
        }
        """

        with patch.object(ai_provider.AIProvider, "complete", return_value=response):
            result = ai_provider.create_edit_plan(
                instruction="Make this tighter",
                transcript="Well I think",
                words=words,
            )

        self.assertEqual(result["summary"], "Tighten the opening.")
        self.assertEqual(len(result["suggestions"]), 1)
        suggestion = result["suggestions"][0]
        self.assertEqual(suggestion["action"], "delete")
        self.assertEqual(suggestion["startWordIndex"], 0)
        self.assertEqual(suggestion["endWordIndex"], 0)
        self.assertEqual(suggestion["startTime"], 0.0)
        self.assertEqual(suggestion["endTime"], 0.2)
        self.assertEqual(suggestion["text"], "Well")

    def test_topic_edit_plan_chunks_refines_and_returns_reviewable_complement(self) -> None:
        words = [
            {
                "index": index,
                "word": word,
                "start": index * 0.5,
                "end": (index + 1) * 0.5,
            }
            for index, word in enumerate(
                "вступление ни о чем сегодня обсуждаем оптимизацию беременности "
                "важная мысль и вывод потом сменили тему про игры".split()
            )
        ]
        responses = [
            """
            {
              "relevantRanges": [
                {
                  "startWordIndex": 3,
                  "endWordIndex": 9,
                  "reason": "Разговор об оптимизации беременности",
                  "confidence": 0.94
                }
              ]
            }
            """,
            """
            {
              "startWordIndex": 4,
              "endWordIndex": 9,
              "reason": "Законченная мысль по теме",
              "confidence": 0.96
            }
            """,
        ]
        progress_updates = []

        with patch.object(ai_provider.AIProvider, "complete", side_effect=responses) as complete:
            result = ai_provider.create_topic_edit_plan(
                instruction="оставь всё про оптимизацию беременности",
                words=words,
                context_padding=0,
                progress_callback=lambda percent, message: progress_updates.append((percent, message)),
            )

        self.assertEqual(complete.call_count, 2)
        self.assertEqual(len(result["selectedSegments"]), 1)
        selected = result["selectedSegments"][0]
        self.assertEqual(selected["startWordIndex"], 4)
        self.assertEqual(selected["endWordIndex"], 9)
        self.assertEqual(
            [(item["startWordIndex"], item["endWordIndex"]) for item in result["suggestions"]],
            [(0, 3), (10, len(words) - 1)],
        )
        self.assertEqual(result["metrics"]["chunkCount"], 1)
        self.assertEqual(progress_updates[-1][0], 100)

    def test_topic_edit_plan_never_deletes_everything_when_no_match_is_found(self) -> None:
        words = [
            {"index": 0, "word": "другая", "start": 0.0, "end": 0.4},
            {"index": 1, "word": "тема", "start": 0.4, "end": 0.8},
        ]

        with patch.object(
            ai_provider.AIProvider,
            "complete",
            return_value='{"relevantRanges": []}',
        ):
            result = ai_provider.create_topic_edit_plan(
                instruction="беременность",
                words=words,
            )

        self.assertEqual(result["selectedSegments"], [])
        self.assertEqual(result["suggestions"], [])

    def test_codex_topic_edit_uses_larger_windows_to_reduce_plan_turns(self) -> None:
        words = [
            {
                "index": index,
                "word": f"word-{index}",
                "start": index * 0.25,
                "end": (index + 1) * 0.25,
            }
            for index in range(2400)
        ]

        with patch.object(
            ai_provider.AIProvider,
            "complete",
            return_value='{"relevantRanges": []}',
        ) as complete:
            result = ai_provider.create_topic_edit_plan(
                instruction="find one topic",
                words=words,
                provider="codex",
            )

        self.assertEqual(complete.call_count, 1)
        self.assertEqual(result["metrics"]["chunkCount"], 1)

    def test_xai_provider_uses_official_openai_compatible_endpoint(self) -> None:
        with patch.object(
            ai_provider,
            "_openai_compatible_complete",
            return_value="ok",
        ) as complete:
            result = ai_provider.AIProvider.complete(
                prompt="test",
                provider="xai",
                api_key="xai-key",
            )

        self.assertEqual(result, "ok")
        args = complete.call_args.args
        self.assertEqual(args[1], "grok-4.5")
        self.assertEqual(args[3], "https://api.x.ai/v1")
        self.assertEqual(args[6], "xAI")
        self.assertEqual(args[7], "xai")

    def test_codex_status_requires_chatgpt_managed_login(self) -> None:
        version = subprocess.CompletedProcess(
            ["codex", "--version"],
            0,
            stdout="codex-cli 1.2.3\n",
            stderr="",
        )
        login = subprocess.CompletedProcess(
            ["codex", "login", "status"],
            0,
            stdout="Logged in using ChatGPT\n",
            stderr="",
        )
        with (
            patch.object(ai_provider, "_find_codex_executable", return_value="/tmp/codex"),
            patch.object(ai_provider, "_run_codex_process", side_effect=[version, login]) as run,
        ):
            result = ai_provider.AIProvider.check_codex(model="gpt-5.6-luna")

        self.assertTrue(result["ok"])
        self.assertTrue(result["authenticated"])
        self.assertEqual(result["provider"], "codex")
        self.assertIn("ChatGPT", result["message"])
        self.assertIn("gpt-5.6-luna", result["models"])
        self.assertEqual(run.call_count, 2)

    def test_codex_status_rejects_api_key_login_to_avoid_separate_billing(self) -> None:
        version = subprocess.CompletedProcess(
            ["codex", "--version"],
            0,
            stdout="codex-cli 1.2.3\n",
            stderr="",
        )
        login = subprocess.CompletedProcess(
            ["codex", "login", "status"],
            0,
            stdout="Logged in using API key\n",
            stderr="",
        )
        with (
            patch.object(ai_provider, "_find_codex_executable", return_value="/tmp/codex"),
            patch.object(ai_provider, "_run_codex_process", side_effect=[version, login]),
        ):
            result = ai_provider.AIProvider.check_codex()

        self.assertFalse(result["ok"])
        self.assertTrue(result["authenticated"])
        self.assertEqual(result["code"], "codex_api_key_login")
        self.assertIn("included ChatGPT plan", result["message"])

    def test_codex_provider_uses_ephemeral_read_only_cli_run(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex", "exec"],
            0,
            stdout='{"ok": true}\n',
            stderr="",
        )
        with (
            patch.object(ai_provider, "_find_codex_executable", return_value="/tmp/codex"),
            patch.object(
                ai_provider.AIProvider,
                "check_codex",
                return_value={"ok": True, "message": "ready"},
            ),
            patch.object(ai_provider, "_run_codex_process", return_value=completed) as run,
        ):
            result = ai_provider.AIProvider.complete(
                prompt='Return {"ok": true}',
                provider="codex",
                model="gpt-5.6-luna",
                system_prompt="Return JSON only.",
            )

        self.assertEqual(result, '{"ok": true}')
        args = run.call_args.args[1]
        self.assertIn("exec", args)
        self.assertIn("--ephemeral", args)
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--ignore-rules", args)
        self.assertIn("read-only", args)
        self.assertIn("gpt-5.6-luna", args)
        self.assertIn("<scriptcut_task>", run.call_args.kwargs["input_text"])

    def test_codex_process_removes_ambient_openai_api_keys(self) -> None:
        completed = subprocess.CompletedProcess(["codex"], 0, stdout="ok", stderr="")
        with (
            patch.dict(
                ai_provider.os.environ,
                {
                    "OPENAI_API_KEY": "should-not-leak",
                    "CODEX_API_KEY": "should-not-leak",
                    "SCRIPTCUT_SAFE_TEST": "kept",
                },
                clear=False,
            ),
            patch.object(ai_provider.subprocess, "run", return_value=completed) as run,
        ):
            ai_provider._run_codex_process("/tmp/codex", ["--version"])

        environment = run.call_args.kwargs["env"]
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("CODEX_API_KEY", environment)
        self.assertEqual(environment["SCRIPTCUT_SAFE_TEST"], "kept")

    def test_cloud_provider_check_verifies_key_and_selected_model_without_completion(self) -> None:
        response = SimpleNamespace(
            ok=True,
            status_code=200,
            text="",
            json=lambda: {
                "object": "list",
                "data": [
                    {"id": "grok-4.5"},
                    {"id": "grok-4.3"},
                ],
            },
        )
        with patch.object(ai_provider.requests, "get", return_value=response) as request:
            result = ai_provider.AIProvider.check_cloud_provider(
                provider="xai",
                api_key="xai-test",
                model="grok-4.5",
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["authenticated"])
        self.assertTrue(result["model_available"])
        self.assertEqual(result["models"], ["grok-4.3", "grok-4.5"])
        self.assertEqual(request.call_args.args[0], "https://api.x.ai/v1/models")
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer xai-test")

    def test_cloud_provider_check_explains_rejected_xai_key(self) -> None:
        response = SimpleNamespace(
            ok=False,
            status_code=400,
            text="",
            json=lambda: {
                "code": "invalid-argument",
                "error": "Incorrect API key provided.",
            },
        )
        with patch.object(ai_provider.requests, "get", return_value=response):
            result = ai_provider.AIProvider.check_cloud_provider(
                provider="xai",
                api_key="xai-secret",
                model="grok-4.5",
            )

        self.assertFalse(result["ok"])
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["code"], "invalid_key")
        self.assertIn("did reach xAI", result["message"])
        self.assertNotIn("xai-secret", str(result))

    def test_completion_error_explains_openai_api_is_separate_from_chatgpt(self) -> None:
        error = SimpleNamespace(status_code=401)
        error.__str__ = lambda self: "Incorrect API key provided"
        message = ai_provider._friendly_completion_error(
            "openai",
            "OpenAI",
            RuntimeError("Incorrect API key provided"),
            "gpt-4o",
        )

        self.assertIn("ChatGPT subscription does not include OpenAI API usage", message)

    def test_clip_request_includes_shorts_platform_guidance(self) -> None:
        captured: dict[str, str] = {}

        def fake_complete(**kwargs):
            captured["prompt"] = kwargs["prompt"]
            return """
            {
              "clips": [
                {
                  "title": "Strong opener",
                  "startWordIndex": 0,
                  "endWordIndex": 1,
                  "startTime": 0,
                  "endTime": 31,
                  "reason": "Clear hook"
                }
              ]
            }
            """

        request = ai_router.ClipRequest(
            transcript="hello world",
            words=[
                ai_router.WordInfo(index=0, word="hello", start=0, end=0.5),
                ai_router.WordInfo(index=1, word="world", start=30.5, end=31),
            ],
            target_duration=60,
            platform="shorts",
            instruction="favor surprising hooks",
            min_duration=30,
            max_duration=90,
        )

        with patch.object(ai_provider.AIProvider, "complete", side_effect=fake_complete):
            result = ai_router.run_create_clip(request)

        self.assertEqual(len(result["clips"]), 1)
        self.assertIn("shorts", captured["prompt"])
        self.assertIn("30-90 seconds", captured["prompt"])
        self.assertIn("favor surprising hooks", captured["prompt"])

    def test_director_edit_plan_returns_clip_package(self) -> None:
        captured: dict[str, str] = {}

        def fake_complete(**kwargs):
            captured["prompt"] = kwargs["prompt"]
            return """
            {
              "summary": "Make a short from the strongest hook.",
              "suggestions": [
                {"action": "delete", "startWordIndex": 0, "endWordIndex": 0, "reason": "Slow start", "confidence": 0.9}
              ],
              "directorClip": {
                "title": "Best moment",
                "startWordIndex": 1,
                "endWordIndex": 2,
                "reason": "Strong payoff"
              },
              "directorPackage": {
                "hook": "This changed everything",
                "title": "Best moment",
                "caption": "Watch the shift",
                "description": "A concise social package",
                "hashtags": ["shorts", "#podcast"]
              },
              "directorNotes": ["Use creator captions"]
            }
            """

        request = ai_router.EditPlanRequest(
            instruction="make a 60 second short",
            transcript="well this changed everything",
            words=[
                ai_router.WordInfo(index=0, word="well", start=0, end=0.2),
                ai_router.WordInfo(index=1, word="this", start=0.2, end=0.5),
                ai_router.WordInfo(index=2, word="changed", start=0.5, end=1.0),
            ],
            mode="director",
            platform="shorts",
            target_duration=60,
        )

        with patch.object(ai_provider.AIProvider, "complete", side_effect=fake_complete):
            result = ai_router.run_edit_plan(request)

        self.assertIn("Target platform: shorts", captured["prompt"])
        self.assertIn("directorClip", captured["prompt"])
        self.assertEqual(result["directorClip"]["startTime"], 0.2)
        self.assertEqual(result["directorClip"]["endTime"], 1.0)
        self.assertEqual(result["directorPackage"]["hashtags"], ["shorts", "podcast"])
        self.assertEqual(result["directorNotes"], ["Use creator captions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
