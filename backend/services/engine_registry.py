import io
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException


@dataclass
class TTSRequest:
    text: str
    language: Optional[str] = None
    voice_id: Optional[str] = None
    ref_text: Optional[str] = None
    instruct: Optional[str] = None
    speed: float = 1.0
    seed: Optional[int] = None


class TTSEngine:
    id: str
    display_name: str
    description: str
    languages: list[str]

    def is_available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def is_loaded(self) -> bool:
        return False

    async def load(self):
        raise NotImplementedError

    async def unload(self):
        raise NotImplementedError

    async def generate(self, request: TTSRequest) -> tuple[bytes, int, dict]:
        raise NotImplementedError

    def info(self) -> dict:
        installed, reason = self.is_available()
        return {
            "id": self.id,
            "display_name": self.display_name,
            "description": self.description,
            "languages": self.languages,
            "installed": installed,
            "available": installed,
            "loaded": self.is_loaded(),
            "reason": reason,
        }


class OmniVoiceEngine(TTSEngine):
    id = "omnivoice"
    display_name = "OmniVoice"
    description = "Default multilingual zero-shot TTS and voice cloning engine."
    languages = ["vi", "en", "zh", "ja", "ko", "fr", "de", "es"]

    def is_available(self) -> tuple[bool, str]:
        try:
            import omnivoice  # noqa: F401
            return True, "Installed"
        except Exception as exc:
            return False, str(exc)

    def is_loaded(self) -> bool:
        import services.model_manager as mm
        return mm.model is not None

    async def load(self):
        from services.model_manager import get_model
        return await get_model()

    async def unload(self):
        import services.model_manager as mm
        async with mm._model_lock:
            if mm.model is not None:
                mm.model = None
                mm.free_vram()
                return True
        return False

    async def generate(self, request: TTSRequest) -> tuple[bytes, int, dict]:
        import asyncio
        import torchaudio

        from api.routers.generation import _run_inference
        from core.config import VOICES_DIR
        from core.db import get_db
        from services.model_manager import _gpu_pool, get_model

        model = await get_model()
        ref_audio_path = None
        ref_text = request.ref_text
        instruct = request.instruct
        used_seed = request.seed
        voice_id = request.voice_id

        if voice_id and voice_id != "default":
            conn = get_db()
            try:
                row = conn.execute("SELECT * FROM voice_profiles WHERE id=?", (voice_id,)).fetchone()
            finally:
                conn.close()
            if row:
                ref_audio_path = os.path.join(VOICES_DIR, row["locked_audio_path"] or row["ref_audio_path"] or "")
                ref_text = ref_text or row["ref_text"]
                instruct = instruct or row["instruct"]
                used_seed = used_seed if used_seed is not None else row["seed"]

        start = time.time()
        loop = asyncio.get_running_loop()
        audio_tensor = await loop.run_in_executor(
            _gpu_pool,
            _run_inference,
            model,
            request.text,
            None if request.language == "Auto" else request.language,
            ref_audio_path,
            ref_text,
            instruct,
            None,
            16,
            2.0,
            request.speed,
            None,
            True,
            True,
            None,
            None,
            None,
            used_seed,
        )

        sample_rate = getattr(model, "sampling_rate", 24000)
        buffer = io.BytesIO()
        torchaudio.save(buffer, audio_tensor, sample_rate, format="wav")
        wav_bytes = buffer.getvalue()
        duration = round(audio_tensor.shape[-1] / sample_rate, 2)
        return wav_bytes, sample_rate, {
            "duration": duration,
            "generation_time": round(time.time() - start, 2),
            "seed": used_seed,
        }


class PlaceholderEngine(TTSEngine):
    def __init__(self, engine_id: str, display_name: str, description: str, languages: list[str], package_name: str):
        self.id = engine_id
        self.display_name = display_name
        self.description = description
        self.languages = languages
        self.package_name = package_name

    def is_available(self) -> tuple[bool, str]:
        return False, f"Install runtime package for {self.package_name} in a later phase."

    async def load(self):
        raise HTTPException(status_code=501, detail=f"{self.display_name} runtime is not installed yet.")

    async def unload(self):
        return False

    async def generate(self, request: TTSRequest) -> tuple[bytes, int, dict]:
        raise HTTPException(status_code=501, detail=f"{self.display_name} runtime is not installed yet.")


_engines: dict[str, TTSEngine] = {
    "omnivoice": OmniVoiceEngine(),
    "kokoro": PlaceholderEngine(
        "kokoro",
        "Kokoro",
        "Lightweight fast TTS engine placeholder; runtime package to be selected.",
        ["en", "ja", "zh", "es", "fr"],
        "kokoro",
    ),
    "gwen": PlaceholderEngine(
        "gwen",
        "Gwen-TTS 0.6B",
        "Vietnamese-focused Qwen3-TTS voice cloning model placeholder.",
        ["vi", "en", "zh", "ja", "ko", "fr", "de", "it", "pt", "ru", "es"],
        "qwen-tts",
    ),
}

_default_engine = os.environ.get("OMNIVOICE_TTS_ENGINE", "omnivoice")


def list_engines() -> list[dict]:
    return [engine.info() for engine in _engines.values()]


def get_default_engine_id() -> str:
    return _default_engine if _default_engine in _engines else "omnivoice"


def set_default_engine(engine_id: str) -> dict:
    global _default_engine
    engine = get_engine(engine_id)
    available, reason = engine.is_available()
    if not available:
        raise HTTPException(status_code=400, detail=reason)
    _default_engine = engine_id
    os.environ["OMNIVOICE_TTS_ENGINE"] = engine_id
    return engine.info()


def get_engine(engine_id: str | None = None) -> TTSEngine:
    resolved = engine_id or get_default_engine_id()
    engine = _engines.get(resolved)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"Unknown TTS engine: {resolved}")
    return engine


def loaded_engine_ids() -> list[str]:
    return [engine.id for engine in _engines.values() if engine.is_loaded()]
