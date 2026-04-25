from fastapi import APIRouter, HTTPException
from ..models.schemas import GenerarDiagramaRequest, GenerarDiagramaResponse
from ..services.gemini_service import generar_diagrama

router = APIRouter(prefix="/ia", tags=["IA"])


@router.post("/generar-diagrama", response_model=GenerarDiagramaResponse)
async def generar_diagrama_endpoint(request: GenerarDiagramaRequest):
    if not request.descripcion.strip():
        raise HTTPException(status_code=400, detail="La descripción no puede estar vacía.")
    try:
        resultado = await generar_diagrama(request.descripcion, request.departamentos_existentes)
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Respuesta inesperada del modelo: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar diagrama: {e}")
