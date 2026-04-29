from fastapi import APIRouter, UploadFile, File, HTTPException
from google.genai import types
from ..services.gemini_service import client, MODELO
from ..models.schemas import TranscripcionResponse
import asyncio

router = APIRouter(prefix="/ia", tags=["IA"])

_PROMPT_TRANSCRIPCION = (
    "Transcribe exactamente lo que dice el hablante en este audio, en español. "
    "Devuelve solo el texto transcrito, sin comillas, sin formato, sin explicaciones adicionales."
)


def _transcribir(audio_bytes: bytes, mime_type: str) -> str:
    response = client.models.generate_content(
        model=MODELO,
        contents=types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                types.Part(text=_PROMPT_TRANSCRIPCION),
            ]
        ),
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=512,
        )
    )
    return response.text.strip()


@router.post("/transcribir-audio", response_model=TranscripcionResponse)
async def transcribir_audio(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Archivo de audio vacío.")

    mime_type = audio.content_type or "audio/webm"
    try:
        texto = await asyncio.to_thread(_transcribir, audio_bytes, mime_type)
        return TranscripcionResponse(texto=texto)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al transcribir audio: {e}")
