from fastapi import APIRouter, HTTPException
from ..models.schemas import ToscaniniRequest, ToscaniniResponse
from ..services.toscanini_service import consultar_toscanini

router = APIRouter(prefix="/ia", tags=["Toscanini"])


@router.post("/toscanini", response_model=ToscaniniResponse)
async def toscanini_endpoint(request: ToscaniniRequest):
    if not request.historial:
        raise HTTPException(status_code=400, detail="El historial no puede estar vacío.")

    ultimo = request.historial[-1]
    if ultimo.rol != "usuario":
        raise HTTPException(status_code=400, detail="El último mensaje debe ser del usuario.")

    try:
        respuesta = await consultar_toscanini(
            [msg.model_dump() for msg in request.historial]
        )
        return ToscaniniResponse(respuesta=respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en Toscanini: {e}")
