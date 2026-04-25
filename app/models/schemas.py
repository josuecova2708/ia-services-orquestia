from pydantic import BaseModel
from typing import Optional, List, Literal


class DepartamentoInput(BaseModel):
    id: str
    nombre: str


class GenerarDiagramaRequest(BaseModel):
    descripcion: str
    departamentos_existentes: List[DepartamentoInput] = []


class CampoFormulario(BaseModel):
    nombre: str
    tipo: Literal['TEXTO', 'NUMERO', 'BOOLEANO', 'OPCIONES', 'FECHA', 'ARCHIVO']
    label: str
    requerido: bool
    opciones: List[str] = []


class NodoGenerado(BaseModel):
    id: str
    tipo: Literal['INICIO', 'FIN', 'ACTIVIDAD', 'GATEWAY_XOR', 'GATEWAY_AND']
    label: str
    posX: int
    posY: int
    departamentoId: Optional[str] = None
    formulario: List[CampoFormulario] = []


class ConexionGenerada(BaseModel):
    id: str
    origenId: str
    destinoId: str
    tipo: Literal['NORMAL', 'CONDICIONAL', 'RETORNO']
    label: Optional[str] = None
    condicion: Optional[str] = None
    esDefault: bool = False
    maxReintentos: Optional[int] = None


class DiagramaGenerado(BaseModel):
    nodos: List[NodoGenerado]
    conexiones: List[ConexionGenerada]
    departamentos_sugeridos: List[str] = []


class GenerarDiagramaResponse(BaseModel):
    nodos: List[NodoGenerado]
    conexiones: List[ConexionGenerada]
    departamentos_sugeridos: List[str]
