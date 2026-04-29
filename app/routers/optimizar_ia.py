from fastapi import APIRouter, HTTPException
from ..models.schemas import OptimizarDiagramaRequest
from ..services.optimizar_service import optimizar_diagrama

router = APIRouter(prefix="/ia", tags=["IA"])


@router.post("/optimizar-diagrama")
async def optimizar_diagrama_endpoint(request: OptimizarDiagramaRequest):
    if not request.nodos:
        raise HTTPException(status_code=400, detail="El diagrama no tiene nodos para optimizar.")
    try:
        return await optimizar_diagrama(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Respuesta inesperada del modelo: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al optimizar diagrama: {e}")
