from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.diagrama_ia import router as diagrama_ia_router

app = FastAPI(
    title="Orquestia IA Services",
    description="Servicios de IA para Orquestia BPM Studio",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagrama_ia_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orquestia-ia-services"}
