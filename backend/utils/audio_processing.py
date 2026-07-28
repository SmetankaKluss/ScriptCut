from pathlib import Path
import tempfile
import os
import logging
import subprocess

from utils.ffmpeg import find_ffmpeg, find_ffprobe

logger = logging.getLogger(__name__)

_temp_audio_files = []


def extract_audio(video_path: Path):
    """Extract compact 16 kHz mono PCM for engines that require a WAV input."""
    temp_dir = Path(tempfile.mkdtemp(prefix="scriptcut_audio_"))
    audio_path = temp_dir / f"{video_path.stem}_audio.wav"
    try:
        result = subprocess.run(
            [
                find_ffmpeg(),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-y",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=60 * 60,
            check=False,
        )
        if result.returncode != 0 or not audio_path.exists():
            detail = (result.stderr or "FFmpeg did not create an audio file").strip()
            raise RuntimeError(detail[-1000:])
        _temp_audio_files.append(str(audio_path))
        return audio_path
    except Exception as e:
        cleanup_temp_audio_file(audio_path)
        raise RuntimeError(f"Audio extraction failed: {e}")


def cleanup_temp_audio_file(audio_path: Path | str):
    """Remove one extracted audio file and its private temporary directory."""
    path = Path(audio_path)
    try:
        if path.exists():
            path.unlink()
        parent = path.parent
        if parent.name.startswith("scriptcut_audio_") and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except Exception as e:
        logger.warning(f"Could not remove temp audio file {path}: {e}")
    try:
        _temp_audio_files.remove(str(path))
    except ValueError:
        pass


def cleanup_temp_audio():
    """Remove all temporary audio files created during processing."""
    cleaned = 0
    for fpath in list(_temp_audio_files):
        try:
            if os.path.exists(fpath):
                cleaned += 1
            cleanup_temp_audio_file(fpath)
        except Exception as e:
            logger.warning(f"Could not remove temp file {fpath}: {e}")
    return cleaned


def get_video_duration(video_path: Path):
    """Get duration of a video/audio file in seconds."""
    try:
        result = subprocess.run(
            [
                find_ffprobe(),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None
