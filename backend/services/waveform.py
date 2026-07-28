"""Memory-bounded waveform extraction for long media files."""

from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import subprocess
import sys

from utils.ffmpeg import find_ffmpeg, find_ffprobe


def generate_waveform(file_path: str, points: int = 4000) -> dict:
    """Decode a low-rate mono stream and reduce it to a fixed number of peaks."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))

    point_count = max(256, min(int(points), 10000))
    duration = _probe_duration(path)
    sample_rate = _waveform_sample_rate(duration, point_count)
    result = subprocess.run(
        [
            find_ffmpeg(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "pipe:1",
        ],
        capture_output=True,
        timeout=10 * 60,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail[-1000:] or "FFmpeg could not decode the audio track")
    if not result.stdout:
        raise RuntimeError("The media file does not contain a decodable audio track")

    samples = array("h")
    samples.frombytes(result.stdout[: len(result.stdout) - (len(result.stdout) % 2)])
    if sys.byteorder != "little":
        samples.byteswap()
    peaks = _reduce_samples(samples, point_count)
    if not peaks:
        raise RuntimeError("The audio track did not contain waveform samples")

    return {
        "duration": duration,
        "sample_rate": sample_rate,
        "points": len(peaks),
        "peaks": peaks,
    }


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            find_ffprobe(),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "FFprobe could not read media duration").strip())
    try:
        duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("FFprobe returned an invalid media duration") from error
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("The media duration is unavailable")
    return duration


def _waveform_sample_rate(duration: float, points: int) -> int:
    return max(8, min(100, math.ceil(points / max(duration, 1))))


def _reduce_samples(samples: array, points: int) -> list[list[float]]:
    sample_count = len(samples)
    if sample_count == 0:
        return []
    bucket_count = min(max(1, points), sample_count)
    peaks: list[list[float]] = []
    for bucket in range(bucket_count):
        start = bucket * sample_count // bucket_count
        end = max(start + 1, (bucket + 1) * sample_count // bucket_count)
        chunk = samples[start:end]
        minimum = min(chunk) / 32768.0
        maximum = max(chunk) / 32768.0
        peaks.append([round(minimum, 4), round(maximum, 4)])
    return peaks
