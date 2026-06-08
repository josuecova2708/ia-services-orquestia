from fastapi import APIRouter, HTTPException
from ..models.schemas import ComandoDiagramaRequest, ComandoDiagramaResponse
from ..services.comando_service import ejecutar_comando

router = APIRouter(prefix="/ia", tags=["Comandos"])


@router.post("/comando-diagrama", response_model=ComandoDiagramaResponse)
async def comando_diagrama_endpoint(request: ComandoDiagramaRequest):
    if not request.comando.strip():
        raise HTTPException(status_code=400, detail="El comando no puede estar vacío.")
    try:
        return await ejecutar_comando(request.comando, request.nodos, request.departamentos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al interpretar el comando: {e}")
