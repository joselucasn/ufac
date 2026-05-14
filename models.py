"""
models.py — Validação Pydantic para o Sistema de Gestão Contratual UFAC
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


class RunrunTask(BaseModel):
    """Modelo de tarefa vinda da API do Runrun.it"""
    id: int
    title: str
    state: str
    is_closed: bool
    created_at: Optional[str] = None  # ISO datetime string
    close_date: Optional[str] = None
    desired_date: Optional[str] = None
    estimated_delivery_date: Optional[str] = None
    desired_start_date: Optional[str] = None
    board_stage_name: Optional[str] = None
    project_name: Optional[str] = None
    client_name: Optional[str] = None

    # Custom fields mapeados
    valor_total: Optional[float] = Field(default=0.0)
    valor_mao_obra: Optional[float] = Field(default=0.0)
    valor_material: Optional[float] = Field(default=0.0)
    local_servico: Optional[str] = Field(default="")
    contrato: Optional[str] = Field(default="")  # "60/2024" ou "61/2024"
    numero_sei: Optional[str] = Field(default="")
    orcamento_link: Optional[str] = Field(default="")
    campus: Optional[str] = Field(default="")

    # Tags
    tags: list[str] = Field(default_factory=list)


class TaskResumo(BaseModel):
    """Resumo para exibição no dashboard"""
    id: int
    titulo_curto: str
    contrato: str
    local: str
    status_execucao: str  # "Executado" | "Em Andamento" | "Aguardando"
    sla: str  # "Em dia" | "Próximo do vencimento" | "Atrasado"
    data_conclusao: Optional[str] = None
    mes_medicao: Optional[str] = None  # MM/AAAA
    valor_total: float
    valor_mao_obra: float
    valor_material: float


class ChatMessage(BaseModel):
    """Mensagem do chat por O.S."""
    id: Optional[int] = None
    task_id: int
    autor_tipo: str  # "cliente" ou "interno"
    mensagem: str = Field(..., min_length=1, max_length=5000)
    timestamp: Optional[str] = None


class ContratoInfo(BaseModel):
    """Dados do contrato"""
    codigo: str
    orcamento_total: float
    orcamento_com_aditivo: float
    local: str


class MensagemInput(BaseModel):
    """Validação de input do chat"""
    task_id: int
    autor_tipo: str = Field(..., pattern="^(cliente|interno)$")
    mensagem: str = Field(..., min_length=1, max_length=5000)
