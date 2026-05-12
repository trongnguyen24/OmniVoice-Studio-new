import os
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.config import OUTPUTS_DIR
from services.engine_registry import (
    TTSRequest,
    get_default_engine_id,
    get_engine,
    list_engines,
    set_default_engine,
)

router = APIRouter(prefix="/api/ext", tags=["extension-tts"])


class ExtensionTTSRequest(BaseModel):
    engine: str | None = None
    text: str = Field(..., min_length=1, max_length=8000)
    language: str | None = "Auto"
    voice_id: str | None = "default"
    ref_text: str | None = None
    instruct: str | None = None
    speed: float = Field(1.0, ge=0.5, le=2.0)
    seed: int | None = None


class SelectEngineRequest(BaseModel):
    engine: str


@router.get("/engines")
def engines():
    return {
        "default_engine": get_default_engine_id(),
        "engines": list_engines(),
    }


@router.post("/engines/select")
def select_engine(payload: SelectEngineRequest):
    return {
        "default_engine": payload.engine,
        "engine": set_default_engine(payload.engine),
    }


@router.post("/engines/{engine_id}/preload")
async def preload_engine(engine_id: str):
    engine = get_engine(engine_id)
    await engine.load()
    return {"engine": engine.info()}


@router.post("/engines/{engine_id}/unload")
async def unload_engine(engine_id: str):
    engine = get_engine(engine_id)
    unloaded = await engine.unload()
    return {"engine": engine.info(), "unloaded": unloaded}


@router.post("/generate")
async def generate(payload: ExtensionTTSRequest):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required.")

    engine = get_engine(payload.engine)
    available, reason = engine.is_available()
    if not available:
        raise HTTPException(status_code=400, detail=reason)

    audio_id = str(uuid.uuid4())[:8]
    started = time.time()
    wav_bytes, _sample_rate, meta = await engine.generate(
        TTSRequest(
            text=text,
            language=payload.language,
            voice_id=payload.voice_id,
            ref_text=payload.ref_text,
            instruct=payload.instruct,
            speed=payload.speed,
            seed=payload.seed,
        )
    )

    filename = f"{audio_id}.wav"
    with open(os.path.join(OUTPUTS_DIR, filename), "wb") as handle:
        handle.write(wav_bytes)

    gen_time = meta.get("generation_time", round(time.time() - started, 2))
    duration = meta.get("duration", "")

    async def stream_wav():
        chunk_size = 16384
        for index in range(0, len(wav_bytes), chunk_size):
            yield wav_bytes[index:index + chunk_size]

    return StreamingResponse(
        stream_wav(),
        media_type="audio/wav",
        headers={
            "X-TTS-Engine": engine.id,
            "X-Gen-Time": str(gen_time),
            "X-Audio-Duration": str(duration),
            "X-Audio-Id": audio_id,
            "X-Audio-Path": filename,
            "Content-Length": str(len(wav_bytes)),
        },
    )
