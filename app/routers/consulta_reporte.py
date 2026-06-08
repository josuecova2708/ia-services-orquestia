from fastapi import APIRouter, HTTPException
from ..models.schemas import ConsultaIaRequest, ConsultaReporteSpec
from ..services.consulta_reporte_service import interpretar_consulta

router = APIRouter(prefix="/ia", tags=["Consulta de Reportes"])


@router.post("/consulta-reporte", response_model=ConsultaReporteSpec)
async def consulta_reporte_endpoint(request: ConsultaIaRequest):
    if not request.pregunta or not request.pregunta.strip():
        raise HTTPException(status_code=400, detail="La consulta no puede estar vacía.")

    try:
        return await interpretar_consulta(
            request.pregunta.strip(),
            request.fecha_actual,
            request.procesos,
            request.funcionarios,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Respuesta inesperada del modelo: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al interpretar la consulta: {e}")
