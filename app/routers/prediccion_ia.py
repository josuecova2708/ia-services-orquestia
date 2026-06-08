"""Router de predicción de instancias (Deep Learning — Fase 5)."""

import asyncio

from fastapi import APIRouter, HTTPException

from ..models.schemas import PrediccionRequest, PrediccionResponse
from ..services import prediccion_service

router = APIRouter(prefix="/ia", tags=["Predicción"])


@router.post("/predecir-instancia", response_model=PrediccionResponse)
async def predecir_instancia(request: PrediccionRequest):
    try:
        return await asyncio.to_thread(prediccion_service.predecir, request)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la predicción: {e}")
