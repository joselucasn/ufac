"""
transformer.py — Regras de negócio: medição, SLA, saldo contratual
"""
from datetime import datetime, date
from typing import Optional

from api_client import CONTRATOS


def inferir_status_execucao(task: dict) -> str:
    """
    Considera EXECUTADO se:
      - state == "closed" / is_closed == True
      - OU board_stage_name contém "FECHAMENTO DE MEDIÇÃO"
      - OU close_date preenchida
    """
    stage = task.get("board_stage_name", "").upper()
    if task.get("is_closed") or task.get("state") == "closed" or task.get("close_date"):
        return "Executado"
    if "FECHAMENTO DE MEDIÇÃO" in stage:
        return "Executado"
    if task.get("state") == "queued":
        return "Aguardando"
    return "Em Andamento"


def extrair_mes_medicao(close_date_str: Optional[str]) -> Optional[str]:
    """Converte close_date ISO para MM/AAAA"""
    if not close_date_str:
        return None
    try:
        dt = datetime.fromisoformat(close_date_str.replace("Z", ""))
        return dt.strftime("%m/%Y")
    except (ValueError, AttributeError):
        return None


def calcular_sla(task: dict) -> str:
    """
    SLA: "Em dia" | "Próximo do vencimento" | "Atrasado"
    - atraso: hoje > entrega estimada
    - alerta: prazo <= 2 dias
    """
    if task.get("is_closed") or task.get("state") == "closed":
        return "Em dia"

    hoje = date.today()
    desired = task.get("desired_date") or task.get("estimated_delivery_date") or task.get("desired_start_date")
    if not desired:
        return "Em dia"

    try:
        desired_date = datetime.fromisoformat(desired.replace("Z", "")).date()
        diff = (desired_date - hoje).days
        if diff < 0:
            return "Atrasado"
        elif diff <= 2:
            return "Próximo do vencimento"
        return "Em dia"
    except (ValueError, AttributeError):
        return "Em dia"


def calcular_saldos(tarefas: list[dict]) -> dict:
    """
    Calcula saldo contratual por contrato
    Retorna dict {contrato: {"orcamento": X, "executado": Y, "saldo": Z, "pct": N}}
    """
    resultados = {}
    for codigo, info in CONTRATOS.items():
        tasks_contrato = [t for t in tarefas if t.get("contrato") == codigo]
        executadas = [t for t in tasks_contrato if inferir_status_execucao(t) == "Executado"]
        total_executado = sum(t.get("valor_total", 0) for t in executadas)
        orcamento = info["orcamento"]
        saldo = orcamento - total_executado
        pct = (total_executado / orcamento * 100) if orcamento > 0 else 0
        resultados[codigo] = {
            "orcamento": orcamento,
            "orcamento_aditivo": info["orcamento_aditivo"],
            "executado": total_executado,
            "saldo": saldo,
            "pct": round(pct, 2),
            "local": info["local"],
            "qtd_total": len(tasks_contrato),
            "qtd_executadas": len(executadas),
            "qtd_abertas": len([t for t in tasks_contrato if inferir_status_execucao(t) != "Executado"]),
        }
    return resultados


def agrupar_medicoes(tarefas: list[dict]) -> list[dict]:
    """
    Agrupa tarefas executadas por mês de conclusão
    Retorna lista de {mes: "MM/AAAA", valor: float, qtd: int}
    """
    medicoes = {}
    for t in tarefas:
        if inferir_status_execucao(t) != "Executado":
            continue
        mes = extrair_mes_medicao(t.get("close_date"))
        if not mes:
            continue
        if mes not in medicoes:
            medicoes[mes] = {"mes": mes, "valor": 0.0, "qtd": 0, "contrato": t.get("contrato", "")}
        medicoes[mes]["valor"] += t.get("valor_total", 0)
        medicoes[mes]["qtd"] += 1
    return sorted(medicoes.values(), key=lambda x: x["mes"])


def gerar_resumo_tarefa(task: dict) -> dict:
    """Gera resumo de uma tarefa para o dashboard"""
    status = inferir_status_execucao(task)
    sla = calcular_sla(task)
    mes = extrair_mes_medicao(task.get("close_date"))

    # Título curto (primeiros 80 chars)
    titulo = task.get("title", "")
    titulo_curto = titulo[:80] + "..." if len(titulo) > 80 else titulo

    return {
        "id": task["id"],
        "titulo_curto": titulo_curto,
        "contrato": task.get("contrato", ""),
        "local": task.get("local_servico", ""),
        "status_execucao": status,
        "sla": sla,
        "data_conclusao": task.get("close_date", ""),
        "mes_medicao": mes,
        "valor_total": task.get("valor_total", 0.0),
        "valor_mao_obra": task.get("valor_mao_obra", 0.0),
        "valor_material": task.get("valor_material", 0.0),
        "board_stage_name": task.get("board_stage_name", ""),
        "campus": task.get("campus", ""),
        "numero_sei": task.get("numero_sei", ""),
        "orcamento_link": task.get("orcamento_link", ""),
        "tags": task.get("tags", []),
    }


def calcular_kpis(tarefas: list[dict]) -> dict:
    """KPIs globais do dashboard"""
    saldos = calcular_saldos(tarefas)
    total_orcamento = sum(s["orcamento"] for s in saldos.values())
    total_executado = sum(s["executado"] for s in saldos.values())
    total_abertas = sum(s["qtd_abertas"] for s in saldos.values())
    total_concluidas = sum(s["qtd_executadas"] for s in saldos.values())
    pct = (total_executado / total_orcamento * 100) if total_orcamento > 0 else 0

    return {
        "saldo_contratual": total_orcamento - total_executado,
        "total_executado": total_executado,
        "orcamento_total": total_orcamento,
        "pct_utilizado": round(pct, 2),
        "os_abertas": total_abertas,
        "os_concluidas": total_concluidas,
        "os_total": total_abertas + total_concluidas,
        "saldos": saldos,
        "medicoes": agrupar_medicoes(tarefas),
    }


def calcular_sla_os(os: dict) -> Optional[float]:
    """Calcula percentual do SLA baseado em entrega desejada vs hoje"""
    entrega_str = os.get("Entrega desejada", "")
    if not entrega_str or str(entrega_str).strip() in ["", "-", "#N/A"]:
        return None
    try:
        entrega_str = str(entrega_str).strip()[:10]
        entrega = datetime.strptime(entrega_str, "%Y-%m-%d").date()
        hoje = date.today()
        dias_total = 30  # prazo padrao 30 dias
        dias_restantes = (entrega - hoje).days
        if dias_restantes <= 0:
            return 100  # vencido
        pct = (1 - dias_restantes / dias_total) * 100
        return max(0, min(100, pct))
    except (ValueError, TypeError):
        return None


def formatar_moeda(valor) -> str:
    """Formata valor em reais"""
    if valor is None:
        return ""
    try:
        # J├í ├® num├®rico (int/float)? Converte direto
        if isinstance(valor, (int, float)):
            v = float(valor)
        elif isinstance(valor, str):
            # String no formato brasileiro: 1.234.567,89
            v = float(valor.replace(".", "").replace(",", "."))
        else:
            v = float(valor)
        if v == 0:
            return ""
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return ""


# ── MAPEAMENTO ETAPAS RUNRUN.IT → KANBAN ──────────────
# Board DEP. OBRAS E MANUT. (id: 569367) — 14 etapas
#
# Coluna Kanban    | Etapas do Runrun.it
# ─────────────────────────────────────────────────
# 📥 EM ABERTO     | EM ABERTO, PENDÊNCIAS
# 📋 ORÇAMENTO     | ELABORAR RELATÓRIO/ORÇAMENTO, ORÇAMENTO EM ANÁLISE DA FISCALIZAÇÃO
# 🔧 PARA EXECUÇÃO | PARA LEVANTAMENTO, PARA EXECUÇÃO
# ⚡ EM EXECUÇÃO   | ATRASADAS
# 🔍 APROVAÇÃO     | APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO
# 📄 CONFORMIDADE  | ELABORAR CONFORMIDADE, CONFORMIDADE EM ANÁLISE DA FISCALIZAÇÃO
# 💰 FECHAMENTO    | PARA PAGAMENTO, FINALIZADAS EM FECHAMENTO DE MEDIÇÃO
# ✅ CONCLUÍDA     | CONCLUÍDAS, ENCERRADAS

ETAPAS_RUNRUN = [
    "EM ABERTO",
    "PENDÊNCIAS",
    "ELABORAR RELATÓRIO/ORÇAMENTO",
    "ORÇAMENTO EM ANÁLISE DA FISCALIZAÇÃO",
    "PARA LEVANTAMENTO",
    "PARA EXECUÇÃO",
    "ATRASADAS",
    "APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO",
    "ELABORAR CONFORMIDADE",
    "CONFORMIDADE EM ANÁLISE DA FISCALIZAÇÃO",
    "PARA PAGAMENTO",
    "FINALIZADAS EM FECHAMENTO DE MEDIÇÃO",
    "CONCLUÍDAS",
    "ENCERRADAS",
]

KANBAN_COLUNAS = [
    "📥 EM ABERTO",
    "🔍 ORÇAMENTO",
    "🔧 PARA EXECUÇÃO",
    "🔴 ATRASADAS",
    "🔍 APROVAÇÃO",
    "📄 CONFORMIDADE",
    "💰 FECHAMENTO",
    "✅ CONCLUÍDAS",
]

# Mapa: etapa → coluna Kanban
MAPA_ETAPA_KANBAN = {
    # ── Em Aberto ──
    "EM ABERTO":                         "EM ABERTO",
    "PARA LEVANTAMENTO":                 "EM ABERTO",
    "INTEGRADO":                         "EM ABERTO",
    "CONFERÊNCIA/SEPARAÇÃO":             "EM ABERTO",
    "FATURAMENTO":                       "EM ABERTO",
    "EM ANDAMENTO - COTAÇÃO":            "EM ABERTO",
    "SOLICITAÇÕES CANCELADAS":           "EM ABERTO",
    "ENTREGA CONFIRMADA":                "EM ABERTO",
    "EM ANÁLISE DO CLIENTE":             "EM ABERTO",
    # ── Elaboração de Orçamento ou Conformidade ──
    "ELABORAR RELATÓRIO/ORÇAMENTO":      "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
    "ELABORAR CONFORMIDADE":             "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
    "PENDÊNCIAS":                        "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
    # ── Fiscalização ──
    "ORÇAMENTO EM ANÁLISE DA FISCALIZAÇÃO":      "FISCALIZAÇÃO",
    "CONFORMIDADE EM ANÁLISE DA FISCALIZAÇÃO":   "FISCALIZAÇÃO",
    # ── Aprovados Aguardando Liberação Fiscalização ──
    "APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO": "APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO",
    # ── Em Execução ──
    "PARA EXECUÇÃO":                     "EM EXECUÇÃO",
    "ATRASADAS":                         "EM EXECUÇÃO",
    "EM EXECUÇÃO":                       "EM EXECUÇÃO",
    # ── Finalizadas em Fechamento de Medição ──
    "FINALIZADAS EM FECHAMENTO DE MEDIÇÃO": "FINALIZADAS EM FECHAMENTO DE MEDIÇÃO",
    # ── Concluídas ──
    "CONCLUÍDAS":                        "CONCLUÍDAS",
    # ── Encerradas ──
    "ENCERRADAS":                        "ENCERRADAS",
    # Etapas extras que sobram (caem em categorias via fallback)
    "NÃO CONFORMIDADE":                   "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
    "CONFORMIDADE DEMANDANTE":            "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
    "CONFORMIDADE TÁCITA":               "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
}


def categorizar_status_kanban(os: dict) -> str:
    """Mapeia a etapa do Runrun.it para a coluna Kanban correta.
    Usa o campo 'Etapa' do CSV (que reflete o board_stage_name do Runrun.it)."""
    etapa_raw = str(os.get("Etapa", os.get("board_stage_name", ""))).strip().upper()

    # Remove acentos para comparação
    import unicodedata
    def normalize(s):
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').strip()

    etapa_norm = normalize(etapa_raw)

    # Tenta match exato
    for etapa_runrun, coluna in MAPA_ETAPA_KANBAN.items():
        etapa_runrun_norm = normalize(etapa_runrun)
        if etapa_norm == etapa_runrun_norm:
            return coluna

    # Match parcial (contém)
    for etapa_runrun, coluna in MAPA_ETAPA_KANBAN.items():
        etapa_runrun_norm = normalize(etapa_runrun)
        if etapa_runrun_norm in etapa_norm or etapa_norm in etapa_runrun_norm:
            return coluna

    # Fallback: detecta por palavras-chave
    if "CONFORMIDADE" in etapa_norm or "PENDÊNCIA" in etapa_norm or "PENDENCIA" in etapa_norm:
        return "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE"
    if "LIBERAÇÃO" in etapa_norm or "LIBERACAO" in etapa_norm:
        if "APROVADO" in etapa_norm or "APROVADA" in etapa_norm:
            return "APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO"
        return "FISCALIZAÇÃO"
    if "FISCALIZAÇÃO" in etapa_norm or "FISCALIZACAO" in etapa_norm:
        return "FISCALIZAÇÃO"
    if "ORÇAMENTO" in etapa_norm or "ORCAMENTO" in etapa_norm or "RELATÓRIO" in etapa_norm or "RELATORIO" in etapa_norm:
        return "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE"
    if "EXECUÇÃO" in etapa_norm or "EXECUCAO" in etapa_norm or "ATRASADA" in etapa_norm:
        return "EM EXECUÇÃO"
    if "LEVANTAMENTO" in etapa_norm:
        return "EM ABERTO"
    if "FECHAMENTO" in etapa_norm or "MEDIÇÃO" in etapa_norm or "MEDICAO" in etapa_norm:
        return "FINALIZADAS EM FECHAMENTO DE MEDIÇÃO"
    if "PAGAMENTO" in etapa_norm:
        return "FINALIZADAS EM FECHAMENTO DE MEDIÇÃO"
    if "CONCLUÍDA" in etapa_norm or "CONCLUIDA" in etapa_norm:
        return "CONCLUÍDAS"
    if "ENCERRADA" in etapa_norm:
        return "ENCERRADAS"
    if "ABERTO" in etapa_norm:
        return "EM ABERTO"

    # Default
    return "EM ABERTO"


def extrair_valor_total(os: dict) -> Optional[float]:
    """Extrai valor total da O.S. do CSV"""
    for chave in ["Valor total", "Valor Total"]:
        v = os.get(chave)
        if v and str(v).strip() not in ["", "-", "#N/A", "0"]:
            try:
                return float(str(v).replace(".", "").replace(",", "."))
            except:
                pass
    return None


def extrair_valor_mo(os: dict) -> Optional[float]:
    """Extrai valor de Mão de Obra"""
    for chave in ["Valor M.O", "Valor MO", "Mão de Obra"]:
        v = os.get(chave)
        if v and str(v).strip() not in ["", "-", "#N/A", "0"]:
            try:
                return float(str(v).replace(".", "").replace(",", "."))
            except:
                pass
    return None


def extrair_valor_ma(os: dict) -> Optional[float]:
    """Extrai valor de Material"""
    for chave in ["Valor M.A", "Valor MA", "Material"]:
        v = os.get(chave)
        if v and str(v).strip() not in ["", "-", "#N/A", "0"]:
            try:
                return float(str(v).replace(".", "").replace(",", "."))
            except:
                pass
    return None
