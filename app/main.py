from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.diagrama_ia import router as diagrama_ia_router
from .routers.toscanini import router as toscanini_router
from .routers.optimizar_ia import router as optimizar_ia_router
from .routers.voz_ia import router as voz_ia_router
from .routers.clasificador_ia import router as clasificador_ia_router
from .routers.comando_ia import router as comando_ia_router
from .routers.consulta_reporte import router as consulta_reporte_router
import os

app = FastAPI(
    title="Orquestia IA Services",
    description="Servicios de IA para Orquestia BPM Studio",
    version="0.1.0"
)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:4200,http://localhost:8080")
_origins = [o.strip() for o in _raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagrama_ia_router)
app.include_router(toscanini_router)
app.include_router(optimizar_ia_router)
app.include_router(voz_ia_router)
app.include_router(clasificador_ia_router)
app.include_router(comando_ia_router)
app.include_router(consulta_reporte_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orquestia-ia-services"}
