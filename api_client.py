"""
api_client.py — Lê dados da planilha Google Sheets (aba UFAC) via CSV público.
Usa a URL publicada da planilha — sem OAuth, sem credenciais.
A aba UFAC já possui a fórmula =QUERY('Status Report Geral'!E1:ET; ...)
API Runrun.it é usada apenas para chat/comentários (opcional).
"""
import os
import logging
from typing import Optional
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL da planilha original — export CSV da aba UFAC (gid=28111961)
# Usa export direto em vez de pub (não expira)
SPREADSHEET_ID = "1Z-2zFKhuSHecdIRWyt6RLzKrE2dtpFomsmf7O4abj6k"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
    "/export?format=csv&gid=28111961"
)

# API Runrun.it
API_BASE = "https://secure.runrun.it/api/v1.0"
TOKEN = "oIbVXFCmN_JuACEi2R8MOGn-odhJ3uvt8-2XI7tcpUM"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ── Orçamento dos contratos (extraído das linhas do CSV) ──
# As linhas SALDO DO CONTRATO / 60/2024 / 61/2024 contêm:
#   ORÇAMENTO ANUAL DO CONTRATO → valores base
#   ORÇAMENTO COM ADITIVO 25%   → valores com aditivo
# Se falhar, usa fallback com os valores conhecidos

_FALLBACK_CONTRATOS = {
    "60/2024": {"orcamento": 1474672.84, "orcamento_aditivo": 1843341.05, "local": "Rio Branco"},
    "61/2024": {"orcamento": 299828.59, "orcamento_aditivo": 374785.74, "local": "Cruzeiro do Sul"},
}

CONTRATOS_CACHE = None

def carregar_contratos(csv_url=None) -> dict:
    """Lê orçamentos das colunas SALDO DO CONTRATO / 60/2024 / 61/2024 no CSV."""
    global CONTRATOS_CACHE
    if CONTRATOS_CACHE is not None:
        return CONTRATOS_CACHE

    try:
        url = csv_url or CSV_URL
        df = pd.read_csv(url, dtype=str, nrows=5, encoding='utf-8')

        contratos = {}
        for _, row in df.iterrows():
            rotulo = str(row.get("SALDO DO CONTRATO", "")).strip()
            if "ANUAL" in rotulo.upper():
                for ct_key, col_name in [("60/2024", "60/2024"), ("61/2024", "61/2024")]:
                    v = safe_float(row.get(col_name, ""))
                    if ct_key not in contratos:
                        contratos[ct_key] = {"local": "Rio Branco" if "60" in ct_key else "Cruzeiro do Sul"}
                    contratos[ct_key]["orcamento"] = v
            elif "ADITIVO" in rotulo.upper():
                for ct_key, col_name in [("60/2024", "60/2024"), ("61/2024", "61/2024")]:
                    v = safe_float(row.get(col_name, ""))
                    if ct_key not in contratos:
                        contratos[ct_key] = {"local": "Rio Branco" if "60" in ct_key else "Cruzeiro do Sul"}
                    contratos[ct_key]["orcamento_aditivo"] = v

        if len(contratos) == 2 and all("orcamento" in c and "orcamento_aditivo" in c for c in contratos.values()):
            CONTRATOS_CACHE = contratos
            return contratos
    except Exception as e:
        logger.warning(f"Falha ao ler orçamento do CSV: {e}")

    logger.info("Usando orçamentos fallback (hardcoded)")
    CONTRATOS_CACHE = _FALLBACK_CONTRATOS
    return _FALLBACK_CONTRATOS

# Mantém CONTRATOS como dict acessível (recarregado na primeira chamada)
def _init_contratos():
    return carregar_contratos()

CONTRATOS = _FALLBACK_CONTRATOS  # será substituído na primeira inicialização

def _ensure_contratos():
    global CONTRATOS
    if CONTRATOS is _FALLBACK_CONTRATOS:
        CONTRATOS = carregar_contratos()


def safe_float(v):
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "null", "-"):
        return 0.0
    s = s.replace("R$", "").replace(".", "").replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def safe_str(v):
    if v is None:
        return ""
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none", "null", "-") else ""


def detectar_contrato(row: dict) -> str:
    """Detecta contrato 60/2024 ou 61/2024 no titulo, contrato ou descricao."""
    campos = " ".join([
        safe_str(row.get("Contrato", "")),
        safe_str(row.get("Titulo", "")),
        safe_str(row.get("Descricao detalhada da solicitacao", ""))
    ])
    if "61/2024" in campos:
        return "61/2024"
    if "60/2024" in campos:
        return "60/2024"
    return ""


def parse_row(row: dict) -> Optional[dict]:
    """Converte uma linha da planilha em dict padronizado.
    Mantém todas as colunas originais do CSV para compatibilidade com dashboard."""
    task_id = safe_str(row.get("ID", ""))
    if not task_id or not task_id.isdigit():
        return None

    task_id = int(task_id)
    title = safe_str(row.get("Titulo", ""))
    estado = safe_str(row.get("Estado", ""))
    etapa = safe_str(row.get("Etapa", ""))
    close_date = safe_str(row.get("Data de entrega", ""))

    result = {
        "id": task_id,
        "title": title,
        "state": estado.lower(),
        "is_closed": close_date != "" or estado.upper() == "EXECUTADO" or "CONCLUÍDA" in etapa.upper(),
        "created_at": safe_str(row.get("Criada em", "")),
        "close_date": close_date,
        "desired_date": safe_str(row.get("Entrega desejada", "")),
        "estimated_delivery_date": safe_str(row.get("Entrega estimada", "")),
        "desired_start_date": "",
        "board_stage_name": etapa,
        "project_name": safe_str(row.get("Projeto", "")),
        "client_name": safe_str(row.get("Cliente", "")),
        "valor_total": safe_float(row.get("Valor total", "")),
        "valor_mao_obra": safe_float(row.get("Valor M.O", "")),
        "valor_material": safe_float(row.get("Valor M.A", "")),
        "local_servico": safe_str(row.get("Local do servico", "")),
        "contrato": detectar_contrato(row),
        "numero_sei": safe_str(row.get("N de referencia", "")),
        "orcamento_link": safe_str(row.get("Link do orcamento previo", "")),
        "campus": safe_str(row.get("Unidade solicitante", "")),
        "os_number": safe_str(row.get("Ordem de Servico", "")),
        "tags": [t.strip() for t in safe_str(row.get("Tags", "")).split(",") if t.strip()],
    }
    # Mantém colunas originais do CSV (ex: "Contrato", "Fiscal responsavel", "Local do servico")
    for k, v in row.items():
        k_clean = k.strip()
        if k_clean not in result:
            result[k_clean] = safe_str(v)
    return result


def buscar_todas_tarefas_ufac() -> list[dict]:
    """Carrega tarefas da aba UFAC via CSV público do Google Sheets.
    A aba UFAC já filtra via =QUERY(... WHERE H contains 'UFAC').
    """
    try:
        df = pd.read_csv(CSV_URL, dtype=str, encoding='utf-8')
    except Exception as e:
        logger.error(f"Erro ao baixar CSV da UFAC: {e}")
        return []

    if df.empty:
        logger.warning("CSV da UFAC vazio")
        return []

    logger.info(f"CSV UFAC: {len(df)} linhas, {len(df.columns)} colunas")
    tarefas = []
    ufac_ids = set()

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        task = parse_row(row_dict)
        if task is None:
            continue
        tid = task["id"]
        if tid in ufac_ids:
            continue
        ufac_ids.add(tid)
        tarefas.append(task)

    logger.info(f"Carregadas {len(tarefas)} tarefas UFAC ({len(ufac_ids)} únicas)")
    _ensure_contratos()
    return tarefas
