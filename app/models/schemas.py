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
    responsableCliente: bool = False
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


# ─── Toscanini Chatbot Schemas ────────────────────────────────────────────────

class ToscaniniMensaje(BaseModel):
    rol: Literal["usuario", "toscanini"]
    mensaje: str


class ToscaniniRequest(BaseModel):
    historial: List[ToscaniniMensaje]


class ToscaniniResponse(BaseModel):
    respuesta: str


# ─── Optimizar Diagrama Schemas ───────────────────────────────────────────────

class NodoOptimizar(BaseModel):
    id: str
    tipo: Literal['INICIO', 'FIN', 'ACTIVIDAD', 'GATEWAY_XOR', 'GATEWAY_AND']
    label: str
    posX: int
    posY: int
    departamentoId: Optional[str] = None
    responsableCliente: bool = False
    formulario: List[CampoFormulario] = []


class ConexionOptimizar(BaseModel):
    id: str
    origenId: str
    destinoId: str
    tipo: Literal['NORMAL', 'CONDICIONAL', 'RETORNO']
    label: Optional[str] = None
    condicion: Optional[str] = None
    esDefault: bool = False
    maxReintentos: Optional[int] = None


class OptimizarDiagramaRequest(BaseModel):
    nodos: List[dict]
    conexiones: List[dict]
    departamentos: List[DepartamentoInput] = []


class OptimizarDiagramaResponse(BaseModel):
    nodos: List[dict]
    conexiones: List[dict]
    cambios_realizados: List[str] = []


# ─── Voz Schemas ──────────────────────────────────────────────────────────────

class TranscripcionResponse(BaseModel):
    texto: str


# ─── Agente de Recepción (Clasificador de trámites) ───────────────────────────

class ProcesoDisponible(BaseModel):
    id: str
    nombre: str
    descripcion: str = ""


class ChatMensaje(BaseModel):
    rol: Literal["usuario", "agente"]
    mensaje: str


class OpcionProceso(BaseModel):
    id: str
    nombre: str


class ClasificarTramiteRequest(BaseModel):
    historial: List[ChatMensaje]
    procesos: List[ProcesoDisponible] = []


class ClasificarTramiteResponse(BaseModel):
    respuesta: str
    proceso_recomendado_id: Optional[str] = None
    requiere_aclaracion: bool = False
    opciones: List[OpcionProceso] = []


# ─── Comandos sobre el diagrama (lenguaje natural → acción) ────────────────────

class NodoComando(BaseModel):
    id: str
    label: str
    tipo: str
    departamentoId: Optional[str] = None
    responsableCliente: bool = False


class ComandoDiagramaRequest(BaseModel):
    comando: str
    nodos: List[NodoComando] = []
    departamentos: List[DepartamentoInput] = []


class AccionDiagrama(BaseModel):
    # asignar_departamento | renombrar | autoservicio | eliminar
    tipo: str
    nodoId: str
    departamentoId: Optional[str] = None
    nuevoLabel: Optional[str] = None
    valor: Optional[bool] = None


class ComandoDiagramaResponse(BaseModel):
    acciones: List[AccionDiagrama] = []
    mensaje: str = ""


# ─── Consulta de Reportes (lenguaje natural → especificación estructurada) ─────

class FuncionarioDisponible(BaseModel):
    id: str
    nombre: str


class ConsultaIaRequest(BaseModel):
    pregunta: str
    fecha_actual: str  # yyyy-MM-dd, para interpretar "junio", "esta semana", etc.
    procesos: List[ProcesoDisponible] = []
    funcionarios: List[FuncionarioDisponible] = []


class ConsultaReporteSpec(BaseModel):
    valido: bool = True
    mensaje: str = ""
    metrica: Optional[str] = None
    desde: Optional[str] = None
    hasta: Optional[str] = None
    estado: Optional[str] = None
    proceso_id: Optional[str] = None
    funcionario_id: Optional[str] = None
    limite: Optional[int] = None
    orden: str = "desc"
    formato: str = "pantalla"  # pantalla | pdf | excel
    titulo: Optional[str] = None
