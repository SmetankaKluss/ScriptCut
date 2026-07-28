"""Audio processing endpoint (noise reduction / Studio Sound)."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.audio_cleaner import clean_audio, is_deepfilter_available
from services.waveform import generate_waveform

logger = logging.getLogger(__name__)
router = APIRouter()


class AudioCleanRequest(BaseModel):
    input_path: str
    output_path: Optional[str] = None


@router.post("/audio/clean")
async def clean_audio_endpoint(req: AudioCleanRequest):
    try:
        output = clean_audio(req.input_path, req.output_path or "")
        return {
            "status": "ok",
            "output_path": output,
            "engine": "deepfilternet" if is_deepfilter_available() else "ffmpeg_anlmdn",
        }
    except Exception as e:
        logger.error(f"Audio cleaning failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/capabilities")
async def audio_capabilities():
    return {
        "deepfilternet_available": is_deepfilter_available(),
    }


@router.get("/audio/waveform")
def audio_waveform(file_path: str, points: int = Query(default=4000, ge=256, le=10000)):
    """Return compact waveform peaks without loading the source media in the UI."""
    try:
        return generate_waveform(file_path, points)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {Path(file_path).name}")
    except Exception as error:
        logger.error("Waveform extraction failed: %s", error)
        raise HTTPException(status_code=422, detail=str(error))
