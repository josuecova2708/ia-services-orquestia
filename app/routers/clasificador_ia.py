from fastapi import APIRouter, HTTPException
from ..models.schemas import ClasificarTramiteRequest, ClasificarTramiteResponse
from ..services.clasificador_service import clasificar_tramite

router = APIRouter(prefix="/ia", tags=["Recepción"])


@router.post("/clasificar-tramite", response_model=ClasificarTramiteResponse)
async def clasificar_tramite_endpoint(request: ClasificarTramiteRequest):
    if not request.historial:
        raise HTTPException(status_code=400, detail="El historial no puede estar vacío.")

    ultimo = request.historial[-1]
    if ultimo.rol != "usuario":
        raise HTTPException(status_code=400, detail="El último mensaje debe ser del usuario.")

    try:
        return await clasificar_tramite(
            [msg.model_dump() for msg in request.historial],
            request.procesos,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Respuesta inesperada del modelo: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el agente de recepción: {e}")
