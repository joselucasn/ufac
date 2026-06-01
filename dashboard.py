"""
dashboard.py — Portal de Gestão Contratual UFAC (Vivace Engenharia)
Estratégia Híbrida: CSV (bulk) + Runrun.it API (pontual)
Foco: Ferramenta operacional de decisão com Kanban visual
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
import os, re, json
from urllib.parse import urlencode

from api_client import (
    buscar_todas_tarefas_ufac, CONTRATOS,
    API_BASE, HEADERS
)
from chat_repository import get_messages, add_message as add_chat_message
from transformer import (
    calcular_sla_os, formatar_moeda, categorizar_status_kanban,
    extrair_valor_total, extrair_valor_mo, extrair_valor_ma
)
from exportacao_fiscal import render_exportacao_fiscal


# ── Fuso Acre (UTC-5) ──
ACRE_TZ = timezone(timedelta(hours=-5))

def agora_ac():
    return datetime.now(ACRE_TZ)


# ── Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Gestão Contratual UFAC",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Constantes ──────────────────────────────────────────────
import os
from dotenv import load_dotenv
load_dotenv()  # carrega variáveis do .env

# Guest hash agora lido de variável de ambiente (não mais hardcoded)
GUEST_HASH = os.getenv("RUNRUN_GUEST_HASH", "")
if not GUEST_HASH:
    raise RuntimeError("RUNRUN_GUEST_HASH não definido no .env — veja .env.example")

# ── Gate de autenticação ────────────────────────────────────
# Bloqueia acesso ao dashboard se o usuário não estiver logado.
# O menu de perfil, troca de senha e painel admin ficam na sidebar.
import auth  # noqa: E402
if not auth.require_auth(render_login_if_needed=True, render_dashboard_fn=None):
    st.stop()

# ── Estilos customizados ────────────────────────────────────
st.markdown("""
<style>
    .os-card {
        background: #1e1e1e;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        font-size: 13px;
    }
    .os-card:hover {
        border-color: #4a90d9;
    }
    .os-id {
        color: #4a90d9;
        font-weight: bold;
        font-size: 14px;
    }
    .os-local {
        color: #ccc;
        font-size: 13px;
        margin: 4px 0;
    }
    .os-valor {
        color: #7ecb7e;
        font-weight: 600;
    }
    .os-prazo {
        color: #e6a817;
        font-size: 12px;
    }
    .os-status {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 10px;
        display: inline-block;
    }
    .sla-verde { background: #1a3a1a; color: #7ecb7e; }
    .sla-amarelo { background: #3a3a1a; color: #e6c017; }
    .sla-vermelho { background: #3a1a1a; color: #e65c5c; }
    .kanban-scroll {
        overflow-x: auto !important;
        overflow-y: hidden;
        padding-bottom: 12px;
        scroll-behavior: smooth;
        width: 100%;
    }
    .kanban-scroll::-webkit-scrollbar {
        height: 8px;
    }
    .kanban-scroll::-webkit-scrollbar-thumb {
        background: #4a90d9;
        border-radius: 4px;
    }
    .kanban-scroll::-webkit-scrollbar-track {
        background: #1a1a2e;
        border-radius: 4px;
    }
    .kanban-scroll .row-widget.stHorizontal {
        flex-wrap: nowrap !important;
        overflow-x: visible !important;
    }
    .kanban-scroll .row-widget.stHorizontal > div {
        min-width: 260px !important;
        flex-shrink: 0 !important;
    }
    .kanban-column {
        background: #1a1a2e;
        border: 1px solid #2a2a4e;
        border-radius: 10px;
        padding: 8px;
        overflow-y: auto;
        max-height: 72vh;
    }
    .kanban-column::-webkit-scrollbar {
        width: 6px;
    }
    .kanban-column::-webkit-scrollbar-thumb {
        background: #4a90d9;
        border-radius: 3px;
    }
    .kanban-column::-webkit-scrollbar-track {
        background: #12122a;
        border-radius: 3px;
    }
    .kanban-title {
        font-weight: 700;
        font-size: 12px;
        padding: 8px;
        border-bottom: 2px solid #4a90d9;
        margin-bottom: 6px;
        text-align: center;
        position: sticky;
        top: 0;
        background: #1a1a2e;
        z-index: 1;
        color: #e0e0e0;
        letter-spacing: 0.3px;
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        margin-right: 4px;
    }
    .badge-azul { background: #1a3a5c; color: #6ab0e6; }
    .badge-verde { background: #1a3a1a; color: #7ecb7e; }
    .badge-laranja { background: #3a2a1a; color: #e6a817; }
    div[data-testid="stMetric"] {
        background: #1e1e2e;
        border: 1px solid #2a2a3e;
        border-radius: 8px;
        padding: 12px;
    }

    /* ── Kanban compacto ── */
    .kanban-column {
        padding: 6px !important;
    }
    .kanban-title {
        padding: 6px !important;
        font-size: 0.65rem !important;
    }
    div.streamlit-expanderContent {
        padding: 0.3rem 0.5rem !important;
    }
    div.streamlit-expanderContent > div {
        margin-bottom: 0.1rem !important;
    }
    div.streamlit-expanderHeader {
        padding: 0.25rem 0.5rem !important;
        font-size: 0.75rem !important;
    }
    /* Botão Atualizar — cinza neutro */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #94a3b8 !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: #334155 !important;
        color: #e2e8f0 !important;
    }

/* Botões header 50% cada */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > a.st-emotion-cache-g0jf5p,
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > button.st-emotion-cache-1j9n2s6 {
    width: 100% !important;
    min-width: 0 !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="column"] .stLinkButton {
    width: 100% !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="column"] .stLinkButton a {
    width: 100% !important;
    max-width: none !important;
}

/* Badge circular de contagem */
.badge-count {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 1.2rem !important;
    height: 1.2rem !important;
    border-radius: 50% !important;
    background: #334155 !important;
    color: #f1f5f9 !important;
    font-size: 0.6rem !important;
    font-weight: 700 !important;
    padding: 0 3px !important;
    line-height: 1 !important;
}

/* Cards Kanban compactos */
.kanban-column .stExpander,
.kanban-column div[data-testid="stExpander"] {
    padding: 0.1rem !important;
    margin: 0 0 2px 0 !important;
}

/* ── Botões header clonam estilo do "Atualizar" sidebar ── */
div[data-testid="stHorizontalBlock"] a.st-emotion-cache-g0jf5p,
.stLinkButton a.st-emotion-cache-g0jf5p {
    width: auto !important;
    max-width: none !important;
    min-width: 180px !important;
    padding: 0.3rem 1rem !important;
    background: #1e3a5f !important;
    border: 1px solid #3b82f6 !important;
    border-radius: 0.375rem !important;
    color: #f1f5f9 !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    box-shadow: none !important;
    text-align: center !important;
    display: inline-block !important;
    margin: 0 auto !important;
}
</style>
""", unsafe_allow_html=True)

# ── State ───────────────────────────────────────────────────
if "tarefas" not in st.session_state:
    st.session_state.tarefas = buscar_todas_tarefas_ufac()

# ── Funções auxiliares ──────────────────────────────────────

def cor_sla(percentual: Optional[float]) -> str:
    """Retorna classe CSS baseada no SLA"""
    if percentual is None:
        return "sla-verde"
    if percentual <= 50:
        return "sla-verde"
    elif percentual <= 80:
        return "sla-amarelo"
    return "sla-vermelho"

def rotulo_sla(percentual: Optional[float]) -> str:
    """Retorna string do SLA"""
    if percentual is None:
        return "✓ OK"
    if percentual <= 50:
        return f"✓ {percentual:.0f}%"
    elif percentual <= 80:
        return f"⚡ {percentual:.0f}%"
    return f"🔴 {percentual:.0f}%"

def icone_status(os: dict) -> str:
    """Ícone para o status da O.S."""
    estado = str(os.get("Estado", "")).strip().upper()
    if estado == "CONCLUÍDA":
        return "✅"
    elif estado == "FECHADA":
        return "✅"
    elif estado == "CANCELADA":
        return "❌"
    elif os.get("Reaberta?") and str(os.get("Reaberta?")).strip().upper() == "SIM":
        return "🔄"
    return "🔧"

from datetime import datetime, timezone

def _is_overdue(os: dict) -> bool:
    """Retorna True se a O.S. está atrasada: Estado=ATRASADAS ou data vencida em etapas abertas"""
    estado = str(os.get("Estado", "")).strip().upper()
    if estado == "ATRASADAS":
        return True
    # Só verificar data em etapas abertas (não concluídas/encerradas/fechadas)
    if estado in ("CONCLUÍDAS", "ENCERRADAS", "FECHADA", "CANCELADA"):
        return False
    dt_str = str(os.get("Entrega desejada", "")).strip()[:10]
    if not dt_str or dt_str in ("", "-", "N/A"):
        return False
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        hoje = agora_ac().date()
        return dt < hoje
    except ValueError:
        return False


def kpi_conformidade(contrato, quantidade):
    if quantidade == 0:
        cor, icone, msg, borda = "#22c55e", "✅", "Em conformidade", "#22c55e"
    elif quantidade <= 10:
        cor, icone, msg, borda = "#f59e0b", "⚠️", "Revisar com o fiscal", "#f59e0b"
    else:
        cor, icone, msg, borda = "#ef4444", "🔴", "Ação urgente necessária", "#ef4444"
    st.markdown(f"""
    <div style="background:#1e293b; border-radius:10px; border:1px solid #334155; border-left:4px solid {borda}; padding:14px 16px;">
      <p style="font-size:0.68rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.06em; margin:0 0 5px 0;">
        {icone} Falhando Conformidade &mdash; {contrato}
      </p>
      <p style="font-size:1.8rem; font-weight:800; color:{cor}; margin:0 0 4px 0; line-height:1;">
        {quantidade}
      </p>
      <p style="font-size:0.72rem; color:#6b7280; margin:0;">
        {msg}
      </p>
    </div>
    """, unsafe_allow_html=True)



def calcular_sla_br(data_prevista_raw):
    if data_prevista_raw is None or str(data_prevista_raw).strip() in ("", "-", "N/A"):
        return "#475569", "Sem prazo", "#475569"
    try:
        raw = str(data_prevista_raw).strip()[:10]
        if len(raw) < 10:
            return "#475569", "Sem prazo", "#475569"
        data = datetime.strptime(raw, "%Y-%m-%d").date()
    except:
        return "#475569", "Sem prazo", "#475569"
    dias = (data - agora_ac().date()).days
    if dias < 0:
        return "#ef4444", f"{abs(dias)}d atrasada", "#ef4444"
    elif dias == 0:
        return "#ef4444", "Vence hoje", "#ef4444"
    elif dias <= 7:
        return "#f59e0b", f"{dias}d restantes", "#f59e0b"
    else:
        return "#22c55e", f"{dias}d restantes", "#22c55e"

def card_kanban(numero_os, contrato, local, data_prevista, status=None):
    cor_sla, texto_sla, cor_borda = calcular_sla_br(data_prevista)
    estado_up = str(status).strip().upper() if status else ""
    if any(c in estado_up for c in ["CONCLUIDA", "CONCLUÍDA", "ENCERRADA", "FECHADA"]):
        cor_sla, texto_sla, cor_borda = "#22c55e", "Concluída", "#22c55e"
    local_display = str(local) if local else "Local não informado"
    if len(local_display) > 30:
        local_display = local_display[:30] + "..."
    num_display = str(int(numero_os)) if numero_os else "?"
    st.markdown(f"""
    <div style="background:#1e293b; border-radius:8px; border:1px solid #334155; border-left:4px solid {cor_borda}; padding:10px 12px; margin-bottom:8px;">
      <p style="font-size:0.7rem; font-weight:600; color:#64748b; margin:0 0 3px 0; line-height:1.2; letter-spacing:0.02em;">
        #{num_display} &middot; {contrato}
      </p>
      <p style="font-size:0.8rem; font-weight:700; color:#e2e8f0; margin:0 0 8px 0; line-height:1.3; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
        {local_display}
      </p>
      <p style="font-size:0.72rem; font-weight:600; color:{cor_sla}; margin:0; display:flex; align-items:center; gap:5px; line-height:1;">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:{cor_sla}; flex-shrink:0;"></span>
        {texto_sla}
      </p>
    </div>
    """, unsafe_allow_html=True)

def render_os_card(os: dict):
    """Card Kanban com expander: mostra min card + detalhes + links ao clicar"""
    os_id = os.get("ID", "")
    titulo = str(os.get("Titulo", ""))[:60]
    local = str(os.get("Local do servico", ""))[:50]
    estado = str(os.get("Estado", "")).strip()
    etapa = str(os.get("Etapa", "")).strip()
    valor = extrair_valor_total(os)
    responsavel = str(os.get("Fiscal responsavel", ""))[:25]
    data_entrega = str(os.get("Entrega desejada", "")).strip()[:10]
    contrato = str(os.get("Contrato", "")).strip()
    solicitante = str(os.get("Solicitante", ""))[:20]
    setor = str(os.get("Setor responsavel", ""))[:20]
    abrangencia = str(os.get("Abrangencia", ""))[:15]
    despesa = str(os.get("Tipo de despesa", ""))[:15]
    parecer = str(os.get("Parecer/complemento", ""))[:30]
    permissoes = str(os.get("Permissoes de sistema", ""))[:20]
    lancado = str(os.get("Lancado no Omie?", ""))[:5]
    processo = str(os.get("Processo concluido?", ""))[:5]

    atrasada = _is_overdue(os)
    guest_url = f"https://{GUEST_HASH}-share.runrun.it/pt-BR/guest/tasks/{os_id}"

    # Card visível (fora do expander) — sempre aparece
    card_kanban(os_id, contrato, local, data_entrega, estado)

    label = f"#{os_id} — {titulo[:25]}"
    if atrasada:
        label = f"🔴 {label}"
    with st.expander(label, expanded=False):
        st.divider()

        # ── Links documentos ──
        link_sit = str(os.get("Link do relatorio situacional", "")).strip()
        link_fin = str(os.get("Link do relatorio final", "")).strip()
        link_orcp = str(os.get("Link do orcamento previo", "")).strip()
        link_orcf = str(os.get("Link do orcamento final", "")).strip()

        docs = []
        for lbl, url, ico in [
            ("Relat. Situacional", link_sit, "📋"),
            ("Relat. Final", link_fin, "✅"),
            ("Orç. Prévio", link_orcp, "💰"),
            ("Orç. Final", link_orcf, "📊"),
        ]:
            if url and url not in ("", "-", "#N/A"):
                docs.append(f"[{ico} {lbl}]({url})")

        if docs:
            st.markdown("**📎 Documentos**")
            for d in docs:
                st.markdown(d)

        # ── Info grid ──
        info_items = [
            ("📋 Etapa", etapa or "—"),
            ("🏢 Local", local or "—"),
            ("👤 Fiscal", responsavel or "—"),
        ]
        if solicitante: info_items.append(("👤 Solicitante", solicitante))
        if setor: info_items.append(("🏢 Setor", setor))
        if abrangencia: info_items.append(("📍 Abrangência", abrangencia))
        if despesa: info_items.append(("💳 Despesa", despesa))
        if parecer: info_items.append(("📝 Parecer", parecer))
        if permissoes: info_items.append(("🔐 Permissões", permissoes))
        if lancado and lancado.upper() not in ('','NÃO','NAO'): info_items.append(("📊 Omie", lancado))
        if processo and processo.upper() not in ('','NÃO','NAO'): info_items.append(("✅ Proc.Concluído", processo))

        for lbl, val in info_items:
            st.markdown(f"{lbl}: **{val}**")

        # Link guest
        st.link_button("🔗 Abrir no Runrun.it (guest)", guest_url, use_container_width=True)

# ── SIDEBAR — Filtros ──────────────────────────────────────

st.sidebar.markdown('<div style="display:flex;justify-content:center;margin:0 0 8px 0;"><img src="data:image/png;base64,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s06/7tBzT5ty5LlnXHv85LPORfurE77zy+v2G3faxMsOPfesa3GtHj75vOuOPO884ePca48+99xrjzrv3ClHynl2lFyvh8k1jTy4rg3OP/f6QwApg/ChF54nx/XcKXCzcw4ujo85TnLeHXXeWdcdNuGUy/713HObLQ/P/3rqqY0OmXDSTw4/64zrDzpj0vVHfuXC6w877xw5l8+77ii51xx17rlTgCPFPUzGYPotfT30wsnXA4d9ZfINmQv/Zy86/5dwAfiruOCGz15URRZ/2IWTO/MhDkA9GQ674LzrMP5OyHWI8cu5ee3h8Ms5ePSFF14z7pyzrj30zNOmHCXhI06fdPzdM2YEy8PHylB2qtbej3/967rPXXju9p858YQTDz5zwv87bPI5l4095/RrgIPF7ZgfrgUfMk90dYWfzng51yTdzCHjwGlHGHE94VBJr0V2zHHccV4cKucAYM7TbnlRbpy0nQHhLB/icO4CYy8855qxF5xzrcH551yDNOO/4Jxrx03uANqR+k378J8r8eecfZXce34g951zjjznjL0umjKl6UWtfbnPcX+P2xcuOHPUEWef/vNDzj7tynHnn33VQZPPvvKA8865aqxg3LnnXi3tXXOYnFtyj7tm7HlnXjP2fDkGk0+/FuMA0Heg1o+wmVukz4u5558jdQiyNLmfZvfVbOy498vx67wPo+7uQJ4sP9yxUk8XZO304CL/oZNl/gCv4mb+6jGW+47EZbz37p5zHc4H3BeAo87Fva4DUu/h551zzbjTJl190Ekn/uKSyy9vzI6PeuntN9Z5+H/PTnzxjdfPePGtN0575vWZk56c8fLEZ2ZOn/j8m69NmDpz2sSnZ06f8NTs6ROmvjbt1KdmVwH/1FkzTzGQuKdnSfzM6ac8PXPaPvHfpgAAEABJREFUyVOBGa+eJO5JL7715smPT3/l1KdmzJjw0ltvTfzf67MvOOWM8/bJOrA6uDc98EDuupt/ddirb7125itvvjXpmRkzJj707LMTX3n7nQnPzBR+ZwtmTJv09KzpE6fOnC7uDIOnTFzV/8zsmRMzCNeTnpG8wGPTXpnw3Ouvnfq/t9449elZMyc8/tIrp0595ZVT31ww//gRG4wc8i3m9EEi9eobs3d66b13Jzzy0gunPPbKqye/8PYbpzz60kunTpXj+sxr06XuGZOenTVj0nOzZxo8/9qsSc8KsjDcZ1+bObErZk2UNidOnTV9wlPS9tNynjwhx/rpGdNPlfwT3/rwgw1xfJ8m4udnTttW+jVxxvvvTHr+jdcmPfbqixMfn/7yhGdmTz/1mVkzJjwtHDwze4bUP2uSjBNtn/bsa7M6IXHGL3lPf/q1GadJXsk3fdIzM2dMfG7mjAnPTp824Zlp006dKm0//cq0Cc+++urEZ1955byv/OhH69Eg3mqHdtujj+Zv+tPvj58x992zHxd+n5iO4zvt1CdnT5uAc+upWdMnyvk14amZMyY+OXOanC+vgvdTp856tYqZ006ZCnSEn5r+6oRnXps54dnZMyc8M3v6pOdemynHZwaOzaTnXp896fnXXz/1qRdfOvWVmbMOCqOorrYvy+o/7aILD5B70PlPTH/5lBfffeOUx6a/dMrTb8w6Ff18YuY06d90jMHg2VnTJzwza5r0f/opU2dMO+WpmdNOeXLGtJMzF/7Hp796EtynZk4/+YkZ0056cuZ0wbSTn5xZxVMzq/FPzZp20lMS1xWvSp0dkPMT53cn5BwVHidNFffpWXLuyTXz5MsvTHrl9dcmvvzG6xMef+H5SS/NnHlm9P775txfVh4+7vwPaO3e8dhjG257yAGHHrHfHtf+7FfXPfufZ6ZOfWP+vBunz5nz7WdmTD/3hTfemDTtvfcmvfS23Mtmz5w4dZZA3Kdnz5r49GuzOsNTJc5A0p+aPWPCUzNnTJj62vRThb9Ts7D4J9TiabmHAE/Nnl6dc+RYTxU8/dr0CVM7zsups6ef+vTsaTh3JW7aqU9K+lOovwZPy7EB5L4xceprMyc8/fqMU+Ei/Iycu8Bzs2dPehZ9Bl6bJcd05kSEn5H+Pv3aTBmLAP2QPqEPwNOzZ0x8etb00+V8+aq0+/OHn/vfg3+/754ZY/fe+/Y9jvv88b99+OGNwOGyHscnn39p3Rdfn33mK+++I/Pwm6dPnTXjjKdmvXr6U6/NOH3q69NPe+a1mZOk/5OeeX2W3PdmSb9nT3rmtdnSl5kyV8ychPsg8PSsRX6En31dxtQTJN+zQJYm45e6cY+d9KwcQ+C52bMmTZ0547QMpm6Je6YGz8r5/4xwkuFZ6af4J2V4bnZ1PunJlbwT5dhPfBIcz5re6X9Sru0sDm5vmDpr+oRnZspcI/f8Z2dMn2AwfdqE5+R4Ac/MmCFxMya9+vZbp8167+2zX3hzVuc1qQ4ee+g/VS5oDokpcRSpIE+hHLVQwrGrKGaHKkwUkaIIrnIoVkyhuKG4ZVksKxsXcYrKEq4ouEwViV8YhxS7juRHOlM5TakU632lidVmb2gINoxd3rktjp33W1vIbawXNFBLElEk3EQOU+y4BDcSXmvdkJVwR5S5XdIlbyzpZWGyrIlS36OgoYFCOXbNC1vn54P6/0oS0YMPUirHrxRF5NXVEQc5ak8TiuQ4RT20G8txj6Tu2n70GJbyietSWc4LIHYcSgROEFAsfYhSrdH+TkTxAQce/BdynailXJE8TG59nZwXnkDKeAIXfiV9cnofr8MmPesXzkGMOfJcCqUfoafEVVRxFJWkT6VUN5aV3hN9WB0QRdF6cj5s+mFbq/KaGin0XeGCBQ6V5DyryLEBwB9c8GeubeE1O7+6uxU5jhXW1D0e5wPuAyqf14IXEua3+ssxvilHSu1fkXOU83n6sL1djp+m5jCkspyLFTmeZTnXANxbsv5Hco6GzHJ/YorIkfNGUcxujy7SK5I3c7N8kbRZkXOl1g3lvhUz6mOpV0n91Kurpb8V4W9BpWSu5zQXyDWttvzz/fdt0l8+Pq5yl/3mN+vc8LWLzjnnGxfd0ByntyS5uhO5oWFTgdMu3M0rlag1SSjxfOHYodYopkjOqVjOrcj1zbUcOp6kyzEQF/EI9+XivhfL8U2US4kc48jcj5TUK2GJj+QYx3I8QnEjhDvSY8mPvLG0Hwmy45koT8o6UlfVjeS8qEjf4YZSP/JlYbihqUcR6oslvRp2ZHyunEsSL+PAPS0SF/dqky7jjSUcisuNdfx+e+uIuD532GsfvH/dxT/83i+nfO2iUy6/5ZbGZTmOeblvK8fjNjnnW6OK4dCpa6BI+oc2DWT86GcibpUXhzD+KrwOf1cX5SMZV19u9/LIj/F1j8e9vnt8ZI4LSz8dwnWJcCzXbCzHCS7CWfxirpSttuGY4wU/jt/SuuZ44L5v4Mi9H/DkfqeoJO1XpB8V4arICZVIU7kSNmXHRO1zwAGzfOVPo5hIhymxVuTIHz51QiasJA7x3UFy00iYKJETqwolflcAV1Eqk3IicGSiJRlkGCeUL9RTsVze98sXXzyEVpOtXCx/InHcTbTn0fB11qYPW1oIB4PkBqKFw+681oaFROoNWjMpuTB8P0eO3PDTKKU4jMmXi3+TDTaevsOZZ86gjk2lOKIOldpKlMaa6uSiQlmdygGsAY55LXprG/Fon2WCIDlPlCZylCIl7TmsyEk06UjukhJmZn3Q/oe8lHfz7+kolTwOedJHSlJypd+S25xnqLM7+uoLuMNFghsfTnAIoEREUCoTfoKboaMaHnni8U9PmTrVk24M+v2GG6/frFyubF4Qcdsq4kGJmMT1B6RyTOBmQBj8kRwNnG84BgD8APwA+Mf5kgHhzmMk9wU3H5TKafjkITvtNK+/BJ93yc+bpD/7+b5PbeUyrbHm2pTK8cN9A/2VNGlSEfwZOvvODuEPfe3u4tzCWLrHZ+HsvtYfVzpEqWZqLhYpleuacznSgU9OPqCWsNzwn4cfGi2CzukvJx9lOVwfh50xcf+rf3fL7/77wnOXxPlgnxadNLakMS+UL2cyQiNqVCFPXi5PoVy3YZRQ4Oelm4rA8ZKg5CgBveVTci51R295EY+8cAH4UbcjbWThzMVxYrm/IQw3C2cuyiINLoA8GUwe6RfSgdow2lJy75UvtDLJEpXkywE11OVbwtJnpr70/A9+efvvp/zgl7/cSM4BFpKWuLtxRHI/5EAm7JyISJJ229tLZO6xnf13iVNH5gOHVAq/QPKhb0sDknqWBqgrywd/BsRl/p5cpC8reqpnaePAUSr3tVDEDUQtgHkAbiRx8Jc5NeeuK1+0c431a2YHQqlK5f2wte0531UpIhOdSt8VOXLjkU9SzHI6OcTMBiSbJiWf1V1JKjPSHJIMpImqkA6BZ9zMyuWQXLk5+EGeiqJog0LdGvPaFu4tWQf9Lie+O/n/fWMPr65+eCrKdGF7G+XlIEQiDEgOjiFATl7JR1oI683tng9hFrITqUeMN3LNpOQ4HtWJCAqUS4HDfxrPInVJtr33pmKxqEmOWy5XIBaBUqlU5HBxFR3HkKQfkrtLPxDO4ru7LDWmYsFDn5W0qUTEJCKqdCqltNxGUsgh8cuer7S9Vm5rfbIQ5FJmJvQ7kPMB5YgdYpa+SD8kK7G4zNUw6tYpk9k6+scd6aRYzlWiWDoiXSGSdCVjI+mLFgEUu47zQWvrln5r6ydokG94xuDVWTN3bRg6dJjyfArEEgHuwEl16Iq00Agk4oJSgMElIHxrkutaDhmzZJAbBtKU+OGSbEhHeZLjBZ6RVmlvm3vC58Y/yiJuJUu/9tda3hnjBn5jOY6pqWkozZ8/n1zHJ5xbqDCVfpm2xSWWvslxRrwBBgEgIC7GzFl6RxgnCeIxidS6iEexLD9cZpZWquejEl5INsSLQ91dkpy5ugJFqfROzrlYrsWKTsmvr2ddlz/6r9MeKaDcygwsy3z7ootOen7Wa7/V+dzesefWtycJF4YNIVfEnOsHRI5LYZxSFCaUkCZwiOtXhksaHANa4ntwzdjleKAM8iIMNwuzcMdZOTm5TLy4JPHIh/wkPGdull51tUQrc1wQxvHs4ko5c57KsWFmOXUcYkeRQrjDlQrIkT9mFq+SPCxwBFVXIqUrMjaMrwMmTj7QOqEuud4cud5gmYpdl9Ncfsi8sPz5m/50+x8vnjJlH+mTkux97sVixJGIyRgQrlly54V7RUzM3SD9lUjZWXLhulbiEmnu6hIpk4flemVmUuiruFk4c5GPsKnquLN6SMLSd0qJBVqwuMvMklotx9Iv5mUIS14tx7oKTcvqpqQpFmBhIZZeALi3JYwvScIHKXJERIpOp3axVr7/4by1qWNTn9tqq/Y9tt3+MU6iBcIPRTJXpi5ROQqJpGNKpwRgyKmc9rUAKXKfJEesCXAJGzwCmfcklFKaxqSUeGWPpS72fUp9L//Ic8/tefEDD0hLkjCI98eIvGDYkH1DJQwKEZ7c0N2UKCdkazEVY75g4asWxJJBgDgtnAOpxiHGbSehLB0uysdpJK145Pie3JxC8rRu9iuVByjbZKnLl2+iWsRnRWtiuZHJQSUtbaCO3lDbPvrQHSlpwnFmxzEtRVFESi5W6Q2lYv4nOS1NgnwcsPvuH+6y03aPea4qETGRnJSSmVKWE1TGTx3I2iSYFnoCo9WEUvAi6bGcryQhV/riS11e6pDLEpIxJnJDKiu1yT//++Aqt+wgBC3Tnl+wIB801n8mYuaiiFrPCygVC6srXDtyOoEjVJiy8NcBEyd+xONcwLEEcCzkdiolU3jFlSOJiUjO2VTOYy0IozLENRXSZKZXiv6HOvqDi7VW095980DO58ivy1NZLD5NdfXSYEQO7hdybHF+mv5JX7Wcv2iHNRGAMeAagAsgnzk3kLc7Os4xcIA8gNx3qRbCjrSoO0Ey1tr0zI94oVr4UaREAbBMWHXCOcvkUlZEur7wye9efsPGtJJv9936q03yI4ZMDnPeiJLwU0oSyjc0UrG9bMYGjnH+eEzkyjWdzQUkDOHeruU6TGtQyz/iSY4BwFI3XAD+DLj+a5HRlfFsXImUw00AMRsXZUxY+oE2AekwZZBTlXAuIx7HG/EIJ9LXDLGOCWlwgaQjLfOj/wDq6A7Ep+iJ3I599swXOVgjnUIdteO+VKjjUhBsf9Ndd176zV//erQMoe89cLisE46EpwT1yvmk5Butw1qGrEkLjwD6a1xiubsyJSo1YzBx3fIgLkMqYwOycE8uxo88mQseMt7AHYD2u4A0pR0wx4qJat0srTe3p37UxqH97sjSOwmVcVMHWO4P5h6RaiIBi+pxhKu8GARmz3p9VFZGsdw1Pr3Hrv9ZOO+DGa7nCD0J4Ru0LzeiRC4CZJSxiJOS5KVs0AYuDdAAABAASURBVFKtxMkuDYlUk70agxMSkFZNfh9CR6wCiXybC1Cn+JuLRbcwZMhujcXiRlLDoN5/c/nlWza3F3fAtwHlOqRlMsKBcFiR72Baqg4fB6sWiEUYbk9AGhj3PI+UCKpIREcsHBeCnG5rbr73rIsuejcr9+Hee2tiJ2XX0SxtSgGSg0PZMRJPjzva6DGhI1JOnepxl5OOmYmUjMxRpDtArtuRk6Q51ttvueW/NdE7OfkmKdc0oc9Q62gHFzvc7qA+tpSricxMLF4nJZmPmFga0aQI6l/l8+vc/9DD+83QWr66SqZBul9y2WXba9fdpSLXbCDfPhcsWEB1siyBix9DBie4duE3QITxVD/AZfWGImdFR5qilHBOKTm/lBzLRIQI7gmO4xCu63KxpD+x5ojfX3LGGW3Uz8259dYtFpRady/FIUVJbGrBOSBnkrk+TIT0A/2r+ql6zmUBcZFfnD73rHytm/n7KrikusGHUi65SnqshTEmSkUgFOPIm9+88PiLL75Y9VX/x5V22223Ofufdtpn/nbf/VM+bGvbVA6oXC/SVbk/sBxvp+MYy6gog8zJ5jozfeZUHECcmr07XwhnyLJlYbhZXF8uJtLadOaq+EFc9zTEAbifwE2Z4BDCaE9uDdQFmL9MjsU/qudHdYy4NkjaJSEB5eHi/qeEHSJ8slQg9xyhEM8KAZHjcKjcHe66974pP7719r2lfWSSfD3vOG9wz0IqM5v7WMelSGgfQBqAXtWOvdpXOfcYqVU3i6vG9P2Z5e3NxZh7Qt+1Ln1qNpZldVnuDRlHcmhMg3IIjIsP4VwOG0gxx2abi2+6KYd4k+f8Y499a+899votviGynAioAJMSKalWypgBi4sCLFK6CiZmRlSPYGaTLksshIkOEzSWV1IRPvl8ntva2rb54aU/2EM6ZvrQYyWDIPK/j/53QlNTUwMmD5IbCrsOAUkayQ1cvi7IGIUD+ey6Z3HMVR6ZuWsGCSFPe3s74SYVBAGuRQor5eYtttzqlgO3265dsnTujkMa+QD0hZnN8UEGZobTI9AGUJvIzJ1lu8ej7gyO3ERr078x4YznNhg58p/CABXEMgSXOzKwqHO0kyH7htCRLBc+GSDMzKZ95qqbxWnF8HZJc13X8VzvCyccddQIkzhIP958880vy9ACnA8VsdbKNWaEpcT1uLPc4ZbmwhP+CNcsKmFmI4RamxdSVAmJ0mT2Xjt/+lak9QdyrJ0Xp70yTtrYxJdvZI7yCPcJtCdpcn3gzlOtGfekqq/jU+5T1aPdEV4Kp3udS1FkiVlQZ3a+Qxiin55yCIKopbX10HDEiJXO2ih95mntCw98/e03fzXn/ff3knsHy2bOF4wF/ANmDlgiA9UMUqfx4JhkUMzmGCItA8t1Do4ymELy0T0sUX3uzGilzyym7e45UAroHr8sYWbuco9hZlOcueqaQMeHXIfc3LJw+2tvuuGi3//zn+t0RC/mpCBeYpnZ1C3eThf+jxssHQDE+dj27Byq7UB23sCtjc/8Xi4grDSV44jEv06RQzz2wJ33vnJb8Ym0EqViEyBF1RNWbkhmspF7pHGzyuAuiYSsk55YJHAR4ZtjBKuEfGtE+SFDhtQrL9j1pQ8/XOnXwdHf/uD7V145fOHChVszszHhQ/iRqjKHGyP4Rb3MTMwMbyeYu4Y7E8QDbsUxO+oAv1pMeiQ3FRETs0768nGvm8SaDyXfTJhZO8QkbhcgG+Lgdgfige7xWRh9gdUmlQjk0xhfBonrvvvKeTAslclRRC6xSUYdxiMfmR8uIFG97jjZldSBdgFkzFz4iSSVmfzAXytXKGxRjRt8n/gZ+4LmBdtHYu2pb2wgnGf4soFrjmW4gDhGGMPlRXqCSCtEdUARc5a7I0oc1IPzleTbVSAWXM9Vcuy0LEXRY0effrooIOrX9vDMmcNeeOXl0WEc5UO5N1Tk5pR941PyJQHoq+La86PWjzK14Vo/SWL3sET1e0cfAfTbXIcQZOyQI980WLkjnn31pV36XfkKKnjpjTfW//bW209rKRU3cAPf9BVLjOAF9xM0Cxf3bmY25wRz1UVab0D57ugtbxaPazjzL6vLzF2KoO0uERLoKU6iexRFiAeYu9bLzF04YGZSnednKncZbdJJNmaWz+qOL2/4EuIFgbSnNsoPW2tkNWXxT05YM1fLMnNnfYvnXL1icPwy9DVy1tTFQkayaSZqbWsj6BfluRSTLjz1xHPmC7CSdLNPvvDCF1QSz8h7PsXybQ4HNpL1CKnPFESmFB8ZcMMUMLM5SMycpXRxcTMIw9BcXLgZ+3LjbGlvowXNzezngk99/dvfXqaf/XWpfCUPtKTpDnGaboDx+zJuJSZxw6uY9CEW4Gdmwx+Gwlz1MzOCfSI7GVyZhKKwTFomDYojHZUrr9QFDbN7KpyVQRozE04M+JcVWT3GlcLMi/qLOImSCx1nDnxdMcTPP+gSvZuGFVKkieUcy3JkZRFmrtaJPgKIq4WSdOZqHuZFrpZMyF+NIWOhwMnHvj9o3x311H//u+77C+YNIVUdNSatUK455mpYKCEhmhZtinDh42YhB2pRdIePTSqZDUsErnx5wTMZYaVCJAI78HyKiuWk3N720FZEkcnYj48P5s1bZ0Hzwm09NzDXQO3xR3UIY2IEEO4NON4ZavOgfBaGpQGojcvSlsfFcw+Jjs23SnKUuVfinsfMFARB04uvvLzzAw88YMzry9POQJZ98NGH915QLu0X1NVxnGhzjUCo4f6MvuPcwVgSuT61nFNA1j4zm2OVheGyfGQQr9lxzHqCSZQPc+6Jix354A4EsuOLOgHUiTgA/gzd+5vFZy4zctDiY5V45moayca8yI8vBt3bcUVYtpeKpF31iR/+8PuwNkip3nfm2vp6zzfQKUpunMCS6kXvgCXl+6jS0ZcMPbXZ2NhIscwx0DJO4Been/YChI9WWeYxo0aVw2LlTk9ueo6qRieyLAW1ZJBlFHdpCMIJAOCC8mXSx0Qvy1uECwudwUWmXGfrD+bO2UyqHHS7jF192Ny8a76uMJyUQ35ODFtyEwEPynHIdUWBxnHnhcXMnX7qY5N6O1NZfPimJg55rChw3HC9tdaedejo0UXE1SKVVe7sxp/Vwcwy78kZX5uxm5+ZTb+Yq2635C7BRL7tojagS0JN4Bs/+UkLxckjBccnlklUOiC7NqjJZrzM1f5l/TWR8sHM8rnkHeepI1xHwvOs11477LQf/GBot1KDIpgfMmSzhqbGupSYcJNl7uBNrl9wlyEbLHipnXiQnqVlLjNTKvcCZiYl94MMcVShinxx0VE4Y5cddniaubYmWqbtK1//+u5ift4kKORJeS7J/YCkPoNErFdAT33LGtGZp8PtK29Hlk5nafMiX4bOwjUe3M8ARIEj9B9hoV74Y8fxgp1agmCleYnmo2+9lX/ng3mn+g31uUgOHe7t6DvuRxhnJJY3hIHs3gJ/d2CcirnTioiyGWgpN0W8xJyoc4mZumVAmQy1SVkc3Nr43vzMS+7forKp4UIoNfcytAFgzsN5rRyn7vW33tweb8NeVGaRT2OpZVFwlfAtCzv9HRA4zLCkOnrqD/jP5/PEjHtjqUG5HqxuStVW5mp6fP4HHxQD3IRkSSqVbzKpqH5AY1IT4KZZW6Y3PzObxrJ03AzQAYTRmTZRwWLedqKUBuXLDG998MFh993/r23CJA5imXgxZnyTgvJkZvMsA7gAr3CBWj/CADPDMcjS4QKIdFwmMfqIsadC4i3vussubyC+JzAzmZsVddugf7uBySFAy50RoI50xHWCJY/UST1szIv6XZssFoJYJs1/R+VilJbL8iVJizGiKnwwpu6oLQs/c/d6U4kGpCo5VyVArMnchODHeQc3X183rHFYozSP0OBCKQnXaa+EgVgXRWDnzI0XogGir3ak4LY2DJ6EKoK1JItHHG4KmhUxs4mWpSjzhQVfVnzXI1cKDK1rfPkLR36+3y8tRMW5+vp95PpwWkVIFcslQp9xraBPzExZ/9FvyLBa4GgTV487LeVm6pHlYHwBwH0MWMqiJhvKG0/NB+KMZUTiUnN/VCTMSfe04Uw7aou/PfDASvPrrjvuumOXdh3tWIxDKoaROfbgvCzWPADiDfdpcC8WK3MuYYwyvOr5IMdFPLKzgYkXTsFlBvCLeANJow7g3MqANNS7JHTmYzJ9lVOvi4v0voC+AFnfurt9le0pDf2tjc/6UxuH8eJcwHkBa6nje9RaLlKuoW4r7/33/S55OwKciOmtw/9xOkvLjxyOpeom+OoLJF8PlhZaC6OC2vy4V9R2xNwjdCrXIO4NqTlHcV+BoC/kcgU/8NelvffuKnz+72tfe2lY45AX5Rs5YcLAyZ/KCAEcYDSAQcDNgHCGLA4uM3c2ysyEi0siZJjaTPp1dXWUSAcXtLfuc/EDF7so87FjADsg36A2SB1n2yTV7Im5k5kJ7/xQrmNeFYADwTXtgUME4dYCcb0B+XBQ8XwPftFUaSuW/YQXe74H5ZVWDFe6IYfBeM1NjbRCdNVvfNSZTjUb2qoJmjzM1XpwfiAtO0eYJV6ac3s4qsycnn36pGcojN70lUMkVh+ca6g/A+paGihmOcGJWCYcTV031EVpdfKBFaSikyH33H33XhIvneuad1UPFSvxuuy5gVfImWfJMHnJOM0x6nts1WPfVx75pmoECI5RGoVEaUyO1sWovfgkzZkzv6+yfaVd8OMf17VHlf3MNSG3IcdxCM+U4Dii7ziv0WZWB+Iyf3/c5S3fU5vZeQ++kY7+oh1mhxAHv18oDPnLXXetNC8z/Oe//v2p9jAaFjtMmJDRT8CVizU7Brg34Ysa4mkAN/DRHUtbPcotbd6BzMfMi1WHvmTonshyz6mNwz2xTUS9n8sRuc52l3znO+KpzWH9y8uAuWf0UAmOnO95MkewUM/QIKpSLK9z+Q9/WFC1+dfaeOP34vbisxQlqes4hAs5S8fF3AmZLDWrqvKWDGhYHLNnijE7MVzkixOztIObGTKlpAmih0UEyLeOzZqfbtgB8YMFMna+8Btf207GN4oUCE9laIrwArBYp+SIRc1Riph5MeBmU4uux2Dx/LhhQVQqueByrleplNvelsYW3xURfrXn4HiI2JA+dsnDzJ1hpGVg5s4+dmYQT5ZONd+6mdkIKBxn6TfrVCIkb/d943XWfyOpVP7HSYz7ArFkAJRkZ4YPEUwsHBEzAZpIzhr56GFnljwSb/KICJK2idJFfcGrGYphJTe3tW2r39x3n6w5SuZBst/53/82/OXuv29FjhOIyKZcoU4u8JRw3YEHZi30ASwud46a5RpGgJm7xGfHNXNxLJEvl/MpleUnWHt8x5137OeOeHj8+PEJ0vqD6e+8c6BYfIZGeFmb9EE6QakcO2Y21eEagIeZJakKhHHCAPD3hKzf3d2e8i4pjpkXy7J4vbi2UzJ9UkxCN7Hj8RZ/AAAQAElEQVRci+BeYilMYuXWBYf/7emng8Uq+4gjcK4saGvZhjwnT45LsSaS3fCL/mJslTgi+V6N55OMBQ5dZJZrScYmlxSCXcDMhGPFLGMXULYJB3JAs5BxmRflYRNDpm1mXiqXlrCh/92xhCLmWGVzVuY6xJQBY9Yy9t5AHRtnrowFXvQjkfVO3O/ZUYT5TuJGLmhuziN9cbjEXK1F8pn7KNzF8/Uew8yddXTPxcydUag3Q2dkh4eZqRYd0Z1OVi5zs7ydGbp5svTe3G7ZFwv2VK42U0JybsrFh/7g/gFXyCOce7gOOU0IP6bB6yYcVrISwOuMGjq0QabDRdUc9slPtu26887PyJ2zFRkxUWapuKBxYsDN4qpulyqqUb18YhBZkvGzQ0FdXeG5aS/vSoNoe5rI9fK5PVzMFqR6HBkO0OJcLp7V8LR4tBxbLUjk5hSTo1juZYram1vnNJbLiwmfEfSgHHLN0qa4JOVwuyPCLZsGYFMdNS3NeNBc5VOfmrv7zrs8J50PcWIibkkAD0CWL/NnbhZf62q5IFzXp/ZimTw/ID8XDIuYO/9fS23eVdXfmqYjg0J+Y0xYWJLCOBQEo3iU3BRwzYq3133R7XDxLEIfOCNYAOI4lttCSHWFvNxIim9XwvTlxUssXczFWqsPFy4YM7d5QWcBOTc7/UvjQd+QL3PhH2gsqU+9ccuazISaSufa45ByTU3b/vTKK9enj3mrqGgtdnmDVO4XmMiJ+zr6S+7skvjpXgPyA7Xx4Ko2vKL83dtdEe2ATbSD8wL+2jbkVCBSzBUnlLOjNmXg/GgbWFKNzNxrFpQHesqwrPE91bEi4ow47TYkBHFu4f2BsPokUSSih0i+tA31HCevajvC8vVwy822fjwpV95LKiEFrmcy1+ap9aPB2nCtHwcfqI0zfpYudQAXX8Q6N+OtNz912wMP1Jv0QfBx87e+lW8ulsZUkpgNR7oLzZ0jzE6kzO1MWIInyw83iWLKy6Ream2jYQ2Nz37rW98q91Rcp1qJAmZKNeGEQNme8tXGMcuxqo3owY+6suisTrhAmprLPUvudPGvNDbdaKNnlE6bUR7oTKzxoA5mlvszL4qVsEQsCnf4wLMBaRNjyooX37ocWWOPpZFU0doiRtcwGQbJx5Sbb95sQWvbZn6hjjw3MD9lh5VG7rEEAQQeAHwbSoQb+GuxOA1yrmpBRwLeCxSI2MEy1JDGJorkvrD5Jhvf9/PzzmvuyLLMjnvzzaPenDNnt/qhQ8W6wCSWQakDbS4Cc80xl1Q5lNJ7WgySROa4S3a4CA8kmFlOt75RbS+VziUC6anGlxIZl7jkKprf1hLkGxp2r+b7OD+dYSnzOrBAMFfHlLJ0uc8u9ZyI80lGahJxPhlPzQeufCCLQp4u6EjQcgYQntvoBi3hpQO4rqKjyh4dufwpu/fBn6HHzMsQWX0pqBx7KYPxMVX9EoTOMeernECklaQI1yp0MtqQ5eNHqs180L0jGAuAORyQuaNHLYA8rKlah9QFjjNk8X25NOAb+O8Ai+VblnBxH0xhfZMvb/lC4RNvvPtuI+40XZrecJP1pw9tGvqSFpOnkosDiRg4IMeNAMShatJdi4OEDMjTF5ilJsWUMKmEeav5lcpK8wAgLef20ntvbT9kxBqjIrkINHXlKKua5WQxnIqbxfXkMjMxV1GbDp4RxgOncVQh33OTEWsMuQNxPSElYpIN5QDx9rozMzFzr+mLJcgJn42ytm6t5AAvlrka4abpVOGg8+3S1djFP5nZ9IW56i6eY/EY0wfpE1yIAC/wKRaTZyVNhr/46ouD5pddM2bMCKbPmPEZx3ObYEqH1Qds4FeUuNhjudAR7gspJuduGTAZMjMJ8VRfX0+4acDq09zcTGkYRXW+dx8tx/bmO+/sVI7C9eWLAaF9HKdaLEvV6Ouy5F/RebNxyLlNCbGcd0T5xnp6YcbLx+O5phXdfp/1K/ZF9PhaLkucH8xyjLsVYK7GYRzdkpYpyMzEzMtUZlXMDJ4SkTc4jzv7L6JNvtR1BuExt3nhI/WTASUF7aP+5QHqWBJ6qx/neVa2ex7Ed4+rDS8pvTbvkvzoB4jFnAogP+JwD6xUKhTk84TzvqXUvvb3f/yDtbL5CvkMThwzpvyJESMeCFyP4rBilBzLUUOlcE2mjg8o+t5uPBgU0JG100H+DFKtSAMmx/PW+8/Dj37spmAaoI2Z9ysnkYzLJYy1S7VaKAckEpz2xJEkmV3qMTcPuIjIXPgz4KBiUioEwbuO7z+fxS/mivJBW0C2NAV/93w9tdE9TxbG+YCTDMjiurhJ3CVYG7jkjDPmjFhj6ONZnCIWiciE9gGSDS74AyTY444+ZAk9jcdxHLNUox1F2lVr/OWuOwePxWfYsKChoWHnQCwyOA/AVxAEJGpCrt3IPOeTcWM4lAmPBFqAvECWXuvWxqNe8Ooph0YMH0ask2ntxajfy1wPvPZa7q/33LND/bBhQ8OOZ81QP/qMY5kB/antB/rfFeni15YUyvKIt8c9qz9ze8y0DJFKbmKK5OKSMhgHwvh2DL9EEb78tBaLFMbp+nVrDvnYv9xJd4VWJvwPKCUkOMTU04Z7O2DOl25ZsrGhnJn0O9Jr45EGoA4A/p6AMv0B2gV6qrM2ToZo5rAsDm1l/uV1UVfn2MS6IBee7MJwZ8XV8wJBIZ0EwlQewQEF+rGkCrvnkb6gP53FuvPUmdDNg/MbyKK715vFw0UbcHtCX+V6yr/EuIz/mow4NqwUJWLtiWQuguT08zn3g+YFm6uafJ3eesd5QMdJ5DD3aN4i2bSk4SYj3n7tGDhO3EjLyeGoYQ8/8d+93nrrrYE/K/rVu/4Xuuq22+rfnzdvTKlSJiVLLN1rwrgRV3tzRHhJYJZrRjIxszlhmasuJjosQ7Q0tzxy8QUXtEmWXnZ8J0nM8UQfAGTU5oSBj0y9VLMxc02ob29WH3LhuNaGEdcThg0Z+i9pofZOYfrAzMbtqUwWh/oXAxMhLssDF2Gc/ITJXrm5d+Z8sGVv79JA/lUJP/zpT9dvLbbtiAvb9TxyRORhvPiWg3EouejhLgm11zGzkFhTACLJcZhg9Wld2EKu4/znygsuWOw9UTVF+vQ2z5mzdqGhfreF7W1uKQpFMixapkDf+yy8WKLcOxaLW/4I9CND37WlPZ6nzGzimZk83ydfhKkKvDXv+NNf8C96uO86V1wqYyPqbN/p8Eo0ZaBl2MBRT9lRV/d4xNUiS6+N648/q2dZXPQbWJYy3fP2VL6nOIxJK2GaGRzziprgemo763NfacymX1nWZXaZebEyzIyxLhafRfTVnyzP0roQYQCEW09lcP/CF0PoDCfwKHWY6xobN+1R+IzdcccZspb/iisHDJVlFcMFEFeL2htnbXxPfgy6Fo7rk/IDlSbp3g+8/HJDT2VWpbiF5bat5s6bO9LNBVQWi1mXWb1jIBg/vD1xiXiAmeF0ATObE4p5kdvW3kK+45Zcx/373ltt1eX/c3UWfpBk4iIjCtA2QJx2JvffQ8REVchAezyZqPdth222/48Ue1duC8TMPaJ7afQd6B7fNbyoJ2apS0QBJm4BrzlixKdffeKeFXX/6dqNFRx6+503DizUN+SVJ9eQcqlUDikbry8TLgRQLVfwG1HKRFqQdQ/xmb/T1eBQdT4nhHoLhUIpiqNHttpqq6gz3zJ6zvvKVzYI43gbz8+RL8ja7u6ie0D36iHUq+g6hu75+hvO+rG05dHH2psu/AZSATMT/mWBLOuB78bWUvFT9zzxxMd2j0sZ33kJXSb0Ubq4zHvGT+ZmFWAOqEUW3+nKFw98+ciA8w/oTF9KT9ZGlh39yJDFLY0LElBuSXmZkbNrrp7K1caBW5Rixueissy4phaFu/jcLqEu92rU3Ru6llo8hHKLxy4ew8zEzKRIXLkpU8e2NOWZpUwNOooSM2feFeqCbzSA+bS2RQwjjCtidY0plOVHLK1XUk1uobCZQoHumDBhQlxwvbvws3ZUtii9NjuqpWUaXC2J8ANyhM27R/z6widv+PWv16JVeJPx8L8efmiXoL5uuJaTXLFL8l3ZjAg8AghkByfNPBIJNjNI0Ow4oAACzExZOjMTM5uTtD7IU1gsv3XkuHGzmLPctPjWkZaolEy7ZmJDttpjinAVUlfVsxSfWnpClMqhTEg+jFUplXISks/e95POOKPN0/ohlrImF26O4sE4WdzuO+IyIA9sWNKqNNlhNZCTOiuD/psbq9SJiSeVPsrxIa145xuvuRmvLc+yrpLuxRdfrOa2NH86kcPXLksp+NksnvfyZYkaS5/4hReOs4GcOWbsWptjQ8ITwuCORADjeQTDVQcTnecps+EWoqe+Lk9RqTz9s/uPe5k7zqWO7Mvk5AuF/VPFw/AyT+o47ujL0lbCupoTLmsZvNSR9beaQtUxZgFxDQcsrQnAVzZWCRLqkSxmz/KZgHwgDZCSEpJPFDC+6ke1faKsPsRq4ZPknBOOEKS6fIGUiFIHz5kxb33rn/+8xH9bYAquiA+Rq0b4ynlABO5WRCPVOlOpP+NTCx+ZP3MRh5xyRpKGR9DdlagVtmdtVY9vtZmsb3A7Ysy5lB3Lalz1E+cc0Fled+OTuZqx45NZriU5VTqCS+3Unls9FVqWa6e2PPoN1MZlfmaWo1ftP/KgDbhUs2HsAPrXE0iOOeIzF/6egCozvpfVRVn0q9pThBYn2HcDcwxzXk6+FGpyXVduf3rrbkerWpjlxlbg5GEnTRe6kkMxS2YmrapALkcmUE5Cc2NUWjKRIqK+XWaHsj9XRAGg4pTEYkFFShtKnrNK/z+l38q3uWlvvbVj6gd1UZSQ6zhy01PkKGGGNblyiQOYaBKWtUeBORmEUBx03JThagkL4cQyQRlIhOykDf+OJDGxlnoFPrna1/TKp7bddhaK9Qo5XiJ6tEw6ph6SY6W0a7JjAuwOPCyLONM/lhOqFxA7pj7kY2Y5viwnWkpmc8xnrx+bEIX1nndf3vPCRMcEKxn6R9I31/EpTYmYmUjGzTLBsSyLuhKHlzWmwl3sMuE7LECy4UJkIUpO32oZIR43euU6pl+ShdhRQzhX2A3+VRnlNZq2WhBH2yUOk5/zSKgQmkQAxgl5YqlVjpAvvEkkCYnkEJMSsBZqBLITNryXB2nwa+SXXJKDmFnOMSIcl3qZvKPWNu2H8Uv77Lhjr28GRx194XO33ea0kB6ncwF5riKVytKrIpJTiEgOHkQDkFJCRtSaCZrMJsnIIlDSLymrASIHA5Fvc74jV5bkVxLveYHEy3mZpCRWPnJ9h0KKqSzf/chjIkfKMlMaxcRSuysclsQ6WyqXyZcvEqlw4Mj5JTc3SU8N8Osd0zcRNrhGwaMUlSyaSNokiZfOUepokutMklLpQ0oUadJyTFLlUuS5Wz009YnNJfFj2XG1s5wJWpZAtYwR15BWLN2vAuOibJN7jxb+atr6IAAAEABJREFUMpD4cS/KkpmZmAWSD/FKK6nZIZZPA/DHjhRLiSQfvnkHeZ9wXCthSK4co1TOU7Rp+pH1p8NFHKAlTy1Y6qyFkrFkYJb+dINmOTy9gGRz5MJJ4pDYdYikLKwCjgumUkqThKQoekQ4tjj+ADOTAmSsGDfJxszyqUhj3NLnVFxNSuKI0D+ch44UkrFrE9ntg5NE9IWcK3IOI4mZiZnhpbTqGD8+mNmkMVddxC26PkhORd2JhDTFct9EHUq4ov/P3ncAyFZUaZ9TN3T3pJd45JyVnEQymBBRcGV5a1rX/My/CphAgXVF1iwKAiJJV1eCGFYQUcEASBJFcg4Cj/DShE431P991X1nenq6Z6Z75gWEfve7VXXq1KlTp6pO1a3b0w8ftSKeMaKIC3RMEbNWRRU2QJoh1y9PfVELPsApQSF1kC7gpXyiTh5lY51Ec15zmn0rqLeb0JVxbeDNoO4xUDfqqLGIhwXCRCJ5DQWugm1a17BIK3zztK/dp3F0u2Jjwnz0isSJFXagaMpxIB4cBg3O/G7ADvDVCH8lFDNBHlu65NVHwzl2I2ttKHP/vfdumhizy2C5rD29/VKtwOpNijXayzbkYdyh42qTlIOIWcqbrdmcdmcf0HFYo6KqmHZAquUtN9j0T2879NCnZfKPTZHPiVuTb4QDAyQni2EjVLUx2TZOWU6vOrsKa6mxJym8Yi3a8q7YoXzu+E/9RaLq3f19vRgHg9AFCxbazNc0nKi0C+VTgMGt2X4pxg/IbjxSBYJpiwg1CcJQkthKgNddBSzgVYznUjU9AjIpjqzPSZSN2a2c2rkJ2pk1oNE2pHF8EYwTzCcYz8D+grtwSdjEhbwxTgSeLytXLJM5vf1Dm2+wwR//5ZBDVjC/G1T/eMN2pSTZKRYrCRaVAAsMxgD6XNuiVT2NbVA4EcqgQ+V4wfIhKTYanqrwl8H5kJFiU5PzjIRAgrgmseSskT68avMwK6gL///AuXPnup8DSLHj5u9/5AO/Nq4steBoSoXjStwYNySKQA4jtVwklWCKVAC6LJi3jmDBE6+Qz5etPRh25QqDzNV/1fQX4bxl7RaLV0ZjOoMqGpIlEKqOT4PU5iIfIfAvImiyBNzkisrw4JD4YqUf85A/l2Kx8WRfso8En8YwoytciGKD3C6ELbH5RO/DZ1isas1pVZVsjEwIUYmBPmHoOx4LvxrCX1QxPnhqSp8xKlNSSdUNBGgqaJsRlezTGBdIzOiCMoynvDn+tM1fdVnrjYob7ZtRiis+5Y1tl9RCtzFWww2Os4HiccJi4U9hL/CAz/HDBkHgCV/JcrAjF/mJzJkzRyrloqiq8Evwqoo4ytVDwYf29KRGR1KYVlVEU8QVsIjzSnkDWof0QciUTkOOF/Vge09E2c6mEPtPMaQrdVEwoXUYJ0kaqZE2n6Rkn4qT5K8wJB4qDTY5HjihOIQg4hyXMxwTMwA7ef7CdYRH86VS6UXrL1my+QzErdGiZ5773e3j1G7PCcOjfP6fNzNRiMOGyGSg2zCpOMkJDGJ0Ijp/aIcdtrsp45ksVEXn1xkUDl8E/ZmlkaeqolpDndxRkI0HVZ1+OT95AodRdyflqu0Jc5IPQqcDZYVwQhTEMULn7Ba1BtGMYt6SpS0yB+acGRZbD4vZI489svPHv/71DdoWWsszbr/99vCWW/66S5gv9NJO7dRVVWdL1fYh7To2CjAibG1cZTJp3wJOaIrDg8tfuvdeN2T0bsK++X1H5Ap5U8bmI8Crn25kNJdR9UTQPvgqMR7iIs43cUEzeFDrx1G3FqvilarSZ430An65KjIyLFquiGIjzN/CGlqxUop4ZchNEOev72OJhi0gbpoXXSkxnp3jD34Ni4mVOI4lDINXnH/N+cF4rjWWmrRiVXX5qrXQJZpuKR6COT85hogsm/b3rEgMm0q5LPN7emRumJMCaHksujmciPcbX0LYOIBXwytv6TT0UM4zIpOBi3ZboLxgkyvYnLKPqlEZ/RNKzg8wpDxhf2XtYci51gzSO4CaVfA7Ps06ZWnqpaoM3Pgj3SUabhzvxUpRCn0FGSoOieIErFwtydDIoOR7clghkjHgVJ4bwRRbKMKmsQg2mx79ahv4sG8j2M+N6cnKMs9gzrQD60+gS6SJRAZoEcZ4PRBjgWnM5+kvhk2DFRqih+6yy8i/veGo32BgPC045jQwoMHuieDuKsIuvJUhG0S4KHkIl2hxY97SpcuFzgaOfOEVV17xOtBqvdWCf20l8S+Fwlx4eIhHHDpNMep20VxYHKC4cxBoGUPSQJrycvb2jLgycBKwzVgZOBAco9+c9/M3jhFbx1QVLn98HlQRI7yPp2cplMmibcNx+rTlap/xpj0OXvqKgw68Aq5mhWKclUsjbpKyRDmqYljDUzLRAiY1jtrwIObS2Y02Vt9zMjwsigk2e2o8WX/jTdYfKpdfBd3bNz4TshaGNz355HZPPvvUQeU48meqHmzQUoSjw6lVKyUJ1QPMn3L5/ruky893L79847/c+rfDDXxIf3/t+738U/mpxHEMToYUjpX5dOCcI4J5xzR8llWcWIdJ+p5N5y84ap1C4Q39okct8HNHrdfbe9TGcxe8YZ1Cz9GSRD+c09uX9hRyEuJUkN+TiqIIbi/Feo0N0iQKTpxRE5l7e3vdAlooFJzMIJ/b9pLLbth6Iueapzi7NanRitbEgiS2PNgAIeIuI9adOvA0bX5v77KBMP+PMEof70nSR8Jq8o9CZB+fF+SeKKT2yQEvAMInB3yf4RKETw944dPTCeeSz3hPD5gAGBc+NWA8IHiqXw3gLUH4ZL/6TyAE/H/0i3msz/hP9oeFJwPPH+QpVIjTzfJIUfijnR78Bf24hRPhXCBc46Tmc5gmarRp37XdiY9qYqdna+w1rHU+srl+polGbTg/mmmsxyFNKnhwLociZS+Jyv25XDlM4/KcnkLZR9pPU5cOExeWcqkt+TYuBWkKxC6dj5NyLrFl9K0LC0jnMXUYZnSkS8gvIV0iHWnHz5Bp0MsdhpRDeagT9ce2nEO9OYZJQjpQC8M4LoVxOprOIR/1lmq92GiphrhZb8OrfE/vjuEInGOBk0k5qFVFVYVOTGb4wf5JwlwOUtGhqmh/cui5V131nHsaP2nx4g2iOH19lMQ6NDzsnFx2YjEdE3Hx5tN1M6+tO3JVdZsf5nuiOJVMxaRJus2mm5//9Y9/vCQdfDDYIaGDAquQVbEhWyff/0tTTR/m903yXiAeRiWPMCvVam1coP6Ek10xRhC3iNNWSErNbmbS9tCJGR9Wg2Ce/Dy9bOnA7677w2t+dM01CyDuOXWh7eaUL526b6KyY2JTtTTCDFqAJUs4pyFXLOw6GnK7iPRAT6/wtcSWW2x5wcnveEe526pu+stfX16OKjtGaaIrV66UKnxKLp8fdeCj9aLOxvhU9cEE8EM+tMX8YGNQwC1YaZrmjbn2TR/96Pl/+eGPf3LXxT+77O5Lfv6T2y+57Cd/A66/+H8vu/knF1+yw9bbXVBcufIpi013hBMgviaDCPGxCfJHT6UMSZOgfT43dxyrI+US7CxSqca+WrPWfscM83GSdrbO4hi0zHKbH+vmJDc9RDpcPvrNL9pps10WvWmze37y8y3euudemy3adedN7/jJxRu/abddNn7jjjttfO/FP9mojg3ftMPOG3SC3Y5+04a7yRje8uKdNwA2zPDWHXbZ8K077LoRwo2BTYgHLr5s0wcuuWwzhBvd+6OLNkorleMrJZz2KHyEqhiAPoN9p1Zcexiyl0fHptR8EYJJL9VxE1RzSTiO0FxYddLsZnY3fyYQ6wTqimlQT9UCVRVVZblY4vSb+SQ+LhwpfmLv7bY/Ll+ufGL7dTf8xOH7HvCJIw84+BOv3mvv4w7f/8BPEK/Z98DjDt/vgGNft+8YXrPv/se+br+Djn0t8/Y94DjEjzt834OOO3yfA4577X4HHkf6YXvve+xhL93/2Ne8ZP9jX7v3fse95qX7MTyWYSNfxn/4Pgc5eVn6tfsecOwR+xwA2rgQsg847siXHnDs61964HH/Ahy5z/7HEq/f+8BjG3HkXvt//PV77/cx4oiXHPDR17+0BvZlzSIt7l9ftKi0cME6j4ZYMLA+OYO5DZAaMcYg7bUo1ZrETmjO4YThqwdVlSSxAr+llTTa7ldXXbFNM+/anraht7eXCwdoFz7l8cmxjCNe6o25I3waZXsJEQMygcDWQ0SbL5bhwE2xGHBxYr6qOtt7BuWs/GPFU0+N/gigTPmBoCaeVv2SsUyWl/FMFqqhy5+Mo5Z3yoc//OxALndD3nhicXxaxYaHdsxOBhr1YJx2YUhMVUOKzTo2CFKslCWB8Xv7+2B+GDEItw4HChvWNHju3P8hkqva+KDIprmwZ2Z/lc9xCZMIkVmANs3A71WUBoelMlx8orR05e0ZT6fhzU880XPllVfuooGPh8qccMPD+cG+6VRWMz91JU0VPsTCgzAhKb9YXNlk/fWvP/mQQ2JHanN7y+tf/0Cgcn9vLpQw8CRJI8nlcvBHiXt4aVOsJZl2zDRgnEyeGneazc0Y/UIOfWbC3HayFn9UFb69hsnUzGyf8VhE4JVwT0XRB3zA2mS99dKTTz45vZj/oS0WEcYJaYozTTCvE1DuxRcvSjJMpyzracSLt31RokksEfxOylc2OO2h//FMgLbUL3YoUU+urkC11g+qOmWVqopm6Tg+VXU01VqYZaLvyia1l/zj/6789hO/+f23fvqFL3370St+863ffeesb531sWO/9d1PfOpb3/v0Cd9mSJzzqU+d/t1PfvqMZnwH9DM//elvn0F88pMIP/ntLM3wO8cff/pZn/70GWec8OkzGG8E81muMfzO8Z86fXz6+NMbyzTHyUuc/anjTydYVyO+e8IJZ579mc+edTZwzvHHn332p2uojdPMGi3ChfPn3xN4vvhqxOCpORErMJrDdBwXeVuIHSWlkIdTEsGToOugoNCz0bXX37ADynmjTGt5hH9a/NAjjxwmnjEpdOWpAsHJg+T4CxsdOojxxLGUIt8AVtg1RlJMthS2T1WczRWFERVNE/HS5LovfeELy8dKt4kdPEZnWYNJMEapxWBvJz8LRaSW0eVdlTVNr7DCCW64zsKf2mol4alPiHFWTaoyWBwcFWAhjmOFdsiI3PSALA60C4Crnp0iTIULDsdpAa8auNgOlYqSGpVitbzNF7/21R3RXhYH73Pj+sSxx/Z6hd6XemgPfySTdpmJ5pbjDOONMmALwcCSVFORFJbEPpmbnzk9+d/85+c/P/U4k9afZ55aua7f3/OSYlTxeNLjYWHh0zT7En0vk6G1xBqVHYcpB11VAuM5OWkai8VmN+eZ4R1e9KJrapzt7+tWKv/IqXdXXKokRihRJMbYizm/fB+2EKGNDURw7iFwF2mES0xyY9v46kzVk3I1knKlKrffdde29BmTFJisw9oAABAASURBVFvrs9xYqWvZaBeRVGhFzk0P4yeOy3WutTcYHlwpGD1uw8tTevZZpVJpqTDziOn0fUsBq5BIvYhWVbC/MmT5ytOGLPE8CzmfJ21ymJp7eNQdx/EoH1yi0MA05CixywjlhoW88GmIzgaboDDX1/OqW5Yvx6N5l0JXc7H8tptuvrJUfKnyiRFPnVxgedoT4LictmpUh86+MT1Z3JXFIk0e2pshbY5XXCJJWpXE/v7gHXaY8jXXM3KwE8XyrUCZzfRWtGae2UzvtPPON0o1vk/xxCVYuLhhIZr1oMMhxjvb8ZowP7Mzy9OZ0ZENDg+JwJ6JqmgQ9K4YHDnwYZHc+NJrd+rpoaH9IxtvwT+/Nj6eSOublplondmKixXl0GYM+cRu0rSaFqM/Hbz55pN/4YUF2uADx35oEy8MX8x5rtjUko3xFP3M+Exg1Bfqy4cMI+riaVSVUP07Dtp0UxyQTS79Na95TeW1rzz0d6HR4ahSkkIIm6II5dE3IdriMpPQxvKyMcpxzLZSpht/1m4lm266eQshzwkS7Z0pmo0ZBYFAgCt1YF4em0ck1uor5/maC0KJsTHlGw0PG3O20fWX03ysT10SN1W01qhkcwekaV04UULBabGK6rRZx/Gqji/HthAcgwxVVdA2G+CBU56nn4k92mQILER3+6LiGSPVKt6D5nLurx84OFTHG7ipqEuqjvHQ6M1QDDK+2nAbhVwoCdhjo3v+8LzzBpyA58BtxVBpp0J/3/wqNocGjp3t4aaHT3psL0/JUknwzzrH3Ngk5hMi6IoWixgnosL2LoQtfbDRoYbqPfaql7/8dlVNGuW1ii8UUdShOLlDdyaCMiKC8xMLzfBUhkTLC2WcvgxbMjQRKZdoIk8r+db3v38krZavhmNAdda9asDkFIvF0QF60p027uBohwzOfgLjoDYIwH3sSqJYQs8X9omFp0rFihtnmu51/vnn58c41/6YnwsOMGFOojhxymbOjG0mHLGDG8zhxoNNUlhPxTee8JRHMTZoWy+RR496w+s4zmj+DiSPsfYM9ByKXcU8j3pHkXBD4WHec0yPcXUZw/jggoWx7U59BOMk73vYwPg/W8TXK9MQa6vVvyTVeAhzSqp40qdNOfaI0eJubmJ8uVBQTTaXQRtlAl0FM2uMxjayrWSJ4B8sFstY7MK//O1ve5K2egFPjgnKccK2MWxGsz5gd+ODYZbXGDeqAqlZlgvHZHKMjj0wu8y18JbzAknxwBXCR3iizvf4fojnr9qQZ3vgQEVwCsp4K7BZqiqqymhLqLbPs9ZTfNy4YmHGOQ4b6yK9GeQjWtFJy/IYss8ZUi7GpWX+8xVjM7SNBTZasODRuFx5hk9/XDjIxpDGI5ieCegEwyCPMYXFCI/qJgylFFU3+Nvdd6zV78GzNt98883Br6/5w97lOJlvVSWOUvECX9wkgnPP+GphbSLV4ryPNz+nBZ+SmMM4w+z0iE+NmlqBoUSixJaHhu4++OCD7yPPlMCBv7bY3YM2ZdGZMHh8pzRNATugVQv6511n46RsBE9S2KzwT0zpiAguwhTFhRpWYHTUSbgEbo5uVLJ2KWi0J4GojMqwKriw+TE7/vG3v92Sec8FnPaDHwzccf99+2HhFB8nEzgdnRW16Vwzm8EhOplMw0o2sPbvL95yu/sdsYvbiSeeaIYq1cN9PNQMj4wIv7dVyOdlaMVKCcOwC4nji+CZQObPny/Lly+XUnFY5vT2SLVUXtrf2/v78ZztU09uvvmDabVyB4aOezXKuUa/xBNojpP2JbMcU4vYelhLuTsXGz4IMcQeTcJcQUwQzL/ljjv2u+i662b2JS1XQ+c39jfRecmxErXxIaNzKptjgs/0bAbGteVKY+tRF7zipX+BA8HmVeAjjFg+Dig8Sb1vybZK2udT8hhUUedYckYx1dayohlJfW4XnjhTm9pz+oknln1jrk/jxCZ4YqlUS5LLB25XHBg3XJpKjE+qKsZRe2SbKAM+bqRKUUUKc/vNM0MrF2Fy6nhpa19qZO7c9Z98ZsnuJvQDL8AxuWckqibCEyy2hw0wbhqN1z1bhMdTmWKXAG6iGfenlVwsKIsyufHpCXPVjddb/+Z79t77GZaYCs8cjPnbwMQNAicvIUYn7Z+GYqs0qtiYnfCZY29Lo+o9vho3vnpyeedYaSs8D43WT+dkJRF1doWtBNBaO8jEfIaE4uZQtyeS7qJDwz4yLKk90hGeA7dHli/fJ5J082IVb53QHmOavGVXbTDYQKr46ouBTI4zilGF1ZK0jBpufuSGw5aS1g1ur1a3LQz0v0hDX1JP3bzgSShdRyEXdCNyXJlKHMmKweUyd6BPevMFiYplgc5/+9KXvrRkHOMkCX5BdoOF617GcUak/J4Q5oXHBxfYRIg25RWTSDmh2uSTrOqJZ3CqAJPyr7usUc96dpeevmC1//UqfCpVQp9nJ1YuOeUtK9fIqIoGicEcrcGNH5LqTI3zsE5aO4NUpEFtaaW3KjmMzPRjPG+K0TJWg6qK6uQY454YU9WJxDpFtX1eneWfOphOTyZ+mv4iSZIqn9BUa87LoPtUZ24892SFDRVl53I5sZCZqJEnnnpq709+6Utr/fd8nnzqqfW9MLd9Kir86yEekXrGCJ2m501mH4XDaD22Gh1pT0+P8M9/YX9ZMG++4PRNSkNDwwfue+CfTlZNW0uYSDXgNFbHMmBndOFYehXEEoOtRQdyKyuK//Ct3lutlK0P2yU49TFQkq6CjpeDNWuCaq0tqggJ1MO8Vk4LWe7iiRnlMMGQvE88teSAs846a+YrMIWuYvz93rt3Np4ZECzKrMrDPGHItjDsFGy/wVhleYPxy3FHG3nGiMWrL0nTFbvuuOOfTj55+uOsWQf109cW42owXC5JAWM55bEHhkUBm1q3kW8u0EEaQ0M83xdVjAGU428OpdVKkvf8P4+MjKwAadqXp+mtmFsVbnqolw+5ibAGEY6r1oIaqNY0JMaiHl6jWGuF3zEL/JykEGY9X8Ke3u1/8OOfrj/Guepjqoni4yrKQpeY4kb9p2BxNoKLcWy0WlrrEpde22+eZJqzr1PXFnTTGJV9iz5kOzhHGHYJmyZJS8tol180nqpvmvu5Od1lO57zxVrP1oZmwVD2o8cc83ff85bwOz4BTzWQzy8jl0slxGZ2+XAwlMnjYL7aCPM5iZNECv19GxRNusfMpK/60mef+93NsUpvXE0TvIGKJYVjh82E7eLvHzVrwIUcj1siqUVAF9HMMZbmJKtWYwnxSoA24o9rzZ8zV3JBsGSdnHfTGOd0YsYtENSNTomYTqnVyXPHoYeuGJjTe7NN0hLt54kKF2LairYY1cWoiKqoZ5A1uR1ZfhQWxejE0HgLz5YC4pmtbh8e3lHW8s9Prr123dvu+PtLI2vznucJHxhSvFadqdoGmxxVrYmxVrI0x7FnzOPrbbXVX2uZnd8vuu6iwt/vvnu/WK3yrSdPZ6g7xzLlczPfudTxJbC5llgT8bBRDrChCIy3TKPk1kO22KI8nnPy1Nxc30O+yi0pHsL6e3rd3FSt22Xyoi6XQwnDSgjGHRG3NMbJJMYdxzNty7xStSJRmiy86prfHYSFa/qVQN4sXKP1qY5G24qFfm3zRjM4p5Bg2zCCYAMjDEUQsuORtzZf1qo2t5P9SJ1JJxrjTBOkzRYsB/AsCFNVuEadIElVR+mqynx9TjztUdNVADMdmVtvscWj1VLp1tAPrJvIMBw3Pfkwh6GtzqCqrcOp5KfYKNCJ0xkScBNSiarEwO9+//uDT7T1WTWVoDWQj8Fv7rj77m3yPQWPpz2KpzsYQ3iUT6eO/AlataI1MimcJNNZx9AmWIBE8aBQjcqyfOky2XTDja/81OLFK8k3XWTyGvmzyd1IW5Pxk1XTVxzyqt+EnvdMtVyRFBtgTa3wxAc7HKeaxaanWW+r2EeKxcuv1psg2pSggMz+WTpK7bwrrrp8Vn5QjvJXFW6846+b+bn8Tup5miQWw8xzi/NM61OF8SDE1EM84EC2xWsvkb6ewhXf+shHBpHd1fXYo9VdKpXqDkGYUy8Ihd+ZITg3KJBjm2G34DjwQ7xCQt8vH1wpaVyVtFL9xzHHHHN3pzLPOPdzQ2KTPxlRyxMf+iWCY6tZlm0mTJJ2MqyVHE6z6deosyj6znhm7rw5R5x9yy3+JMVXSZaqoo91dmRbbG4gKoU0to1A1F2d2MkVWEM3q+zlVBL0E/VnihCjo3ZiW/ggRhUxRsQij/HZhKo6caq10CU6uKmOlVPVUd1VtaUU+MLWGS25/7mIZjrNGbz99qex6bkBx8dlGMt9QTGKIvd0OJ3yk/HQ+XHjw5MQOkSe/BT6emXOvLnh4PDQjlv+9rfzJiu/hvN0YO7cbWNs3qg7n2b5VMfQUyM9+cKk6tH4nGCcbBMYmSEqxWJRaCM60Hk47cEmKC0Xi1dP4J+CwLqUs7fOR/FEy7rrPGsiGM4tuyeJ44d8Y0RV4XsA6O0hLi0+bEMzOYUD4zglsjw3w0FnWKPDYSONVyU9K4aHd73wyit7M961MbzoR5dsmqTpRpwrMAdO/UKBhUZVrbVpNOkirWguo+HGcWXUF1UVTa1w/Koqw3TewnWukC4/qFuvv/aGXVJP1185NMgTDvE96Ix+RZ6rj68yuxQ/WqxULYkJjBT4X06EYWqT9M7SypUPjDJMM7K5bF5JovTvaP8w56/F2OBmZari5JsMPOmhb+BpNvkokyhXcOoTpzv+4YIL1puqjtnOpx7E7MpVEUxGXMLxWfMroPEbV7Nb0SqQRq2hPvo8s4uqCjc3zFFVN15VayEVUK3lM/5chKo+F9WeNZ3NdCTxz0KPPOzQv/cGwQpPrfvOiWcCwXo/neKT8tCRc2GvDTgj/EJrhNc7S5ev1MKceTtWi8W1+VecjfXM9oPDw3iiq21yqnBocJ6SJIn7YnLWeIU3MNYIhxs3eZhmkmaZWMIYrdFTIW+KG55EpKevTyrlSGJsNPmz6r7Yexf0999K/k6QgtlNYuiB6Cq/WFc3lZy9+KTiNptu/mvlaY9Na07UKGxlYDIjXJwJjpdG8PsYTLNO2phhzZ6MTYS1idA5V2zqLVhn4R4jUbTFRK61g3Kftbmypq82hbDg5ULh+OK8oXaKMcWwG3A84phM3KYSjpCvjVRVMPTEN+aeBX3zpvdXgy0qv/7OO+fddOdt+4vx+gKcdoR4DRVVyxjpKh5mQcoBiZMPmekHMtzmDZu2pFSu9ofB9R9ftKjUqVhVtcd+6AN32Ch6EEdpArHCv0KjHNpDEeF4YkiIsAEgSm1CuRGKqONBWMvB5hoG5uaHY5MPQuVyWUqVsvjox8T3+pbH5deSd7UhxeqOyqgndaq1BYQuLovetIo56oTUGz0qx4zG1vaIMRiRcAbUOPMtmc6WAwH+x2DUCtrrISSYr6oMHJwtkM8wVfY7RshYtgjsJIJp4RulAAAQAElEQVSBL91/GsW1k2LBRGT5qiDUE+xz1Vo6rQX1nOdfYKbb5E1zvdf51cr9dJKe52Haq6jBMqyUkOJWg8WCMh4WfqQ1EjiNFI6B5+qchHg/LxJZMegVP98jOF7a/L+++U3+ivO09YQiq+26+Prr/YrIZiF0pfO1cSKhB1WTGLaxwmN4KqNYnAzgpZw+iukBo3EUYkKlSAnymFQrmBkpbrFkDiVOE/cXTnN6+sTHKw6pxtec9LnPdfwruqlJJU4i8TyVWl0GNXsuLpN8VFVUtS0HZRFtGbrICCrRlQWbVnyU5f+qi0VfIuig6sEG0DuGjZIU+lsxMBrWLLgj62CwWfKkFicd7kdqtkyFjc3iDOGyJQk9GUmTrU/57/9eK//jSJhAbrjhhlyayx9YspgYYYgZY91/r5BWMfrIIAZ3g3mm40B7WecFa/kwgOPLQphOQsxh/g5OApagt1CzFTbZ+TT55Re/8pWuX3P95i9/2STO5fcvJpFabGKlWhVs2YRzBEqIcMyjbuqSYqFoBumNUPA3w+UbT2KMhzlhQYJqPHjQbntc6eR3cVuvZ84DYTW+x6RxGluMrwL8G+aoqopvPYwvD0MI44jeTy2qhwdzC1oKurhXshmfYKxaFUmtFWb6RiTGxo8bQM/jCDUSGyN/e/ChV5500UVhF+p2XMTzPauqVMrBE8QhhU1B0PIysDshGGPWqmRgmgViFIaHQq6g/VaQJHkUnMOjibU0YqynnAN+IlLwAlH4Wa5HPKlTVVH0JWEwAjJ4iFtMRzW+wBVJLIpRYSRCWQMZXpjDq10riU0FZhNV5KcxKpi+EVS1JTOpBjm0NX0vN2tIom+sA9SSDGwHQb6Mx4UiKoGs+s9aWgPtNy3VPv2BDyzfYN11bisPj0jg+cJTGi720yo8TSZ2JCGYbCyCzsuJ7+/2D5Ec02sb/udHP9oCU30hBzZ144DMwHQjFG1SCwqeTDkQiRRLGChtrxROlXwGDnIEp0pJNSp7SXLLHhts0NEXN1mBtQlVY9RNjmwiOMIs3dBfNUlYLGqR7u5vfutbH46LxXvUJqKqkmCU0nQC92qQ9mFwT1Rom1Y1NNIZJ1Jr3SJEOaoqqiq4Ca0yHFX6/UJhv5utDWQt/Hz/f/5ni9jYTQ2c6VBxRLzAlzSuSn9fz6Tast2TMiAzjWPp7clLCScRK4ZWYF77eI3mD1eHRm7mbyuBpavr/B/9YIfEk42twM6QwLFvJK2nQEBfWvTj6JghqQvguUByXs79LpCWq/d5W2zxSBdiXJG3HHbY0HZbbHnT3L7eCqaccOGzLkfcgq6Yu5J9MDeFqKfZvkbUyYImZtFxIekce9jM7lBduXL7cZmrKlH74ZasSa6WmfiBWt+lkEMIehQYJx1Zz4EryOWkDyfrXM+q2KALdjKu/7Fp4cYlTlNhHudTDdjw2lpDOUZCPIy4Uz0V6enpdd/xLJUrUigUhL6bJmA5Fy8xNT2wzPQ4x7jYJ92UG5Pw/IhhSZl+QxfMW3A5jmsr/J2VarnkBkNj6U4NzkmHseKcoXMaDcLoGNiJxvf2/8xxx/U3ZK01US/0Xg5lPGDSi3bJMCljPZNtJ5jkZOHk6seE6iv03P/RD3/gVtUGj0umKbDwmmto5gkbBeo0RdEZZUP3mnfoUMpLDz102Ffvct94eBYz4qsRbngEC6eoijUqHBuT6Z/lZaE0fVRVoJ8bw3B6CnmHnPHJT+ZlLfwMrVz5+jw+dL78a0q2iUsNvyw7U3Ut7DA0PCxz584V/sXg8OAQNhL+PZ/45HF3qmpX/Uedwlz+X/DK2me8pq+VBIsFN6BYNkbHokENrcByBMs6YATbBjCP8HGCidHARcaus3DdP569eHFteWdmh2B7t9tmy98NrRwc4pizWABRpZOSChR1sfE3lBlP6CDF9vi5YL2fX/HLvToo9pxiTVL27qjKa2VkeWlQlhdXSoRT8Z6BXkk9i4P1iuQKIfwMel7Hg6+EE9AYBoEncVRxSJNIYpzC5kJf+F91DK5YjjSGI3bnUVQV9bDc1r4RIW0+VjUbcW04pknmnGlkbU7PTi2NNTy34uiJ6Sv80u12/sPw8pWPx3hH7RkjdDjE9CVM5OS0ICbmiFj0TlDI73DPI49s1Sp/TdKufuih/BNPPHUIdWynBwcb0S6fy4pBJsE4oq7NDLEQMxB+J2AAT/YrVyyzxcGh+zfYYNMHXUYHt2cOPtgq/rFIpk8Wkra2gScNu+60y01JpTpoMMqIRh1VVVTV2ar1clTjZhtVtZZocaeN+fMJw8USZe34yJIlG7RgW6Okj33ta4UVg4P7UwlufLD/EX7hnWlVdXZQrYWktQLt0JKutTlW6O0Rnihy09OXL6TFwRV/X2+zOQ+1KjMd2tEf+1jh2WeePZC6tqubcpg3FchHtOJzfgOnMAxtNR5M4vhi8s4EoV+4qzcM/xHjBKyQD7FBS4DJRtnktVHvdhyqKn4Yznl8yZMvufr22/va8c0yHb0+yxKf4+L6e/J2oK9XJI6kgoeAIMEpqOeLLRUlh1PnEAgkkRCbHQe0l2EeA89LIwmQ3wf+efmC2EpJklIJr+QjmYOTpAGcBmmU4GHCSGlo0CbDPOeDgBaX6viumWzstCg+gTTT8hME/hMRTCdtOfEDHyjnA+9yk9qkP98jgfE6Kd6WV+FXGrucmwmQJEWJZStX+OWocpS1pIKwllzX/+53uy0fHNy5nTrQt13WlHS2nUwMLd8Lw7kPFHqLe+6+2+/evP/+K5i3tkNVJVVt7NZpq6w4aThq0RtulzT+u9rUwr+4BT4TwJFAZOmZhFU81eNYSXK9PTmTD/91JrJWRdkwl9ujFFW2TXDsHkWR8K+DBgYGBEdgwvkx4zpxesaNFMfrAE4VAzVD++619x+O3uHgkW5l9xYK2/X2983FlmGcCPZZqthsWY5sEUGum/tIZiFI07ugNxkVixS/12XE3vyORYueJG0m+PrHP17yUr1sIN9j00rEr+cIX2lRbwLqO9pUtqc9pf5pjNdJo0GpUtGwt3ffH1xyyeajxBciq9cC5eqIDI081ZvIsr44XdYbpUsZFsrR0p4q0g52eU8lXUYUonRpT2SX5qvp0qBSXdbvectMuby0snz50nlBbukc4y3LVePlfarLvUplhZZKy3tEl2oUPx6EcDgtWqdJgmHSMDHAAz+I+9QX507GRV/ZCo4H6wjHL5HxP1/DjjY+6Ij45BM+dxHOr58ojQy5d5noLfdExLCVEVHGLVptQzq9ekFE6zEROhmrRgbmzZVlw8UjP/yVr6w1joH/P9fFP/vZK4rVykZpi1HUaAu2e7RRLSIckASzuDDQBpTJkLT+/n4ZxpGpZ9OnNlp3/R9DXpbF7GmBr7pw4OM0RXlXJgtdYga3TE4WNoryLFvUSJl+fNPYezD0gt9gk10xMJAnVtwrLoSIjI6pRlu3kt5Kr0Y+li/09svyoSFZumLlUSd95zvrNuavyTjH2TW///2rBodH1sv39Mm8efMkjWLhX3RFWPC9wJfuLVxrWTWOJd/bIwX+Hk41knik/PDGW21wGezW8TirSRRR399npFQ2Cb/ULLVPpqcLjY7qjXpG+7JVvFZ67J7xZJRCmBOJk1K5WP7ZRm9969MZfSbhZhtveGm1WHoKm8BJxaSC7ZabVZOytc20KB/ilCDoyW9/xZVXHtyWcZYyYLsZaNudEp6hN+uu7OoqdernT7n4P4/99F6feufi3S4+89zdfnXxj3e/4LRv7HbV/1y0+/9d8IPdfn7hD3b76YXf3xVguNvF539/94vPu3D3S8+9cPfzvnHGbhv05HdbWOjb/ZtfOHX3dfv6d58XMN2763yT23X9OX27XHb+ubu+561v3n3Duf37fOAHl7bcnFsP72xFOu4ftfLCpwsLmE7LDOT7HvJTuc2kkvb25DstPo6fnTZZT7NPVwwNipcPF64YXH7AuMJrMPGEyAYjUXSAhv60DACHIxkmqp2CRCDAlSqcKRwinzKJ8vCQ9BfyEhrv19859thnwNLlZaDCeGuD0KWs8cVmSc44oYccckj8hsNf9xuJ42cNn1S0pnsiVlKAzKq1E0duXphuhXZ5qioGr2tjLs5GxS/kZOnKwU0fffLJtWacPVKpbLhk2TP7zFlnfm5kZESKxbJ4nieqKvzjggSnQNLwUa3ZqIE0Gm1lB9qSxxfVKJJhbPx8cK8z0P/br7/9ox39OCaKjbv+seSJ7fsG+g11bcywUI9zmiBdFQREandEcDmfAIYsBMldqura7RK4cROsqlIqFjE3zJN77bbT3xepJsia8XXqf33pidCa33sWA81CGSeRc5RwCdzGXKeqIj351Wh/1TF+2t7P5/2gv/9fT7R2TOjk4p4zudhXr/W67rjuusNvOvTQxxYvWvTonhtt9OiOPfMfPWCjrR7dcf78ltgT9Ayv3GqrR6/9/sWP3nLxxY8u2nNPxL/v4kw7II+yPrXoPx694SdX/GOyMYoxwmvUXqpj42SU2BRR1dq8SDFOAQiQRjSxv5CsW6DjibbR3nsv2WW77a8vBH61NDwidFB1WRMCVZ1Aa0Xg0VxGp3PM4gzxCkLKadR39XXX7n355Zfj8Y7UNYsL/ud/1k2MbqPGE1FApv9RVTdQVeshiirAdvPZCMNXGILkbJvDU72mqcyf0/9bxSsg0rsDZkW9IOTUY2t3UDXh37w4fZBjzCitJG5S0z60k2qNxlZwsjNsBumNYL6qjvZBIZ8Xbir4xcP8QG//r6++eueLLrqos06l0FWAS376082xIdvBbc4g3xMVT40YhHHauAhL1x9ufsKcL+4vNTGW1+mb+3OdwTg76ayzeu575NFtrFFNxQpkOVBBxhkSik7FJcrEFGgsR9YsrZJKXz5nk3L54cP2PbDjX2umrFYYmjdvROLqdXg1UcWrVjfmOD9b8U5G47ibLJ95Hk6sVo4UxevJ7X7zBz4wh7RVBehjV5XsF+TOzALoG04Fwo23bIzPTGrNX85Uxj9jedNpow5RjXd50Q634kl8Reh7bYtPt+PoAAUOLBOEAVDreKxuKZw7/3M/L/C91Pde9Gyvt2HGt6ZC6Kc33Hwz/8+kTSK4Eeo4mS7gd+1p5hmjcwHDEoEnS9LQbMfKuKSxGNgg55mn5vblu/4/k/jl5kxPviZh3zBNuMpwY30ZkJz2lZVhOO1C02Q844MfHN58s83+lJSrGCJW+BcUnudJhBMKntYkOK1hWzK0EpvlkZ9gmnzUl+1PYiv8s9MYi3SsNtSeYFfZfPOF5FmTgH7m2r/csKs1/noJZinbTd1Bd+OJbeHIadaRPI00pgnSsrIM2XaGYhRTORbDsVyqDEqSdP2jhayjZ968bYN8blNs1pwTp56s36pKgjHeOL6tTVjEgcwGPC6BG3Uj3OYIuoE0ejk69/FENUr684XrPnD00U+NMswwQh/3kXcuviuw+kyA8SbwiJL7bQAAEABJREFUT85eUJL6WMxJplkNdSEYJxgnGFdFAUbqID1DnQRzJxKEeamK7Y9y/msy+qoIE02U9Wey2YbGNOlMN4K0DKoqqjU007J0c+h5VptpL6QnWgB9kcKfWeaoqhsX7AemJwN5CM5jQlVH+0hVna9QrYWOD3EwuL9mnUzuP3seXGrnTeypVG6oFkcejKoVFB7vflVrhkfGtC86Q9fjTSUUab4Dj3Ckb8Lci//81zu2A2lNX2rywWFYjDwvHwp1n4lCXHCy8o02oIPF60SJyxVJKuVff/PkU2fk2NEtjeKzKl3oJoSLrX03P7I/XzBnTiWulqVSLAknbW9vLwLtaPK2bWOSSqVUFeMFUooiVT+385333L6lrOHP+ddcE/ph7lBsyDBEjKT19UPTWjeyPUQrNVU5c1rltKbB4QpetvBnAx7acccdy625pqZCH73ngQf2LEXVTeiEQ5ymtSvF8d2ch/LNJNfPJKrqaJxpAoaRpFyt7rvXXn/S2hMUybOCOX19d4Uq93CnwM0bgTqcbIaES3R5Y3nCqC/qGangIeeeB+5/zYknnuh3KbLjYqoTbdooRFUbky/EV6UFGsZv4zyYqkq6BdX2/aRay1OdGGpDnVPV88+W39XG5zMf+tDSTTba6IaB3j5pFABDzsg+rhPh1+kUCQrj0736nsRq1/n5lZfvdLW1q80xsP5mnHzxxT2J6B7qBzKMTUlz/szTYxb1VKUvDOO4VPzrk+usg1W/e+l42K6N/O5FdFwymYWJZcvlB1Y8u+zB3kKPO5mxkkixPCL8r0F4UqM6/WY1OxQunIHvSxiGYvh9H5z6aM7f4LsXXrAVeKcvuGPLTF3gsp/+z5zY6EsiaJFAL+gj2P0IHuGEmx+miXaSVFGwXWYDnd8VKuFVS1TCQ0yU3vfJj30MkQaGDqLX3nNP329+/9vd8EDQN1REH1XjcaU5vxsJjRpi2qOVjbljcVUV+oNGZLbo7ck/Uxkq3TjGPTuxrQuFJdWR8p2SphjGqB/jg5KNNfB5Hk7IDLpCSZo2VFVUx4OFy7CTny+I5oKdci960SrbdHvWo5lHdWDd7aCq7bJeoK8iC2gX/hJlpHFe8UG8GdZojQfhqOooiKX0edvJZtQQHUbmzR341fJly3B67eZSy9J0zJMhFSsEO45oFMIeMeLBuVhJ4hTH5KmXGLu33HFHvpFvdcdvue4PrzBhsLCSxGI86EdFZ6AEB2VWHGPRRY1lyz3xcJhm4+SRD777vTfz+N1ldnlTjP1WRdk/zfRWtGae6aRn8lddmfzv/ud/DvWGwZVRuWKHhoac087lcsJXP/xPLml+VXX0rEwnYd3GUkV/auAJNhs5k8u9+v777w87kTPbvCNVuw/G2PwEp52Exc6VYD2KmwFqFwZJLTLhrkrOCeRxBD5Y9GFTqXjtlBTLjwzdL+N3K+O4J0/8Y3h43UjtPhBg1lt/Q+FJUrsSU2mmqqN9ynZnUFUnUrUWxqXyDT/84hdn/Sce+OX6V7zs5X/EJrPIulkpQ8LA5RlRQZ5wM8a8TqCqjl0V/gO+LRcEkmJRGq6UNznnB+fthzpqDI6r8TbzuOr0REMHIWZao3axmM+0zudw+Qmd00kfcMPTru3oh+YsmxoT3Hefzd13331rFLfffnu4ynSw9+VutzZ0QD2wp6Eh3I2RTnHYvgf+OZ8P3Y/pQVinxUf54UMkhVMfJSDC3nfOBZkWryJ6+/vwnG9l5dDgIZ/50pdW6RcAUf2k19KVgwfjEdCkxpPUo6aTsk8vE06vNmjRHdgBcpDW229NVL130/U2vmd6gibhSrtx0ZPIW01ZW2+9ddVXvRGbnEpfb8HVysXaRZputFsTaUKycayy9/ifv/JPovGOXaIkES5AeFVzyHu+/OX+CYVXEwE6mpFy+WjxfeVr3iRN3SJEfdmLBFWZTnvJNxnSOBHK0SSNc4Heu/XWEk3GP1neZ//z+O01CHcQnNA+9ewzIhjXuOGUCuO6RUGOcZIxzRm0Bezh2u8Y4CuMqigSKJ/09fT9WlbR4tqn+gfo9gzr5yaOYwTOanSzo0otoMg0LtUar2otzIrkcNoomPNJYqXQ2zeQJvFLf46Tsyx/FYRo0iqQ2kYkbDe+wW34nu/kxtcYsNk4czBNjCPWE1w3MtRJwg4mMC8kQ8aDoSYE5mYhDvQ9+37w5Sfs//73jOGD7/ks0sC7SPvsvu9/Vw2L33XCvo1opmdpho18i9+Bchkga3EjSH/XCS/7fx88Yb/3vfv4UfkNMqAL9WgCdSOo6zs+uz/qOBBya3jPZw9cDLwHbVr8nhP2PujfTzjwwJec8IqDX3r86//f+z70xe9+1/2fjK09kkz9edlb3lK2cfondIizcVZCtfNxnnUKw1E5kEoHH+BpaHh4WDzfl3U32HBunFTW2BecT7ngggWPPvbo7uVqRXKFvFSjRKx0bUIRTSX7qNbspqrCdsOpQzLOe+Lkdn/ZsmczvudSiA0ienFmGisWtdccetjTorICcalWq8LQN55wMZIuPhizowtpnt/tGR6RnJ+TKjYBlagq8xass1BNssa+T3bymWeu88CjD784xoYHWx5s+nFcB29FvXkaKDgnZbOZJhjvFrShZ4ykcfJspVJ5GLYdG5QdCo2TdG9sHEPqXOjtca8Q24ng+G7MYzsyNNKzeGPeaDxNnozL1Vl/zZXV+Y3PfOZp3/Pvsjx1w6bY4iGMeiu/Z4UNWMbXSWgby0EONvTCjRwGtawcGTKxZ/bCjnuV+bhx9bdRnDwZ2rC8QJ5tC1hMcIHrtzWXSftL06cVrYkF65FgKGENURV+sjKq49PI86zRd5i+vhNkoO8EA9j+3uO1t/f4tK/neAGdIfI/g/hnkH88+I5nmPGB19FJI18d5HHyQD9B+/sbAPmsYxT9jg/yPqv9vZ+FfJdGfcd7c1CO6O89AXqcIH09DWHfCba3Fygcb3v7nK7a13c88BmDNMLj7Zw+tKvnhMK6C4nP9q678HMVz3y0LLH7XyC6XrX53wrMndtzOQw4AnR9ZZudrIMoyBMVU+t/4VMW89QzsnzFCtMzp9/t2GQNfPzA7JXP925pjC8RntByeOWyqtTg5se3OvzaV7/6qkWLFiWrqp7ngtw9d9vtGU91SeNJD8eFwYLdrL9qbYI301umsfBYbHZoa+bzuz4B+vSpZ57xsec4grQ1gapUduvt61svwgYnFSOqOgrqo3COnBME01nIeKfgGC4Wizafz9/18Y9+tOu/6DrppJNCPAb8a5ALZXB4SKCwYCMl/ChvLUC7W9Dp8jMgOXqpqnBTwPIEdqu4rAP7P0nSv5zyxeNn9KV/meSjqjbvBz8Fi02w8UEoo3rAcRnxSOoY7K8MmdwKxmH/nDlYuHSbj3z8I9t0LHT6BTB8ajZkkUyPxpD0DI30buKZnBfCyS1gPY9Di3Dje3LusVw3f5DMQkTdheEpBBPsN75VIQ9pmKckY6yZOnxJBWdOGuBR3IViNRABQMc09Ul3YWI9F4LOMgq+ZriyoLtQTCiTgXyspzFUlMnSqE8sdGN9DJlOrce68UAIvbEWJx7WY4SR8TXxPIkJNRKrL1U4lhJeJw+VI1STj3r6+1cKPgbo6qJTOPGTn7nHT+39CgkEAndhJykpCIQjtLmNz09HNztkz/IMjs3V+KJoSF/fgETVCvZc5Fi9wOAxt/79tp1jtfM9OPc4jt2mbKZawLeOE8EOITw8ZaqVZ9LU3DyOoW1iiozmiqZgR3un4JiYnW1WoffEzBlQ0iRZlkTJ0ziVkHyYEyOKjWcsGIMtpbajNzNjTmByWPECTBB+UR0neNVyGSc+C+Tu++7f/xPf+x4evptLrdo07O499Ohj+w4XywtyYd61sdaetF5xKpgpzjmCFzQDiEu7SJtbuz7hL0EXcoXYRtGtOy5c+Fib4lOS70vKu8CeWwwVR2T+OutIGSdnfgDnWS9JLRt14PxOQESZOofgcVcmfhSOBLDIcbBctBPRNKlqHF87b+fqMmStsivv658Dq8tRX60ODPIUOmD3UEtPcVdV14ft2PJBKFGlKgyH+CVza/sGo+pR7fhnRo/HFbcwPvuhkcgx1YjGvMnj6bhsi6WyWfY4hhcSEyygdR+NIebylAPexcZu7Jux1MQYZEwkTkLhGCBSjAWGFt5VgCwU9TB+PWFIOkMFjSHBcoRFZ7cKxRpsXDjRW4csQ7lZfQypB+kMufYbrP+si/U2psV44n5SBro7fjESiwrjTqa1UsEpLf9wABtLSTWNkjQuCj7QCPdur6o87lejO+NiMeWrB3hftNMT1CVUkApY14sp1RmFSFqvMRVOEMKQZhOhDGam2AAnAJ2MeEaqWJhsFOPEa2AL5q9uXHbjjfOuv/W2XWPP5ItRRXxYLgw84Vjl+GwEiNKYZjwV7LPhDNhWgrs8NUbQZ8KTDFWVAELTalUCo8KNT28+d/0Zn/rUCpmFj+9jp46B4GE3zKdlg7oplvoLbd8A0jKQZzJgvAuhqo6NE5NgwudtFgCbLPej5MkQhvNFsehZ3D2Jcepmm+SzbiIjq4K/DQR0CbHpSRPBk71oNZYQk2yQr1YHejYqVUdelMlZXeFl11234E83/nWnMNcTYshIgKcdN4WgAMcQNt41e+O0QTXAdFF0HyDGxdkXBIiuBNyAEEatOCClqsL+V1XBsBCTVEf22XO3W/iFXunyc8+DD73K+KHP8RXFVeiSSJRGo9JMatAST3zriaoniacOqRghVFX4oa4ZLAwQo28E84HzhCHHZQr5+cA8/aqXH/j3Q/SQmOVWFd7xxrc9G1ai20JUwCkzgrptzrj2pUmtfdStETU9VVQVpSa7UlGxEnhGqpWS+L4vkedLHOYOPvqkk1jlZIU7zovRAyzEPkpRr2qmH5yZ1KDom0bQf7cD+0I1k0HJkIq+MjCUqgouEl/ANC0Auyk+sJu6+Zn5sWz+S/3DNTGBL4e1HW9WhiHnPlFnFYv+yNLMJ51yuQYwhEuVZqSYdxka87hmNaYZJ20yZHLahZTBPIaNII1IbCwE441wvNgvGMWK4MasFYUnEYAh1094GjGqwv0IbZUmJvaLcYU24Ghn2BWO3mef5XN6+29YZ+7cIhcOnoJw5xdbkRK/B4PXBplgtakQWZohnQVDZLhAoDQ7mR0FEegQUFSEE5VOgUfnDz/8yHYnXXTRrDuFugJtgzhJNizF0W4ahDqAI2nqFONJrW2BaWRw4JEt35NzbUyqkbgTjYTO0E96fG9Gv6JL2eOR1pLYgNUik98z/Sbnap2rtjW9G+rbDj10ZE5v7z1pFFXLeI1C25dg+3xPAeK6H8JunHlYxHyDCQKbixFPVfj6Z6hUXOc311yzL2ygqGS1XcOVdAsJg13K5RhjonZiYjClpd5nY2Y1NX+DPFUzqh/0HY1nkVZ9kaJVXLgKgS+2Gj+9yYJ1f5fxdxp+5Yc/XOeJJ58+BHILsREAABAASURBVI9TMJ9Kkf+NRBi6hXxMX5FGPUhPoIOFvcV9xtrgkvVbgldMPk5YE7FSrZYlF3iiSWKxGX74xVu+6I462yoLDn/xi1doufyHnBekVTzwBPmcxPBlXhg4+2cVq6qo1pDRphOWy0WJ4StVUVY8idlOsZsWly3baTrl1wYeVeiODlVVpw7Hlovgtkp3pZD/z3Jh3jrjIRzXpOY5k2WqqhtvWXo2Q1WdtjjqS3Bj0Sq0dVHtwmlX1CEj7ca9hGJOCT4Wvj2Jk1IpTZ9BEineu4Sq2te88tAbVy5fuXT5s0ult9AjBrv9fBC631yhA5yW6MwqTcxuAhmVYRyf88vEc+fOlVKpvP7gY4+t9tdd/++Tn9w2KOQ35RE+/4uDxD3tpU0ad57kgKnilCeKIleYcivVEpxh9fEDXnbg3xxxNm5W6kNwNoRNS4ZVzoRpsU7NdOjLXnZTzvNXDAwMuO+OLFiwQPjn7VOXnJyjjFdbtD1VNb43evqW6yn0PP3s0j0uvuWWgcklzF4udNBPnvCZnZM02WThuuu6BRZzTBqnR+tOtOOUgBycSFiHrPw4GaqiquIrjoax2e7L56778nHHdf1dmVvuumsHPwy2CMNQqQh9gKq6fmK6FcjoHNN41cexMoubnsHBQadvX2+vjAwNy0Bff1pcOXzLJ48+uutXc+MqmiSxzTbbVPbYeffbJElX5PxA0jR17WIbuflRVafbJCImzerr6xOOO/YZ/YCqk2dWDA0dBZpOWngVZaqqa5OqrqIaVpvY51RF6O9x+qqO2V9VR/tEVcfxrYqE6vTqoM6TYVXoRpmskyHWGAZt4fkqPJBha8IwSHN8kgK3AWZ09cTxnYHqo/PnzhH+tUOCpyJWlOK1FBzhqOxGx5sRuSuTcXsvI3gPl2W7kA6GT+ClUknK2CD4YTDw9zvvfInLXI23uQvmHabG9PDkKZ/PO2PyB/Smq4KqtmQNgkAsdniep26zaMDXn++RNI5vfPOrXre0ZaFVTMwG1QyrUavautFdCA6i6IbS0PDDXPg8Y6QclSXA07fI+M2namdV0v4cp26RxasGzgtu2DHuFBvdnS/7yU8260LdrorcIuIPzO3fZ2D+vOCpZ58RHmnbenOoXya0ThrnCFVJHW+LUX6XV0tl8lRVONZC44mJ099CWGMVMt3P1Vdf7d948817i+9tVImqwv90k/OjGkeiHuezyOSCrRhWlia8C/XLQALLeugXbjqMqISeL5WR4Xi3XXa8TvHgRZ5VjUMPf9UDeE34mIeNomK8ccxQrxinUdS1m/o5x4hiGQ85cSwGYxrtEcrm5uqRxx596anf+c7cbmRPVYb1ZjyME1maOmTxTsKsXHPodyLkBd4JFqA9iQkZILSjI2tWrlbym2lMT4bpKMLyzXytaM08WZrj1yEjNIT054onLMrDg8XKHJ90kW+AGV0nfeQjg9tusflvPDxgVoslsXihFvDVASYylWkU3s5JKL2IbVQlHS0GZXHk70lSf6fp53N9jy55cv+f/elP/aNMqzjy3ve+NxgeKR7C05kYDjo76h4cGZ5WzTR6O8bhYlmsUeFrs3JpRAQLRlwulUOjV9+3+eZD7crNJr2VflnfMcwwm3V2KutLn/zk0LZbb/3nvlzBLQ4rV650r1JayWF7MrTKH0fDKyQMVXfSw34Nsek0vicRFiOcvGyLhX21/Vn710/+SGGkUn7lsuXLhSec1INjg6DOnCYMCYNNgIJgoT8hWJAdHTRjU8Fe2gFJqcEgNGRxMNaIArYSPbr3Xjtf44hd3LyNN55XrJZeWomjXIzTEFUjSYz6Eeci3qlI9hv15Wswfs8vRj9wU1DC3CiPFEVTK3njD64/Z+HvO5UtXRYYXjFyj02SO+NqNfU8T0zgCzd27B/qS3Qp2hWjPLaRJ49RlEgOY7BvYGDLp0YquzmGWbuNf/GU6Z2F3VQzWVnmJYr39t0Ifp6Xoe2IVmYgnWiVhzV+3CvY5nSrMp3SWHeGTst2wz/durhOUT79R7bXoP8IPB8PVyqVUmnJxz72sTJ5DG8zRcEzV4xgJZrT3ye9eB/PRTzl0xA2K5RNJ8xwuqDSBPnpPNlwhl4QynCpqOWk+uLf3Xz9avuS8+C8eXuZwN+UTo86ZeCTbRZvF1L3dnmks138v6co28cGqDefk+LI8MO77LjzLYtUE/LMCoyzKI8Fpi0uG0hZgeZ0Rl9dIdb4n5WKI0M2iWW9dfCqa3h6G8/J9OP3xthHHKM8rWA8DPPYbPuAl5+zcN7Lzrr55mAyGbOVN/R0su+cuXM3CHJ5yfXi1I+9pSqcyNSvVT3skwy1/LQW1O8sx/x6cjQgzWATH0TpNZ9438eXj2Z0GPnDLTds1TMwsJcGnnCzFmD+8+SHr6j40CL1D0cfUU+6wDUPPoK6kMD8rK2MU3fKCcNQiP6+HsHpsnjW/uRHp5zS9as51tUJPr5oUWnTjTa6OvBMOQgCMfCalbjiNpaZHFUVVc2Sk4ZZe8nENvJEiyfJuVztu37FSlmefOqp9X712ysP4K/akm+2YC12jg3CVKenc0ORCVHVmgzV8eEExhcIbS2gLU4vLeZGqwKkE63yOqXNVA70duN+JmE7nTOZWT7TWbxdSL/RmJfzA+HbJ9I22XCjZyGDLgYbIVJmiH955+I7Bnp7/rBy6VLhhiefq1XmGXiIKWTzqXUyFu7YoKzwhIqnLUEhJ9YzL/rlr656+er4f7suuugi74677voPLwz8KhZc6sKnMxqYx2iT6T6dPB5rc/FN+Z0hPCVj0xgvGBi45shXvvL26ZR/PvH8+1vecmug5k9pNXInNIWe3Eya78pyseErGS7a4hnhj1PyyZv9whUuSu2/XHr66es75lV44+bqH08tefNwuexhrMnS5cskwXhIDTYy2PFx3GXVK6ZubYkhBfnSCBnniOjYuLgSkn249mHTo3H6rG/tL3Zeb71iltVp+P0f/eiokUpl4xgya0hd/cb4YjlJmgWiLdnpVJbF9tRY04wkFg8BaKYMDg9BjhW2t1IsiUnsir6w5+JRxtUU2XmvnX9WGik+Uy1X3IljT1+veIGRcXaFLo39hOSkV4otLU/rImyi+COtCR4WWZ5jsn/+3PxwVD304VJp40mFzDCT9TVihuJeKD4DCzT2A+ctRWUh481gHucF0ZxnrAiR0RURgjQCydGLckYTz7GIop1Epra1iXBOZWk+UNCfs82bbLzpAxl96p1JxjlJ+N499ij39+R/NtBTKEfFosRYmAI8GXEityrGDmimt6KhTeLhaDmCkw7z2PCAqQzZJswVyql95dc/+clCs5zZTt8TjWy5fGTwJcUKHB6eZvlen4bkIHWL4wwqpNOkw+fmLheEdOpio6i4z557X8m/ZJqB6LWiKCYUemz2VHnvK14xbCuVXxSCoIKDH7F4rTpT6Qabcy46PJ0wvoe9jnFjjnQkJLJ23Xx//8tmWs9U5Z++9datly1fsScX1DLGWu9Av5jAd8U41lykxQ02dhuDLKuZl+OLYD7HG50EO8XD5MKJz12f+uAH/4oySJGjM3z4pJMGVo4UX+/lMXZhuxjzFLKc/UrDI+6v4yiR9WYVZCHpdEbUp7YRqm16HC8VJAPAL/9ynvnGk5wfSGi8W/7zpJPultX8OfP9xz299RZb3F+ADyjCx9G38WGM7SW6VkdVjOcJHXTmM0vlqnhhTsQzO3/uv/5rtf8hh+DTPK5Amtalqo5PtRa6xAu3aVlAtbXNuu2LaVVaZ2Id9ehaH0zUteY76Oec/7B29IGEa3Xg+2LgaKwkQ1njTBaZSaiq6cc+/PG/jAwO3j93zhzhr+HSWVFmayWpaCqKp0TyiDSogSe9Gi0VMAgdDJ0CHn7dU76PDVCpCseQC/ceGRpaKLP1aSPn9jvu2CPX37sxT3sSWNb3Q1H1oLEKF0e0XRo/bC9BGvMyMN0KngmEPGkci0eGJFoyN467/s4FRbREqhb1NK47rl7qSrQsMw1ic1nU4eROo2jHLJCd7LnrLn+LS5VH+/AqSLG7B83Vl4WZUOo1FTj+kqgquQAbDFUhf9ananBiAVrVJnrPow8dfjRO/jLZqyK87+GHX+IX8usPlYoinhFuhlVrOlEvbg4UOwVV0BQpTG7SVZEenTPQrE5nHgGK4BlIvIAyq0IZgpNLiwGXVuNbByqVR8nTDUbiysFhPo/THtSgHvrBgxjjwNfAKSctUtnVOPho+5p+mOdgUFWUV8SYTl1fuHz4CAs5niieYPGSs1S6dcGCBav0RwulzScuR/dysx36GC/g4UZFlTojgYv6ss0MCZBG28F0M5hPwHqiqpLGVoz6EsLH8WEvKBR6l44MH0Ce2YKqcToZw34SUdVRyAw+qupKN7aRBF9qtmL8BbS3gKq66YHQ9Qc5aUuGGZrTGZ0hrU8w3i0ovxntZGV87fKnoje2cype5reqrybD1uwFH+hMiNACLMNNkBEVx5dasUky+pt4hgyzgYFc7h859e4sDQ1Zm8biG0/oGDLZVrNY69A2kBmn0rWhIG6iUnkL5wqX6HZzsdj5IyMjezUUm/Xo1Vdf7d9y699eNFgszQ17CzhCE/fKjbvIFM6YsFhoWlVMfUlnPsF4K1BGtQp7+T4cu8jCgYFbv3HyyaMd1KpMVzQVmrWropMVyto5Gc9s5h116OH35zxzd3WkZH04b4tlfabyszY0G8hikQjxSqOcJC/aYWV1g5nW0678L26+ued3v//jXl4YDhicamD1Ez8I3FjLyjROVOpLcE6lLeYVSdgjuaIcexxjfIDgKxSBA/CMkZzxR/bea68/L1q0qOoYu7jd/djDByZGgpSOBqD9WC/nbQaZ5sfpqeOZmXTtjCOYxIpJ7fJDX/nKm/bdZJPSeM7Vk8rl/Qd6Czhkhg3ZPtqS7Z1J7Vn/KR572FZxHyMJxl6MTtcweBVftzvyDG+p5TlfayG0f+ucF6hrwgJjY2H11r66auN4I7qtb6J9UrcvoDz6RfoixsnHh5U0TiT0vdF1FVOL2TPHzXvssWzB3Lm3whHgtVevVHFcXxwaHhVMBeC9RtOMOBojdVDZ1PJeJ9QDC6XpaMiP/Yak2FRFyFs2vPLVJ5544qy1ASLHXUuM2WCwWt7XywW+8X3hay4+KeXxWir08CwD59RYYDodSZ5GUB7bxc6ROEriSpn/N1Cj2LUiTh2JNa3Mv7/qVc/0h8FN2PxUPGOE46LRnp3q56mKEcGkSUUUEHEbbQRup1jB6Ugprq779Molq+wnFDQM188P9O2IDYTHH/6sYCPMEx/+XIInKmwj9WHI2eGg0BObDdIzgARetMYCrlVGPM9z2dysq1uwE0lxyoXj0+VzC4XrXGYXt3N++cvN/rHk6X1SDGCLuqhTJsbVg7rYLxltYpiCBGcl0AdAYtTujGfgz2N4xkDnmD7lsa232+K2LG91h4NPL32wODhsOVd9zn1daMr0AAAQAElEQVS8amUbMzTrQ3ozrV066zEPtiSPRcjNj9dT2OFHf/7zjqTNFEb5t3ITpXSi58TSL1BmxQJJ0jiF2ops7iumJ0OjIPJlafoSIkszVFVRVUanDcrsFNMW3oZRtb2O2YOEOF+eCn8Tr4DXxrkwlMHlQzhOrwk1tWDm95NV05cdctD1cAjLhlYOSi9OSObgtVezZNX2SjfzMm0ERxVwMC6OocEnV1XIAIaLxX2X9fSssv/J+BOf+8zm+b6+3eHcpViuYK2IhK/d2NFVvG6jTq2gCv2aMliGGE9G69STwHjuz9mxCC+ZP7DO7PzfXOMrEqzi2kyaTlpVRVUnZVWt5avWwkmZZ5ipqvaVB7/s1r58YYR/3jxDceOKp/UUhhmWYovNkIjiNVjY1zP/Z5f//ACcAOZlFXyuvOaarVMjOy8bXCmFnj6ZO3eu2wTElarQOXmiWAbH25YTnHry6UZafFiOZJ72YE6Kh4U6qpaFi7bFa9VCGNy2cRQ9Rp5uMBhXXlRWs2lqMGp1vG6ZPDwECZGlpwrJyzlCZJsntoMYHhyyavX+/lx/16/mpqp/qvx15iy4BxuxlTluJuGT2GrqmpVrjGe0VqGqimoNzGe7FZ3pAIKit62ocOMzUi55Q1HpdbKKPpPrvIoqfUHsRAt4nk4kzh5lbepn6pJhpi1sZTT6xkxuDocUwyODwt8BXLjeeo9kdJNFZiP0Riq3+apLuLviojQ8POjEqrZSz2U5x8iJX0uN3Ukj6PTpBBkfNZZRsUDVJvNy/YVdxkrNbszk8ztX03geXquJ4qnT8wLBA67w2CzB4uGZmZuPT/ZcYdWKxOXq9YsOO2zV/GihYuszi+ZRVVHVSSVqylZNytJVponSG1c+/fQzvbnQbQy6ElIvRA0Vp4wTe9JICpMVI2x4beqbILfdcC63oF5s1gKMaXPZ5T/fpZTGc/nFZn63Y8WKFULLhgHGG8YFdkG4GKlVmyJzNGWpeR0uXuPJ7lVs0FUVr509J8ODZG60e8L8b04++eRsr5exTyvkX1P+8qrf7Bz05NblxitVI6oeyiKEDgqgMlw1LTl3U+hMgMldSLqQN0dXqEKQ0ABXNooln8vF22695W8Xv+51o09tDWyrJfqGN7xheeD594Y+Tn+xKUVrha+70Iejbe1WEVUVVR0tTpukouLnC3Lnfffv/+ULL+wdzXwh8rywgOrYeJhug1nCoJyqiqoKBmYNUwhQBW+dR3UsXie1DbKxP1nYtnCbjEZZZGGa4VSwULvmccY4WbaQy4skqTz5yCNxlmOyyGyEp37608vXW3fhlR5M7XkenG0gnugE0aoTaY1MVDYD6aoT+dlINV7/JZddtsdsvQNnXRlQP9bE5EiLUeSHgfAvbEATPjHz1IfIeBkyj2E7qKqo6oRsIyq0FRa5UhRVf/3+N795payKj0VFLeSqqqi2R3MR1RpvRldVF1WthS6xim9fOe64pzfZaKNr0EGY17br2hRbG8rIBJgsUg9TMZLL90iUJOLlwt2P/+LnZ/3HDK+4//6gGievsOiFBBuImHV5nps7/PNtNNBp06gnCYlYIbhAMt0IrSe4aQj9wKVSbNR9zwiBYNg3puP/m0vqn8JDDy247c7bD05UQ1unNY9/VRUDyBSfZv1VVYyMwbUFGyJs1qp9+Z6rZQ1+9n7JS1ak1eiaqFJNQgPPVn+d19z2RhWZl6GR3hhXZSuxzYExFR5TYAH6t0SF/22J5vP5LZ9a9tSsvO6SFz7PeQtk44nhmm6Mqorq5OhEx+Y2NaebZam2rhtK4VLhG6IwDKWnp+fprbfZppSVN1lktkLfCy7HKUZkjHGVzoZcVR0Vo3AMFt6S8DwvZzyz58jC3oUyy58jFi9eoJ73EjV4uktTiaJIqnh6ZpgtRpVKZUKtqmO6TsgEQVVdh6jWQpDcxgc70if22n2ve1Th5UmcbShWyhnIhF5O7w5E2NTgKKWDAp2wpknyS2wGEpaZanKQZzJoU6basWkxUioKNj2Ck5h1h4dG9kJdY5lN5bpJfuu00zZW39s331MQzBs3Z9I0FRsnwglLmWqRhilRt1hsd1LcuTASzMd6yaAG6k7UUm5sse84dg3mJMlpFP9xv5e85HHGu8G1N/xxw7CnZ88EHeB0gm6Ug6TQlg7UgcAiLg7kmAjqJkaxBRWxqkLjOqBR3Lhhjgs3b6WR4t0Lt9vuIVmDn3032aS03fbb3lwtVwZ944nrJ7SdNmilVjt6I6+quiTvqry7pLMH3Jz7hehKHG38f1f8ev9V9IAHd2YnQFVFVWvKzOBujZ25kBnU/1wpirHSlZ1QTrRpA05ahum0X3Vi1aoTadORNV0eVZ2V8dVcn8XySWT0XpyYLn8WL1GsfeK8k04aXbDpYzKeWQnf89a33uPZ9NE0iXA8HQgnrxMMJ6iAi/MGBV0AAzBsB3agqo5mq6qbpM7pGNXI2u1+9vNfbTrKMEuRwoI5L4mNN4AFTyyewkPP567RPYmncHaCtmSnPtSxVbWq6jpXVVtlO1oC2SqpJJXo/qNe97pV979Nu552N6ww9dBp0Bh3hAk31fH61/pUJAtVx+dTwKp2dx9/33v+Go8MP8K/U2HtzX1AWgbqQ1BfgvEaam23tYSk9TALDDLyYQGbESvWUw36eg9CngfM2pWaZD8/l+sbKZe4uXKbHc+rLaoYeG6sN7eNlSt0IxgfB8wrvqRzbQdPtRqLh5MkwaZHVSWuRiJxeuO7P/rRrl8Zff9HFx+YGlnHKvRU415XZzqgSiGy9HRCtkMhy/FiXgmBBNuQViLBeasM9Pb9/OzFi6E8MtbgddTh//IQTnsej/AKtLFfGuNUrzlNWitwjLGdzHNzBv2XAkwzr6+vT1LVwmBU3XHeHnv0kb42gzoTHAOuPWuzsmupbmk2IKifGUuMxZghojCy1jc9Uv9w3BHNvPXsCQFlTCCCkNGzEKRZuVRVVHVWZFEITMAAc8QFsAl8OvwHbcjxV6yUhXMo53vlGkftDq5aZLbuex188FCQxFeaNLZxHAkrt/XnOIVCBOtSVbGcIUgY8cBRA/MJ1xJob8AH7y8EzWXxxMvfIjGeSCpWSmmy6d/uvGM7dDazIW3mF2UtrZRfUzUqBg7Zg3PnAEviqiR4+o7VurrZLpsIFEHV0FUaoGgr03h4x5OhQH20F8awgAiWJspE2/zAYOFIk9A397/t5S9fdb9PYo1a1Oc2jNa6wcc4tMdlJiCFfgSKweJ2HLjxY1MhRCxKEgiaLzWq2kycrfSuO+y5Ih+n1/JbPjaJnVi++qkmqRic0nnqi0nYQypoubixxvFm0A+AwZhTwEJDqyqp1D58WiDIyk2VRIkkUSqJF8iz5dL+b/rkJxfWOGd+5zhbNjh0qIY+6rfi+xgXNhaOsxgLq4cNkCoUNJ5YNWIF/WSNm9wGDo/wsANR0FKwYSAJGi1qEvHFCvUPMX7jOAUtFBwiia/myXm9hRt2VK120wLqHFl9tfFzmsC+NRkpglRot2Ygw10GOhJQEGkjAr0U8Kw4PTm/FI1IRDFXrIOgjT2+L1qplnfYYpM/yVrw0UrlTiP6V6uS8v92gz2EeirawZBgHDzoJxFVHYU0fcjHNgvazTkVayKxpO6fgePAA6TEGHsVdlyhsNdTzzyzUZOIrpLUOYPCxgTHewZPVLK4qfcb9cziHuYNIRiPqVjoa+v9pc4WSDh/wVlJ1eWFz7QtkPULQxZiiOHB6ChgZVi+llRVUVXXX+w3QlWFH4OQ/Sj0iRifmPu1MYm4Z+BPsA5gmIFm0G8KmZ54ivnGPhdIQiisvA5FmiBNMXeNgY+FHJ4kq6qo1iCTfNieRjSzqtZkqE4vxDwUQsSIQD8XIp6CGIsVDz7Uov3F4eI9jXWBuzHZfTwrubVI9aV77vEHTNphH5Vm9JpCuEM5heHTsQzMk9rEoUEysqo6QzLdTCeNsOTJ5fJVNa98WCRH2mzgyxefv95f77hzL82FalUwMMQNLCPwdir1j0FIIGi4Ml2zUFVFdTzIrqoMgJQLXbRw3oIHVBWWAWlVXJwFQlWyeo0oBrdM8cnakbFRQeiJIYVxholDesbD+cH06sAOCxcWTZReHZdLJYMKqRMHOcH/6NHC43rGuH5rtCp1ZJ8KJgeK4TKSjUXSXVxT1+fIlACOgK+cotRKrr+vb3mluA/ps4FTf/jDuc88u3SbkVJJEtjS1uFjsWc7mB6tR7UerbWJDs0BVLYfgbBtLuQNwGiVMMyLRQZDRX+nUXzvccd+qutfPn7PZz+7eTlN9hweKYlAJ+ogLT4cJy3Ik5DYCkLQDiMKTicbNinkwxs/9NEP3gfSGr/cl6vT9PpqqVxxC0mTRqrUvIk4SZJtJDj2aDNuHGEBjM4UgZVKqer+0i81ZttjTvj0rpOImkaW73hUVVTVxXlTHYsz3QkwtOrs6DM0wNRTghYwmqxKn8YK/onAMZA1h3EiS3cScjyRn/5DVcf1NWlZnmBusXvUE6G/SfCWhm8gYjzgk8dDZ/LhmA9kQRCAhG0uyhhfxcC3kp/yrHv6F4hLAAwCSYWfjC71dKswK99NyBNxbto1TfC8Z8VD1R4exgygUMDAZ9uoCh+uEqqOO+E2yJ/VS2HJ1x5xxL25IHwodn/5AG3qNTDGidLYoWxwPXtcADmuw1rlZ3kM/TCQcrX8kjPPPnvWNj5Rkt+hb+7AelSIdTDM4IlKRmtcULN8hpnOWUhaBtd+oy5JOXyF5huN9nnJS+53xLX4Rn2JViq2aitotYa2KjBDGvRI//Woo+/u7+l9nBsTTlh+/8p4OB3BzLe0sU63+vbTgN+N4Xe58vm8xHGsjz788Ctmq13xihXrF0vlAVXFBgVnVwgh240vOhbU19ZKqur4MgZVzaJjIWj87xUUzoqnSJrEiRG9e52RkSfGmDqLpb4ehPnbx/9Sg86ys9KdcauiTcBIsXyb9C1cdaehnaklO2/5opvm5HuqeePXNtbQsUMRo+z0B8QooSlCGxNxmgaeZ17ZlN1xUvHJCjFKZOkXwhlbYI0KoO+YTIHmfK7H/D8Kl61cJuqhJPxmnEbih0ggjkdyF4+TqrhXu3ggJK1aLcMXVoUbIm5m+IBF8GSdYJxojDPdCuTpGnj8DuHbctjg5BAGOL5iPM80TnkY7/NCCeCwopEintTQxvpl6uGsBkExfmhkePDmwPMT7sLYMBqoVkmKYKxaVTg3UHixYwjGMzSnSVfVmtPH4mbVSN/ceVvdeN11ezJvprj66qv9C3/0P7uXyuV14WwENhNBPamOScaYkHabnjGuqWPcqabYZWODiKuKQ6upy8yEQ7XWCNVa2Iks1fFl2C9EKxnt6K14Z0Lb68UvfmB4ePiuqFK1gW8wEbEQuSeR2pPHtPSwY2NR6p9UajT2MTc8JCdJ4r7cXiyX9j31/PM3I22mMH35zYN82B+GodNdVetPTDXJquNtXqO2MXgzTgAAEABJREFUunNO1egcrw5Icsz29OQlCDwp+KGExgy/5tBXX/2a17ymguyOr/OuPi9/w003HVxJ4rAaRcIN4di87ljcuLY2lvZERVWF+hdLlRUL1tvg5kPXX3+kkWdNxvMH7/cXa83f+dsgqjqqiupYnETV8WnS2kG1Pe/g4KB42NDj1O6Ioz/5yTntZEyTbtvxqaqze7v8F+jPPQuk2AwQ9IVZqKrCByusyyNJqbRy3YH+lSapDoYig/N7C4NarQ56aTSoUTQYxNVBbCQGfRsP+kkyGNpksGDMYE7SQfLl43gwF6XAWJiP7WA+TgCEUTyYR34eIfhW5qIYSIF6WEVYdWnIGC8H/IO5LL9FCLkrwzgG0kGEqIc6JIgng7k4XRHG6bK0VF4q5fLTBd9/UnEoI/VPzcPXE7MVLHrlK1dut9XWNxY8b4SLBzcKRtSJtwg489gRBJQRwmXWb6RnIIlxhkTGy5DA4ZuoZ/yRtPoq5s8YG244N0nTPfwwLARBDhsfnCBwIcTmh7o3ymfb0BxpRGM+49S9ERmNIcGNYd4PB3Pl8uiPK5E+60ip7ZhUVWotoqrjYNlOQLVGl6aPIt0IJEcvtnM0gYhNIQjhqrr+5VWvembzzTa+Phf4ZY6vNK1tAPwgEMUGiF9M5+LZ2G8ci+Mt0aydGUfgKVLOD/CEEwt/ZycVs7BUrc7KfxxpvNwGarwenMxKFa/mUlFR1dENARe7MWWoFzFGYay5LSmIbG8CVoalSlmwMZQ4qkhSra7EU9GNYOnqWrk0t+2IjXbNz+kzxfKI9PV1911bjhOCSljcCATu4qbHRSwagEiuN79sk803qX71V7/Y5bTf/WqX0xj+5H93+eFvfrPzd37yvzue/fOf7/BtoF145k9/+uIzLwcaQ8brOBchy5KPIWUR3/m/n+x41k9/utP3fvGLXYjTL/vlrmf/8te7nv7LX+664rrrdqqqfTDAppLjC2q6fmOYgba3mqUmD1XVbfIcF56qkXLR7DZnzhwnP1GZo5rM4L/piUfHFu1PqKqTrapZdbMaeoaWmFWRLwibxALsU6KRRXV836oqx0FVEvvNdHj4mFw1OvawffY95sCddztmhw03PubNh732mHe9/g3HLP7XRce87ch/OebfDj3smL222PqYQrF8TG81OfYl228PnsOPeccRrz/mba9+3THvOLQ13vnqIz/+zsNe//F3vPqIYxi+67DXH5PB5bn8I5F3pJNBWrOsdx6GvFcfATk1PqYzvA15b3nNa49542sPP+ZN0OWNrzvy4286/Mhj3vyaI495y+uO+H9vft2R73/T645YfPSrX/u+fzviiJ802qTmXRopsxTfdYedri0NDS/jwm4aPVuTfNtmXrDzCFV1E5PFVJVBA/j9DCvlOJInnn5qjxPPOy/fkNlV9Iwzz9xAw9zuxSKO81KcHKBKi/WbTVBV4UKTgRWoggYwnkFVs+iEkG0ikSG5QvXEF7n9WyedVPu1R2auCmjKJoyTrKrj0q0Sqjpq/yyfumfx5jDLY6h8ydrMMItpxQ5+521fdL1J0yGbxOibRBIc1YIuxvfEGFi2ZX3GUdXWwtr4rMVdRsOtdtITQ5ZxwGnHvD9cf+2OaJ82sHUV/fkVV6wnRgvcsBF8CuNmh/q3Ekh6hsZ8Iyq1Ngg+nBMi7GyC8jwjeM8t0psP/7pgeLjrX2v+7R//sM1ItbIR5xs3PUNDQ6ivswt266CAET/Ir3/dzTd/7jvfO/eCU7/01Qu+/q1vX3DauedecOwXTrrg6+edf+Ep3/n2hV8669sX/hfQIrzglO+eceEpp59x4RfOPv3CL3wbYFjHF886HeXOuvDU73zngv8++yzEv33hf59dwxfPPOvCL559xoX/efo3LvjCmd++4OvfO+P8L571jQu+fM5ZF/zt3jvPL2nyisg5AhX2ibT5MK8d0PeTlqVIjoth/qQCTuwq1are/eCDr4YNlXndAuW7LdpxuaTpgatjAS8U6MoC7GPCGOPGGMdgJoh0jKuKFyU/fea315z70C+uPOd7x376nB+f/PlzfvHVb5zzjQ986JzP/8c7HU5557vP+SrSv/jGaec8dNXvznngiiu/+7NTv3rOVxd/4JxT3734nFM+8IFzPv+h1vjPD77vewTzGTbi8x96/7lERst4GDaC+Y18TGf4L8j/rw9+8HunfOBD55yyePE5X3zf+7536gcWn0Oc8r73XXjK+99/0akf/vClpx738ctO/vjHH8zaz9DwtiqwQ37gnt5c+FfP2lGnzD0OnXH2lMR62QkE4+wcgvHpgLL4pdBCf594+dx2Tzz++O7TKTcZz533PrB7onbLvoF+weBwrNTbReq3zOvQeFxwCOqdoc7mgoyWhZ6oswdD+k0bx/Gcnp7fyOr50GTjamJfNGJcZlOC/UQ0kddocpvNt74xLlfuDNQIf6GTfRbFFXdCw5OfmnJG2Fe0dy09dmd7xuCehPg0NIr+/to44OnRSKkiYaGQu++hh7b7+bXXdnrcMVYpYv93223zlg8P7YBxgTdQRrhBoZMSxegCUswbnDxiA2McUGTcpapgVdBSoPkyoycI2Btiw1MQvONOCib42cknnxw3c08n/Yubb+75+3337Bf29c2ngAoeNmpfeJxO6fY82dgjhyrbwxhh0G4RLPo9YS63/YpiaRfNhbsURXaJc/ld/Llzdy0FZreRvLd7MWyLPZDnUMr5ezSjmAv2KIJOjCAs5YLda/B3L+Y8yPZ3Lffmdxn2dZch3+6yLK7uvKxa3jnpye/i9fRsmBicBjeorIoEH5IQsAWtkLWXYZZfm5ToR5z2ZLQs9MNAgjAU/llurpA3K4dGDv7Et761ZZbfWVh7EFDV+tjprPQL3KvOAsqJugrE07dB9gTJoKtgI42M2vBD5Pl0cT1YJe1dvHhxtNWmm5/vpxJ5NhWV1NXDCQ+jI27E8IkbBxG1NEj1ix2VgaTGONON8AJfBoeHJVWz8Ko/XP3ay++7PNeY30mc3+8ZrhbfEcWxxy+1enivbuHIKIMhRwh1YTozHNMEac2Yiu7BKpqk97x8v5f8orns7Kfdsq+dys3a0NxHlJPlMb6m8PFFi0qbbbDR9+JyOS6XitjgWOF/7sn+KlcrTWqh1yzQRBWUaiZZrVH4/QrKY1t5ioTNiOb7e7cO8vl1axzd3a/9wx+2Hy6O7IsNlauJ8nm6hH2w23QxTXQmnW0zkunOuZbyu0mVkuQ98/ejXvXqrjfYn/n857ayxj8qFjXlOBIfC7KqU33aKrYaQ1lh1VayjFv0K3gN6OexecPTa4rXmINxVSqeyooqTutBSzwjiecDE8MUrylT3xOGzXwx6FWUJSLIYVh1oUrVeFJFHTHyS/BfNheIj1dbQSEvfL1eTWJp/Ki20r+Ro3WcPqV1To3KMcGfDfB8X1LoU6xWtr3k55e+hr6qxtHZXXVMT1UV1TF0JukF7tm0AOaGzqa8TBbkOn+SpVU163Or1iYZ/fkW0lOusjYvfu/brk8q5YfTKHJ1eJi4xviuIzihVUc7weW3u7HzGvNUdTRZTeCGkA57Crlqmuw//MzcTUYzO4yc8ctfbgLn+BKTy0kcpWK0pmuzGFWF8xMH6kY080ArSegw8eTOxczzPNduft9CsNkL6KjjWLw4veati962pLn87Kdry6HqmO2mUwdPUFq1j2VJJxjPoNqZ/KzcTMJ3v/Etvy8E4cMmscIBzU0rx1cO/Tgqt77hoXY8ocvoTLstYZ1Qs1I9gcA3ntAGuRALbzURLwglitMNS4HMQXZXF2ym//vTn+7v5fObiHpiISXFOGGoSo1AcC0xbsyAv22obIymLDAGtNW68iI+Nu58ztc4vert733V02NMncVy+fy+sejGJf55aC50heOk6sJWt1Y6t+LLaBm/YG4QWZqLvqHNQU9EJcbGJMUmgDVzM2TZYW6Hp3jVaSZA6nkMFXbJwDRB80lGT1RIy0DZ/NpYEOQkpT+ALAMePzESol4Dnag/opKBaVUV1RrYDtJQ1IllvBHMJxpptXhaC9B/lM2NJk8cC319/RiE+yXrr9/1+KsJrt0zvRha1tUGgg0geYhErPA3jDhma1LG31VrbVfV8RkvpCa1QDYOmsNJC02SqapiMF8ojz5M6h+mAYtBauuk511gVmWLd+pZd2Vg5YqcH6Q2idxxbalcFh+OBDSx9CpdKGDt+P4q9PbJYLEoXiHc+gunfmGTLkS6IoPlkUMl8HPDIyPui5sV6GrSmoma63QFcKMjQDDhUq1Nem56AjylcjG22KT19vY63hGcUgVilg4Uen6/y2r4ixWjRvFxdWehS6zCm66m9/t77LLLsuLgymtyHs8QVQJsKgshNq/YWE6/ebV+bub3sciyD4sYX2E+535dWXx/3f/8z88vbOadbvoaEQ+b9MPF9/x242e6shr5skVc6psepqNKRTSJV8zpK9y4hW5RbuSfbhxjX8upfa2Xy5ne/n73Px2DJjlsSKYro1s+Lvosy21AotgIIpGifYwzZI97mKM+GBl6YJx+KG6jxJ4n1BqcQsN6kEfbGYRqkQZUBLyAiHDD46Me8jAfJKE9GDZjqrnGfKK5nEtr6uSiKlk5PCTz11kgPGmqpnb3J5Ys2cDxdH7TzotMLNFW54msL1DWAguwv4hxqgTjUmsksaYq5XxfZXVvvfXWVT+RP+IdxLCHE4/GPw2OokSM+l3XnTkaX3zhlyzVM3gK0XUrSbo78rxOBfOL0bfddferw0JeozRxzp2bM8qxDatT5jXgZ4VgfpadDayMzjTbTR6eHDBewgKa4vUDF+Ykrj723re/fdwvSpJ3VSDVmoumTpTPkGC8E9DZZ5iqnDWZJabinFn+zuutV9rvJXv/GS0sJVEs/EssjAGp/bn1mGyDBWwsVYtx4cz6VLDw1ahjd54cGWOEm1f2XwWvOFKj/U8PDu+BOrqaP198//vnB329uw7jVQ0tlEKBDCIUSYj7sI/GwxPVDCpsEqG8uRLiFmipf+Zgo61Jcs/HFn/49jqp4+D9p5602cP/eHyPGCX55Njb2y/VckW4mQdp0mu87irNadqfmCiEyz3RnEPb1MByRjxYzEObzSjc0UrdoIo+nRyCcjUYEfHAXwPjIqyD5QV0pIR/I6CwNWEQosjohfEwGs8idTWyZMuQY2Asg20mahRuvCm30NMjzyxfJtjVC163bXPqN782Kz/fUauluzv7sruSL5RqtgBs2TSamjleSM+mBcxsCmuWxc78lyNf80AYBo/QUdJpcgHhQmJx+oEziOYiHaXpEBQlckEedyOpWA8r32FPiuRA6OiaO6ewRRp4WyxdOaj5Qq/k8z0S49UGHrmEdTQLo7NyaMhwI9eM52Z7eWJAhDj54a+90mFCd+ul8iAUfahBxCqPot7ROhrjo8QOI2xtOzkWO4QOxXXFjnGWHvryV9yeVquPBp4RT61wrBUKhQzMdzwAABAASURBVFF51HM00Rxxi1ozsZbmwmOw8eEGqILNuueHkiBd6O3d56RrTupq/vg5/wCYZk7Qkxc3ZmpVzfiuaIfhoIQkxtnmwRUrbaDmUU+k67/mSrz8y9ZZf/15MdbjGK98OJf5EMONIKpabRe6dbSuxvgoEZF2YxFZLS/4DExx60CGTG4WklY3qbCvuJFhmmBeN8B4FcLCV0wmh/XRbwj4TOBLmCsIx2AZJ5nVOHllN3WjDMUi6Pyizp2WwiEsh+E0iz2P2dCnbH2n45dlpkKrfnM06z9v+6Yrxz2VoRvzd99p9/vU2hvSFEsHTjpocJummMsq3ATMxPIsa6xIYDyJIduEWJTE7vXuD72749cQDzy+BE+06cb5/l5Rz8jK5Sskh6N8ys9QaxdcJY6g0zpIgwoCTybZR1WFDpLgqUMIvTig6cQYT+NE4FgrB+y732/fdeSRQ1m5VRriFIs6sA6GhIvjRv0zINnyGm+DlizjiKoqyncC46irLtHXY++VJPkr7Joag9M/OBJuOhWnI2LNtCtmnzUuRhi1EJtgI2VFVQUDV3xsYJ9dsXz/63/81PxpC64zwu5aKkeHR5BVwulUitc3EIpc6mhGxw31IJBRv2r59cRoMJ6nRs441YrM6e0ZmT/Q9+u3HXpoVz8AeNZZZwVX//Ha/ctRHCptKUZUtQ5UUKuy6zt1bMREQdhtSYpaxYG8HkgE45bz0KSSAominxAyPl0k4M/AOe3kaSpWRWjbBCERG5EYFbqQcZSLAfI16oz+dUmWJVyiflNVZ7d60gWqKhYbGwEYqtZ4VMdCMq4cGhZufgp9veIXchKJfeXbTzyRT3zMXm1Q1Y7qso3H5R2VfP4x26avcMymBVTH+q1ezxhhNit6jsjCFF61mi465JDhdeYu+EtvoVD0/dqCxA0ANz0Wpz4zrd3C8/BVl+cFUi6XBa+qBuAhXt2J3Osee6zws//7xW4aBHOrUeTkFHI5SRBX214Ss1D9KENjXHVsXFGGj1d9caXqfkwu9HxJo7hsfP+a0cIvRGZkgbcc8Nrlm2+62bVpHJc4rlTVva6kUIM4wwzNCxLp3NgxbEaEMUAaN1HG9yRBJ5eTSBYsXHduz9zelzOvE5xwxhkbP/7Uk7vyy6Ge73dStC0v2wO1xvLrCbYpjZPBPXfeqetxVt18861WlEs7BfmcoQ1oW85dzjVuCscqnf1YK4keJh2dVoZErGSgHToFxEHCWE0sr6pug6KqLiOTzw0Q+RmSj3AMTTcuLATJqjpOFmmdgCeXtPvAwICsGFwpRfiQFBpXo3hOpVzeqhNZnm+pfidFWvKqTr9N1nraUsgLxHEWsN4LdhpnkFWcoP9YxVWIvPSle+HEJ12ZYBGxmHucyEQn3xFguVbwcdrD329hnocncf7lw/33P3hoJ3/uWVq6dH4isoNVNVyQqBuNYgRzFvpKWjsKZx0ZpD75yUdYsDIkMoeoqu5Pq0ulktCB8SSC4KlPtRrd27tgwRr5jxdVG5SlwjMA7dFcXHX25DfLniy9+y67XOupGaGN+SqmUTfViTq5/MaOayGcp36+8d2pDxd6vvriKR6fzm+/4679WxSZlDR33jq7Ll85uEGQx2sLnPx1uxJxM12rCMcfQtRSbKUDBDP0RO55pqKP1nI7v//woh9tPzBvzqYjxbIMDY5ID18fYk70Qn/Pg/TORXZUgu2sIcUpKSGCgxYH0rm5w9kMZKbdAac7QqA0ZWXIZHOMkIZsd2UnSVMMG8fLsi7S4obuaUGdSFJV912qEh7q+vv7hX6nGseS6ymo+LKldP6xnReZQQlvBmWfx0UnGzszMUsmV1UlmImg53hZszr0n7vuRrcnlcqjIRYQHxtbLiCslwsUwxkhjiTil0RxehRjg5KiRVWVnX93xx3bTVfuMSecsI0V3Yd60ckZUSx0OExu8TMHdHi2SbCF41S3+GTOF84ZTJQVVyP3xdgQJ0gmwEkPnk8Hh1bIZuut/4uzFy+OmkStsqRRUXxG5TfGR4kdRti+xiIT0opaGxlmFJ+68IL1N7lDouRBiay4U0WcqFgUY/8gqF/sIxn9TodwhavnMGhuA3+SQJU54lgVDH39c2SQv1rsefudeNZZm8o0P9yMf+e8c3bL9ffO50aYG4e66GlKaMVmQCQQjF5WOB69NLVze3ouufikk6qjWR1EeBL6xFNP7Ds4MrxOvjcvQSGQIjbxCV5Vu80fJ0MH8lqxUkQrNPPSTgT7sgZypJhNFjPPMiGUwwhDVXDXhx/TGb1VSFozsjLN9MY0ebKHnIzONMF0TSvGJgLaiaoKN9CqTGU87EuCaYNxmgjHCb8ewEWLYa7QI0PFEVOO047+65TM2VBvSp8pqHX2ypGyGuVimgiBDmLWC5iGBXSyATOhPPwY1p0J5DYEVfZWU+bzeOeTzbAmi8xu8qRFi6pbbrjhI3h0kQD254TgyYr4sDw6RBXENlVaweQH4CWkERwjHCj8s9Igts45qDEygs1PNfDm3/7Ig3vIND/LqtWDfD8Y6PXzEoqRuFwS30e9BGTUJjRNBRryBTD0bnjy5fcCBAPQYpOkaSIqKSZ8KtSNEPD5JpBiVJEIXiIyiRR6wmEpDXf9+gEqdXxhrYITtRPKKSiNQNJd7KNGOCJubJNBKwlVFVUAdF6qymCNgeNsi/U2/LXgJIUbH/U9ScW6dqfwwOyrxNTUq7VDkC/ChZRUaq/WoO8Mk8J+Zx7L+lhEfZD5Vz2UHWDxqaise++jj+7imKdxK82fv37R033inBcODw9LTxhgrMgoKJtoZXdxmqaopQanlyKpgVjxBcMPCXLFYjDOkqgkElWGClV7rcvo7jbfWMXc8EwlqY1fG6pYGEJ9TwxsJZgLraDqiQJTVYvpIQ6wbwrYDForycUeHSiuvexDgN/JiTSR7L+MsKjHQo8UyMIUncfXklm6ORSUUYGOdYiiXfW6U9RN8JWWao2uqmAB6vysS6yp0ZBnUZZlqCcMI4T1rNObNCv1jzXIqkFRgO1L4Ucoy6SQh3wURitRL+koZtNYCjhd0yiRwHhSKUei+bzedPvft0B2RxfnAwvwjzwJxruFsSIB7JxDOygDUUkR4RjO4BkYBrQXrqktoKpgMk1ActwFC8PwFlAlv8BfAYir6uh49EQxzgRTB50k+KR2HB8o8A/u/ry80cqrpeE9udx9vTj1SLEoeTz1wUqcTUIqoDrWaUxPhdF8dChfTfG0RrGRyvf3yspSqe+mv966w1k334yd1Shn20hhzpyDShWcHOH9uWeMeJ4n/JP2alyB42pdTK24gcVcDEUMMxBIBEHd9EeEF9pJ56aQy+8KWLTTJvFf3/32ReP+7xCyrlIYq5l86kNk6U7DxrIGzW5VnqZILTqnVeYqpJlq+rtAvUhQdeoWjrFRllmACxEHPnVkPKOzLRkmqsherjkStp9SY9F5f7rlpl14kjORvwXF9xeOxOVtuaDOnz9fikPDLZg6I6Vop2D0ccxyIUsx3iJssgf6+iTnmZs/8p73PCFdfi74/nmbpmrwCliEOtNWDGvrHC3YpeBJijUPp2zQ0uZZMcazV06kYX8BC4h0GioKs0yGxr5nnPlElp+FXNQZZx75IGbUFzBesw9jIowTTI1rm2VpUtsjK8c6MnDMuhLqYd+km335wgt7XXqaN1ZbG8nTLDAFG/UiC+VybPDBolFv5r2AqS2gnLwNbMaN6AYCouPGD9IYXe7+wq1zC5jOi3RXolIs3m0TLP1JLHTSBk+M0uZhAINAMozVRlUbUcuxkJESaSp8EufGKgxDH097e22QJBvXuNrf//3EEzdd8vTTLx2YO0cKvT3CI3zWDRk49fEnFKTjIRoHHbVyOyTOfpRgQCAq3JRxMWLcVyNptZom5fL1e+y+/3LSVhusJKhr4twBcVVdRtExq0p4G7mnfv7Ld6VJcqvFeOAr0DZsQuef9VE7nmY6F9wm5MTIQQ8Uixs187ZKH3PssS+dM2fOZpSx7Nmlkg9zrdg6o2FDTXnc+LNgNt7SOE5Xrlx5zYsPO2wl6d3gzzfe+K8YMD1cyDgnxBrhcs3FjuDmshu5jWU8m2LDMh4GNDe/lL1Ug9paqax+D2TCB6+Pvu4eIjw1ni68xI7ys36FTQSDoKad4KnaiEkNQlChM+1ESMMHqkuKBjEES0POxKiz+0QyKYrO2PrRJUtm/P8TUlg34LjgX7lVPZHIiDCe0dguboS6kft8LIM5rF20eyZFVnd9M9F11stiuM66zJYC15u/4L64GqXcUNBJ8/s93ORyYjeiZeEWRJbhwsU/MY2SWIJc6DYqURRJLggU6e2u+v3vp/z+RSmOD5i/zoKQ/68TfxXVD3BI5BmpxpHE2Ki1qHqUpJJKo1OjTqOZiDj94JRTsWJUJRCD1xvh8n323OuWfTfZBO8iwLTaLmojY0efM6wXE9VJoKNzkbXkprn1hgpecG1vPpeybzi7iWb1+F2dZlq7dNbWLJ9pAtt4jazd/r++/OUpf0UX/DpcLr66EkWeYBz4vi/8Sz+sf5nYrkJVjkLBSLSuvO+phMaTSrn87LpzF9y2o2pX3+/58Gmn5YaK5YPxBA8VFbINMHaBOJboMkYZhMEK3thXrja0q1kseUlz+WiuK4OQNMY7DbMyLJfJZrwRGU8WNuZl8axsxkP9mEc6wXgr1GZkq5z2NIyj0UwVb4Or//j7XU+0bvcla+LD+Y8xIgwJxtkuYk3o81yvUzUbPe1bwjGQoT3XlDn1mTMl3z8lg1ldrXr14a98TOL0qZ4wJ3giF24yOFHcBHFPdjVNVGsdT7qDe11Ryxt/h+rqiQa+YAVxWRwMoRfCjXp8GF34q6uu2h404zJb3E488URz9113HVBOIuWrLcXTs2DTw41K4r43hE0QylFPBC0vVRXVGpy+KpKCk2WIhE+kWORCz5cq/xPN2D76sv33vwMsa+KCdmPVwjZjiXqMzpuoJycEWRtd2LZvJhRbbYR9NpbKsmee+ls0Uip6grmdAi1qJ5XvyVtkTUpqtBnjqep6sbE7TVoImWeffbaP92+7C8YYTwC58eHpIrJmdFGWgUwPr2cpiP8XnI90YOW+lx9wcNe/1rzsmce3jY1sLgZDBkgR4HIbfS7mjDvQkDKzD8cb4eQ2yXPjjBVBB8ZZk6riRIXT2gj1gp7utGFVh/xOUWMd4xf5mj5sRw21tIhxuioUJ/i6sAYQOrw43hqLwB6Fp5cu3f3ghx8ecPQ1cIMOrlZVtk7Q1gbUafLCZ0oL+Daz5JSsExhaleS8IDJm8hBZ2oW15c1Fn283s7oafOTL9xnJeXodTn3cTxakePOSfQejUYfmyc28VjTSCWxaREPffScnrlQl9APhYhAU8oEWgtdf8/DDIflaYf622241VCntlS8UjPE8KUdV4UYll89LrlD7bTALh6uqo5sb1Ya4eE4sHXbzoKL/JjxszNI0lgByTGomoDXeAAAQAElEQVRTW6z8faB33v2u4Bq8TWbTRrVUtTHZUZzN7ajALDCravql//7vv0Wl4v29fuj2Nq3ayv5i/wj6BWVa96+Otb2VDJb1C7nAC3NvOProo2uDoU0bfnXnbYf2zZu/UYCTyVKlLPxze9Ux+W2KTUlWzmAMQGsTEcAmkXhWkrwX3Lbjy17W1Z+xo61ardgjvFy+L4GOaYMWqMptfhpIM4qq4sQKZmh00qMCkYeO4fbVgXEHy0YLoirWwOzoQwuwP5pDymVftwpJy5DxMC34MOT4YJhaGBQaME0gGymYGxHaJgOS4y5ugMYRGhJOLtrdQOo4Chk6MH/Bvk8+/PD6nRZGH8/a6S/rZlPYXsKDQQz6DuNQbAotyfACurKAqrpxrqoTynPMTiC+QJiWBWoeZFqsM2NaKAuLe+2y269sNS4ZUfGw0eBfPUj9U3MtfHmQCp+I6uQJAadRI8rVEg6SImwsPOF3JlRrA6QUYxPj+Xt/9bT/XjBBSJ3w13vuebEN/A3Iy1dm/I5PEOZlaGhE+Fc34pk6Z/ugVlt7vtjGwtdvaRRLX5ivbL7B+r96xyGHlNtLXPU5dHpZLXRUjcjo7UKWJdrlrw10b3DwgR4vuB0nbM43KFcra/A0ahoW7XTScdauHaoqquqyKbaEzbIWcnsU11ln0qfuJctXHhThfGLZ4Er3207lShGvZo2TM5ObqrqNftYngRhsfNLi+gvn/2HxnntG3cg+/bLL5t9421/2wZwIsIZBxHg92Xp+D4dAZtcXO8dC33ZIsatLgNR4Qrg40oK0A2rm2FVr0K+m3r/TD40rJygrKFsLKS+DiojixJAhaQybYUHIkIqgh2tA1F0sR7jEuJvjdhSIkAyO0HBTZc4YIavLhSDHabLViV/4wvT+rB2jwdkK5Wbr4iYnQwClsu9KBdiHe5gg3mxV9E8uJ1bnpVwrVcf3uSNO85atjRl7czqjuxDjwYXPw5tZXW1W1fSII157Z973nkyrVWE3+74vdNhEt3rMmTPHOX6e8lAGv9Ba6OsXzw+lnCbzEglafvnv9ttvD6+89ve748RooeLVgPE84W+UcJPC/+Op0Nfr5FLmdIF571hdqKlzghYUtjOJY/GitLrdVtteD9Lqv6zpfjZ1qa3R1V8nVX3nEUcM77Pnbrd61la8lAsMqWPg2KNDGKN0HsN4FlW4dZwwJp5ZmHpyUDsp/Mubp1au2G24WpHefuyPsKEOQoxPpN1YaVdwGvQY48ripIdjLPBUbJoIFqLBLbbY7o/TKN6SxS8E2yZqtq6mqVo1Qh25eHuibpMgs/jh6yKCdWSg+BSjlXOHdmaccEMYNs96VBEnL3XrJmQZRSVEYzxLt5JLWgaWwTYH87ym0WQPbDVeETRL+MlkZGnSJkM7H2k9z9NC4XWTlW2dN3PX79qgKm6Dg1f6tVDEgKbywqcTC6hmo26sFGhjiRdis2qBmY/+DtTp75t3V07MH/J+EPtwqNVSWWrODA4bcuCDcM+uVOjQ2fkE+YgslzSCGxXfeGLgUjjh/CAn/JVTOG6xWFzufuSRf33vWWdNeJv5+8cfX8/0FA7QIPSrSQrnZcQEoQgWpQiLR5qmQvl0OI1wr+jwms7WoVCaEGgg1mTq1UJsfhjxPE9C9SSuVn53/kknPSJr4GOgGtvTXHVj21rFaQfSs3KUQWRphs1p0ojU4nGZkdUM6GPn9M25oscPn1XUzd8+YR/EcYpeUtev3Cjwe2bInvSCLMfPsJnRLcaeLyNRJPc89MiR/H+tmnmYvvfpJ/ZPfG87i01ShAXCgljE6y4PG39ERy/WQYwSphHJQSZPJbJ+4jiTauXaC44/vqs/Y7/IWu/L3/7mnhoGmyUqQl3duMbYtmwwLOjS0M0aMCDs5uKYwvmupNjtRKgkNZ6oFwjbwb5hqKouTd5UFP6AgE7gtylCzNtu6m4sY1F/I1LUQ2Q0xbxtRIr2Z6Ac/qGGYuMpkjIpqup0dmMLvoRtJNhHBDcLtFoGV6jFTVWdLLad2aq1tOpYaGH/GD1UjaNXvv3EE+eSbzI0OkFVnYzV1a06OQ8FqBVYRN2DrKJTjCjJ0EqcRSKFo3eUF26TWQD9rPhII5r5W+VltGbexrQx6BVVKZfL4nkeTpp9STHAN92+o//xpFHkcz5uVmcLXrvzzstffuDBV5rEDiV4FdXb2yvocIdu9eDEy8piDrqoxVzjU2SqInga3//pJx7b78tX/mTdUy46d+Fpl1++8Cu/+MU6X/jWV3eNPLMHeVyhWbxlOtHJUSxfa5g0KS8oDJyHkZ2pyazVBrQTpu6ualUYcrVpOjsVvWq77e5NKuVfGWulODIkpZGye8VEJ8D/QoQnJblcbsaVpXDx2DxLxciB1zz++MGnXXTRwq/88IfrfOUXxC/W+fBpp238p5tuOmxFqbSuBJ6wflXYE4uWKsIZakBn1tfXB6dWdAtQby5f7in0nq8tniCnU9V9Pzh73XJiX58YzSs2dama0WKN2mI8jdJnElHfE/YDNzrVqAwT+TIyNCx5bII8LKSjwIOIQVrRnwY2Nwg5zyw2PzbF8t8mhIcX4cYkxdhvDkGjmQgjKlno5IvCnhaohaxLsJR7quIhYUTc6ddAT0Ewt0XTqvjQy1eRPB6gQtiOYwyTDpxjF9P0CxnGclrHVFVUtWUmtePbCr+vZ+FdDzywqCXTRKKKRQthv4lZnVMsVGObWNLFmYbVEhgI/lWGkvL8L//kJ+t++ScXrsu5Qbj5gTnC+JoCdWqsuzndmJfFM70bw1Mw37P8VuEp52LNAc9ZaC/fMtBO7ZDZMctvTmd0hqowNCNTQFWlUqm4MdTf3+/CkZERgc/wdthpl/lcCxv1brQD4xkynsZ0Fp8s/A76PgNlfP2yy+aefvVFfRddfXXfDy6/fOCiq66acxVwOeIOf/7zwM/+9Kd+5l945ZW9xLd/8pMFlMHyjSBtOnVnPCyb9R2G5xSWm+3ssneNxMmTBk5naOUKTJFU4DWk1UdVhQ6WGM3HpOXEdagT6USySZfC+UCiMD8RlVh045tvu/W0r3712xd970c/vfSUb3z10v/+9jcuTYPgVLhLvHeoC0HQaqB5kEHQKdagojoGQQtqgABe0M8ACj9LBHiqz8ERJuXq3//fh973N7KsbhwtNErN0zW2UVWnVEV1PA/7ohGTCTCK1X0yhlWYt2jRomT9hQsu8z0v5oQPcfqXVCOplqrSk8sLv1xcKo1AA46WbiFuLOCG16rpJtf/9S+nnfE/37/k9PO+e+npp33v0tO/861Lf/6bK3/0j6efeqPxvVDFkySxDsKPN7Ppx3Ef+EYqeJKbMzAgK5cvk3Jx+P55edP1X3P9/Irfbh+n8UujBDMHT4pUk+AoYH0c00xn840h092CTlhVhXK52QnUyAD6ysMpmp8kwq1pHsIZEi5usbmo00IMMZ/wVDoOUcZtirAhUiCLN4ZuU4WN1SgNp8GkCUIF4pFh8SqR5GAID2nL15dxJOSxCJ3N4Os47wi2U5AmmEYzpnWp6jg+liVMmJOVwyP+o08+8Uo81NFE4/gaE4nqeCHOdzVyjMUpeyzVOub8ANwKQ250XIgasr98q3oi9z35xGdO+/65l3z5nPMv+dIPzr70yxeefelpPzrv0q99/7uXfqWeJv1LF55zaSfhqd8/55JTv3/WJade8N1L/vvCMy/+7/O/e/EXzz8TOBsYC5mf8Y2GF5516de/d8YlX0KZL59/zsXEaeecedGXz/veRV8677t1nHPxl8475+L/Pve7GS76+oXn/S/xtQu/92OH87/34zPPPet/v3zudy768vfOGoevnnPmxV/53lmXfO+SH//4G2ef8eP/Ov0b5x77za9M+SvvtHuG1lYfo6rC2PUkbU/Uk6MBTyTp64IgED7wVaKq5LFZX7FiRe4Xv7riS187+4xLv3LBuZd+7cLzHU4/95xLGCftW987+xIio5HOODEWP+uS088945JvnX8WMBaefv7Zl5x+/pmXfPmCcy455ZzTL/nK+edc8q0fnn/p6eee/cMLLvjpsf971RUfu/KmP3/q6uv+9Plf3HzDKT+98frPX3bTn0/68RU/++wPf3bpZ/738p9+5Ds/uvA9XzzzW1/41vfPufgrkP+1C8665Gvnn3Xp184/Gzjn0i9+70zUedYl3zz/DKAWnnb+2ZecdsGZlzA8BeEXUb/LP/dMN16+/oPzLvnq/5xz6cw876h5px/55vEffWqLTTf5o8apDPSMnfhMt7Oba6JjkforJXZ8Cgb4IEmx1lsQ4jQJi9Xqjn5Pz4GJrweY3vwBaeAdmOvteXGMRSiFo0URYf0MuwH8MGqrl4QjgDCoZBFYLHIJlju4uzS9ftd1d1pa51ojwUza2E5h1drkU62FjXzpGnrVlemwyXob3V4cHHowKnMhSt1pQugHWLMSqVRKEuTwajNj7jLkellNUvFy+aCssv1gXD3Q5nMHSk/hQOyuDoxV9svPmbteoafPjQeeUGA0YMlRl+6y2tFifGXMBTbGpm7enLm2EOSuPPXL3352lKHDSLEaHVron1PA9HQ/OcHi7FnOM+rNdAabRWYQ9sMJaxJbL41X4tjqAa9SfqBH9AG/Wn2gNzVIVx70KpUH/UrVwauUkSaYLj8YVKsPhpUYaB36JZQtRQ+2DisP9iTWIZ8mLuxJxoeFOH4Qxngwl8QP5uP0gXwSP1BI7AOFNHmgJ00B+8C8IHigX7wHfOpB3Y08ZdIk6Yd/a97gcA4SNBntqdgEMU2QNl2oYvygY+DiRHxPg0J+l8ceeWDP6ZZv5GPdjcjySMvircNUWD//CxGOBYJpIsKmOYZv7VtnnR3KnhyA49YDoiA4oBKGB1RzuQMT+OOi8WtpH7TQP6DaQRgH/oFxkDswzgUHRmH+wCgfIF5Lx5BPepLPgxYckPGNhmHugCSfOyAqhAdGLJ8h7x8U58M6ggNjyhwD6MHLQHtZks8dEufCQ5I8kTskyeUPSnK5g+IwPAhtdGE1lzswygUHVALvYOntOTicM2efWHR+azuKKJ+IRKyq4jmqBpnGh7aejI2vtuI4FoIPfzxdrYcmEbNr6vkHVkMP/WDGgbQM5UAPyFAJx/NV0G+VMId2oi+DsbAUeAeU0N9FIwdU0ecVpIvGHID0q0vGHO/Pm/O5DbfZ8rhNXrTdB9bfbLPFm22/3Qe33nGHj2yx/Ys+tsPeex+79a67nlBYMP+zZU8/VDLewSXPRx25A11dkFeFbWv29TGu0JdBLayinqofHJCFFaz5VYwr1h/5Icp7B1b94EAzmdFWVV5cHLlCraT8zRGEtWq4eQGyycYOJWqZre/OGSOLMsibqAifPBI3A0UUm5DAz4nxQ7WhryuKRbGeJ3w1sWzZCszFsY2X1D8GZRshwq0UUWeoB2CTDCRRb0JBdACRcirFEYmjaCQQ77add16vCPJadzl963q3U472t1htkgAAEABJREFUJRrzVWHwRgLiqhNpIK+R64RPfWp5IV+4BhM9pQMol6tC7fj0M1sK5YNQMKJEcXqT+kZiIAp8qdhUinEkseep8QKJkRYYMDQeXomoqz7F6xsXmcFNVYWninRsaZwMjaxY8Zd9Nt643I1I/tcbcZoekthUcUIlHvQWnF4SylDG3AWGSzdVjCvD+aHYNJZWrpQ+37tg/933PPptR/7L0Ue9+rCj33XU0Ue/7Ygjj37fv77p6He98U1Hv/uNixze9aZFR7/n3964aPEbFwFvXPTuo49a9J5J8N5FRy2aDO864vWLiLe/9oijifciJN7+L0gD73jdkUcT73rtkUe/98g31PE6hK87+t1HHnH02488EvlHHf1vyP+P1x919Dvf9Maj995xl8+ZKF2S4vRHJcWYS0c3uRZd7wDfRH9Bg9AOhGITxLARiVjJgOEjjbBGxXq+VFEO4QY/vvRnO0AmaqDUiUiR2UhlkmikMd6KRnorsC0ZnbplcYZMj5SK4vyyh7lhjFgf+rLtCBOkRTGmJoGF9ZrRooyCpmq8CSAdkGbUZSoWfo193yHCXG1GltccJkGgKRCpKlFFWPWMEmWjSlShz1BU1Qq083LByFve8m/t/b/vS/MHIptJE9Lk4Thg2AhRFSLE6Sn70/kfz0i1WpWVmG98/SVGJfFU0Gapoi8YEs1xpttDUVYlRn2tEKHOBP6wLKkQtMUzQ4P+Q48/7i9ZutzHGPASNV4s6lUsVudCwSsmif/AY48VHl2yZH7Rpl5ZrEbQs+p8qydR4AnjVejPfkS2ZLAponWk2AgQpDG/HirjGHWy2j8fft+HbvasPMrK2SkZMkWYzuLTDS0YOQmtoMMRd1dqpThcwoN3j6wYHJJCf69EoMVJInMG5gk3XsY6zhndUsEurqFaJxP1wNvJ3DlzJK6UH3n1Ya/6q6rOQm2dq3qx1IyC+qX5041GlEM0y1rb0jssXDgyMjT8J2B4oLfPnfjYOBGLxZZjDL02I5XZzzxpSaJYqnEqmLySGE+qGA8xJmoKZ8bxFiWxJNVEPFXxOUhRv4cuIWakAAqz/6hDDs4gSZNH3vTGN9+jXY6zH1977XorR4Y2K5Yr4kF3yEENIpynrIcggU3gokYw3S0oz+BpdCAI7Ybz1z3v0s9//tbPv/vdt576/vff+jmExPHvfOdfTv738fjc299+y6fr+Nzb33PLjPAelAdOXrz4L8Txixf/hTj5nYv/4oA06QT1qYH6jeHT0JV6nwLez7/pP259ye57/arge4+yrzlGOrEPx+W0+VVlpFySsLeA8Rf1ep63398ffbTtl5wDCIbNUYWFa5olV0Q/R0A222qsCiHuY9woN8bHiUOKWaFisMCmWJiwJiHug0ZgQ4THAStTh6IByozxpdbDoZoCY2EmJ4Uuk+WTL4ZBCGrHh2YUwRzG4qniQjwESJbfKrRqhDqJek6vFPqlxhMiQV7fwBwpVSpSLFeHBvrWGZF2nySxqqgU+aoqqjUg2fJSnTw/K1TEw76PuUy78+HI8zyZO3cuv+Mj3PywzYQYde21KpJ6KgxJbw6b7ZSKwj7gR/8l6FvbEI7axngSpwYyPQnCHinj1fDDjz0ht91xp4wUy+4AwvdDgQnEipGHH31Ebrn1r7JscFASNCRGHbQl5WeIYO8UdIv6XD0ImZZ6aDkukM+0oH5FvzBkWj0ftUDw6r6223LLFWjlH7AATX/2WSNC1JVlh6RaS2RxhqOwNdEoJez4XC4nwzAy/9qCT/wlDAjDwQOZxkEwYWvyOrmzvkZ+g2rhWZwsRXxoaMgWcvl7t9xpp7sb+VZ/nJYQUVXJPtRzKmS8z8VQsQE46bOfvXPevHmPLFu2zD3toC+Er4e0Pj5m2i6TWv4XKTW7KmzrGYkFjgCTTZA2eNoxhhNNxQjozuun4hmkkC8z/PAJrqenR6IoSpOo+pfd11nn792KTGz0onxPIZ+r/3gnZbeTxXFPZHOwHd9kdMVToIfHMD+O7tloxYqu9Z6sjjWRV+rvf8IkemtUrfKww6mgitZieLgEbwYJwM5gHLIs+ypOrKgXqBiz/w233LK+tPnUT3zYbW04xsiUPZZqH/Os1P6cHTr4KeJ1BGh5gHger5YN8jzEA/EljVLxFfMB+Z54GAFGUgUwO6YTJlaxGAL1MK2Xa6Zn6Sy/MUwwD5mfol6l78eiDCVEoVNzyHzSGRrwMWSafIRLQ4aqJ4bzHPOecYJWGx4eFouHoryXH3526dL2Jz5gzmzOMAPIEy5VnUDLCBYRAoG7Qpz4eB7sTL8DSowHDZ748I8iuCZSf7bLtaWh/Rl9JiHLUm4aW9fngQmENB9hgnHwzJPPyN233yXDg8Ni4EjUqjzz1DPy0AMPSaVYkUJYEIMxQlta5FNPhgTlCOxuUSatw4KbcYaEoE8YNkLRRx42WQa2WO3XzuutVzpo75dc7VXjEZNaGKOmAhtUi4lwA1FD6uKi2GsCWb5axFzDEUGIlLtUrBBMcPAE+UCWL18uHna9HATc9GCRcH9JQp6ZI4WItKYjY4obLvSTo/lpWt10/Y2uOu7QQ0dAXqOXal05pwX1dpGObqqNMmpFVWs0trlGwR1O3ShuiK7JK1cu3zu09Fn+flTakw/5ZCwlvIIw2HiYhnEzUcfpURKcHnoKx21j9xStqqKKEWjUnS5yDJKHr7WM1PJc3ag/Rdnp1dKai3MgB8dWHimKp1rZZsutbl60aFG1NffUVC+f26JUiYIIemEbJZwrBsVYD4JxF2kE5+i4jA4TgRVJKqVfX3zxxUmHRdda9pMPOSTecsMNf+urRiKpqOo4XVXHpzlGxjE0JFTVlVfVBqq4scZycSUWji14R8G6tel3zjuv/X+fYrAdS4UHF6IY+7X+M85P8TUb5TVW0pxuzGN8rO85Smo6qaBDITjTNsUJaxQlwnGqqlItR8IHUUX97gnfWkm5cMnUocXCBlZwGslCwTwjPQtJb5THtGABZH5z6MqhIdRVVUUR59UYcq56xoiqQgSA5hnGGQLYTI72hU1rNhCBFdAu2k/Fk76eXhkZHhoayOfbrgFqYDSplc/sWqOA2HCpZtqBCBviPulFHQiOEVXF24+8g3pGSGNeJrE5RMOc7Ea6qqJ1jlwLoYMRzxEUcUayUJA2JGBme9h8GfDxYcoYH6c8BeHrt7vvu1+eWb5MUuRzDN/3wIPyyKP/EG7KuE4rytAeKjXbqFtkjKiqUI64jxH2s8UNFyi1tIjB7LNohrqQaUW7gyCHHLCt7ktV08Nf+fI7e9L0sTxUiKuRJNgVCo6grPHcgpHHbk+S1E3K2phIJTUYWbSCUZRiM0QURlQMbM+K+DAwNhp4AknFU+R5AhGphDjtoVGURktEPC+QahSJFRhTIRNmQbTNZUBvDQ4aLl6c1J4xYiEbKgve+Yp6RvgfYRasVnbYaKOrIGSNXe6vulC7WrYYkexC21VVVMcArWHbsTRNRmRFONEzUFojVNWxqdbCdA1/uZnKvOvII4cO2mvvW70EoywuwesnEhbybrwpG0abANS4ESxbg0EwEYkoJpQVLzCSYNPjqwEFrIlgzBoRhI6WggeDUTEW47Q+5sAW4SlQOXZhQJ0EgvIOKNPqShKsrRh4hSAsbrPl5le24pkuTQN/Yw08P4I8luGGjboxTtCpWNw47mk7B6e7wUIqDtL0ifGE6cGpqe8JzZ2FMVYJgzkTqAznxM5I76Yq14rk+uuue71N4+E4jcV4HoYDDFXXzNJJSCpovtAmk6FexAWqKqo10HaeMSJ4kucikWCMVdF3RWP+xTG3uNmcqajYYmg4GBOxCcYmwBMM5SIFCGDhAVCREOxrQtNEmkG6FRHyY1hIDfDTmiJu0TaGIgannjHq4WvfMJ+Df0fd4BGoQR9J/55BJZVGZHSGpENpVJiMA+mNIG8jGvOa41DfXdz4cWnxUDvBOEG6sL/qUDSYdAM+FnRtxuKjyDAqsBwYhG2HimBgP/F1E+QM56Ko7YlPzGmcoryBZPQxbYviLS4DwQY1IGzKVVUxTRB8KMvDGFRVZ3tYXzjmrFGMQSOqKq0+quryVMfCCXzoR+tGN6WiX5DGQJEMKdLqKzY5sURJVegHU/CXqyXhq7QiWnLb/ffJUBLLs8URue/hR0RwSljEnkARUnfBR1Vd21z/YSzCgUuKuSX4wPSi9CeQxX5oBC1lIZuhj/YmUVUwVR43KLdGLk2KD2oc3ZZWo6S/t9e9c2QjU4wko76USyUJTIBFRLDAwKgwoEgq7DCGAj42WKTWBA5GjD/Hz7jjQcvARlbEapequkgz3REnubXKUlW3Mx0aWik8zqMD8sOccJDxPebI0LCgx28/dIcdHmpVfnXSzCxXplqzI8Wy37KQ0z4Viz5jjNQ1j568uTL07KBHnTE4hktF4Tvl0M91rZyq1sfimAiIHku0iGVjjmGL7FES7ZlhlNgqgjkRBHDT6IpqceTWzUbiB1qxTYd2+tVX911+5a93Ft8L+ETueYH4Whs1nGeZzrXQwNGIg9Tnn7T55PN5Nxb49MY2kY3zg6dJgQdHXC3fu83mWzxI+j8TtgqCp+Jq+aYcHroibHixngkXQUktxp4vKTYsSZK4JquqC7u55XniVywJX+GHPQUZjsove/MXPzWvlayknIwk1eoQRoxYPGhm/WtaMNf87MSMZk1TNW4ekD8DS3HBq4W8wxvXC5KHlCxkfLagqqKqsyVunBzOAYJEhtlYRstAwo4Fd8ZVx+pXrcX5Khp70uF42bK2Gx/Pszom0wmb4ka7t+q5KYqtwWz2eQZuuhgfjivy1MoV8vSKZfLgo48J//so66NdHgD72ZoJx2mdkRjSZlOB9udJE+dcijkH/jsgfZzM1ZZ408GvXbrNVlveBAdYGRoaksHBQeHTIRWg442hoNafEgXOFcoya1agqm6CqOqM5VFPP8QiEQT8noXQwKoquSCUeQNzZKC/8Gu8fqh5uBnX1r0AVXjc7ouPK6k60W5Z/2ThuAJrOPEfB73y9jAI7g/41IP9GCcCF+JSpTxBM2Rj2zaB3JKgqm5RZ5vboWXBNsRMBrM54RtBWjOoK798yY3EQL7nDyeffHLmgZtZp0yH5fKWJgg2T9PaksW5qDqxn5VeX9pXw2wiqzCFCC7KLBcEWHKRaXGiROAMznpqbj3m+JOXZPz/LCH7Yr111/1ZEleTJIqcb4NtXUj/lrVTFQbKEl2EqvA12FyxKL9P0tPfNxCtiPdluhlemg56nj7LJ2D2sgl8Sawd35vYTAsodBccj5TBDb1ag42uEY450gj2LcMMqjNrC+WoTi5DVZ3vJu/qQGaDFC138xH2ymjNYaaPak1H1VqIh/g0KUcr7zj66ErG0xwmCSZGnZjJrSfXpmBWdVFVoe8awknPU88+Iw88/JA7kTJ8ShCMwrS9n0F2y4tWJLJM9YxUcMrj42S+glMmH5uqkZUrnlb4boIAABAASURBVDEZw+oOFZ5wu622vsXG0UgepyT8AbZCIYfNQ8UZg/9fFidyo17jBsRo6zo3TqNM6OEm0nTCxnK1uBE+teVzPRLjSN/F8YRL1aJqWaJKpWTS9Pc13n+OO+3U2JJxfVLPII2oJ9d4cMghh8SBBtdUyxXBkxfGWORO6vg0vsaVgwK0FYFox1eERRULaayJ/rrjwg0FfnTJj7erxtHm1qibf9LiQ8efqgh5OA6IFmyjJPJyXpBAB0d+l8ZrA2yBsJCmI7Ya3/KKLbccJM8/G4aXLr8ZD/LPDPT1j/6as/E9bDawjGIBbdVe2qgVvR2tgpNxHB8J/89CL/Dl2WVLg/seeuDgVvzJkiVLPTWPpkmS5vMhFoSKuD4VK7UQfdugF7pauAHSxt1OXTD7th51Qad6u0JtbtORRZ5GNIvK8prpnaYpZ6oyo7YwOmEtEZvw+yzlAw7Y7+GT1e0qW4rjiQ8zuvUDLLu2o5UtPd+XBBucJUuWyPIVK8Rg05NyDKpi+91i4HXYSNqzWq267zXR94eeD/9mnlpjGx/qv8v6G/85DIKHObl46sNvmrPhVRx/CQZRvlAgmwMnH588XKKDm+rEwag6RutA1OigbizDRYDfV0jwjpHvrxVhjMWoN5eXQhD+9atf+cYDjfxre5wOkJiunqo6XdY1yod3/hf3BLkV2IxKgvfHRZz24AWqZFOLITGVknRyxFR80813tsZY53hnPEMn5TE3lvSF4dPTLdPM97clS3r/8eQTB5swmEOnUyyX3Fin02jmbU5b+HKimZ6lVTE+ACz17jSUGx/OcbxPEyP65Lv/499vUUULsgL/ROG3Tv/qo5XhkT8bHLYmeDCiPXHC7R6SjPHFGm9ca2GHcenpJLIHRD4kKhaNQn+/N1Qq73PapZdu3FweJ8/V17/28Ad81fJwaViM31h/KtjliPtw4QHol5WTgnGXwZvBjRCxrmvVjRUQZ/WiLYhZFTqJMM5poh1LpsvE+UlbEONLckgrSPyVeE2T0gbrrX8PkpNeHB+NDFmdjbS1LU4dG8E2NKJZX/JmNNo7SmKhTZ/ExodrKMdwnCbCkxr6CfKSj2EjaNtaGp4FPqgWn3j3PI8bT+Hegrk4fRPf856e2GPMXU14xzveUZ43d+5VPYW89ORzbrfX098nPBLmF8KyhjeqYyVpTK6RuKq6yc5Nj6o6RxaGodOFP8EfekYKvm9HBof+vKCnZ43+WrNTapIbB90k2eOyVHVcujGhOpanOhZv5FmT8de86vAn40rxjgC6zZ83x534xEn3Y0lV3RhQnTzspM2qY7KmW44Tu1ouPvSKV72q7fcHppL1f1f9bCCydu84tZpgkZszZ56bizxNYlmOEYJxYqoHkEZerpsswzlNemA8URB4+hYXy/fNKwzcieQ/5bXu1umKeb39N0WlUhUnW2Jx0mWMET4o0Xew0aoqqjUw3QnYDzE28XPxSp3fparEkXDRKCfRltdd+4fdW8nyEvMINmElnnbGcRWLTgoIvGrWU7VSlM1Nj9aS7pUu46S1WojqbKs8UNVRe6nqaH2q2pI+yjCDiKqOllZVV09GaGcLbhoFZxYJfIyNklIaV55TD8BZ+1ZFqFqzoaq6ceVhc8KHLZxcCzc89BVZve3sm+VPFdKH8cSHmzHKz/mBXf70svvW6MaHSheM+dWyp56p9uAVEQcJ/z8RPxcKEeMpiTzNYCOaaZ2kVRsMj6dtOqF2oOHbgXWy0+hsyEMDF3CEnM/lZHjFysG80b/tscEGJfKtzeCClCHTk+0hsrSquijvhEvgpqrjHAFI7lLFoFYY16XW/O3N++yzPGe93yZRbFcux5EqJlsFCwXbON7lj9eV+Y1grqoymBZU1dlHtXWYjbtmYao1/mZ6luYCpEgoNiqYD4+84WUvKyPZ1XXpz67aupzaHTzMuwpOK3n6yg08X580CsSZQGOyOd4yTSeW2Y9zxfNVErxzF9i+v9Bz8wcXLRpuWfCfgLin7hm98qCD7+z1c8t7e3okDDzn6Nk09JnMZONNGYS6xTUSPiiqqmjgiwlzC/9404273HzzzQF5GjFvIPd3Y9NBm0Q48td6Vq1nqRMXbIMJwfFVz2z4g5GMwhBLhwUYXU1QzfRddRVmYzULVWt1qqqbx1nN9JeqmiVdSPsJ+sPi9RYJTFu8xknjZPncuXMfIa0d6ksditjRMdKO95+Jzu+ZWaPCkDZ3p/BIMyRgEGePLFRV1w+q0wudXPQBT0Y5tovDQ9VCPj+0ekeuTPx89bQv3TW3r+dvw4ODOPUJJfSNcANEGBzFcoA1luKk5JGsM4Q25kwvrtpZIdXJ+RO82lJVCYIAHZTAmXhSGhy0vWH4wEcWf+Am5Znn9FRba7nQhil1I0+GjFltCheapdZsuOOOO1b/34c+cmfO+EO9eIXKhYKToVOt2MbGMkxPhkbeyeKNMibja8zj4qRJanvC4OE5adr1xkeD4LBYbR4nPpIr9Aj/qID/sSs3QI31NcepczONaerFkJ1Pp0Y+N19x4oFFQGwUy0ChN9l6y83+j3z/zNhu2xf9pTxcfCCtVGylUnFH7rSH5/vOZ8y07cYYsXDs3FT6fihRnEo5jvygJ7/v0IL8gmb5lQcfv783DG5VnEQIFmhunMjj/CojgOsrbKgRdZsehs1g37IdzfRVlW5XVzs69Zgsj/nTRSs5jTTGs3UqEVpGhDZ0NsWrnM033eyOkxYvLk63vucTHx+MeCrD0xiGXPc5lmfLBuwHyuPc40re19v77Jnf/vYyM1sVdCtnvZXJiCd6fYoj20A9N2CoLA3gJjUmINPGUlVirCbSCQ427hZboTmvOT0mbSxGmRlI5cAmGG8EedhxzOP/9M3XXTZOJAwCm5Qrdy4YGVkr/0yX+mbI2kPbWaOSgbYnyJfxTBbSFuPykYiBtekyEi/Hojuo8E08lXOTQdU9QbTTU7WWr1oLm/lot0ZwfDWiMa8xntk5k9ecp1qrT1WF/UCoqjR/fLHFZKh4/9Zbb11tzptO+u0nnph/avmyl2PzIxEXQtRBJ0TbMOTTKyF4knUPHBBKXRG4ucqwEc0aclzw5Fa1lpPzfDFYqONS+b5NS/FfG8v+M8YLTz75ZDxSvNf3PCvY+OVwGkyb0L4JNx8zbTTsmsJHsq/K2Fhx02pBs2Fuz8svv2r9ZvH8a7PNNtjoCoMjhlBUOBfYPyxP30XdWIZpVWXUIetzl6jfMt56cpUEqiqq2lb2ZDowT1VdeVVtK4MZqur4GCdUW6dVa3RVdfNSVYUf1kUwTvD3iZhjBPckup20yYB9sKjqKMhLeQTjhKoyGAdVHVdmXOY0EpRPTIN1WiyqY/qo6tRlyAPEmAs+Dw9QAu5ZOKbRMFw6DsgedzWPSx2XW0tkPFyrsRldLklSMrWsNXffeOONyyufXXrDvP6+oXKxKHwi9NW472DQOVAzVWXgJqmLuFtau9eyXLzVTXUKhlaFOqBxQaIz464yxmsCA0+SVqvxHrvs9Cd+h6kDUauM9WKB6bjSSvuP6ng7zeZkaF/r6s2ZPzD/Gd/qMokSqRRH3JfeZqqBqrqJmclRHZ/O6N2GHF8sy0lLZP1CemA8kTh94t8X/dsD2uXJYj7o2TnX17MV363zNVcljtyGhgsfvI8oK58CdCy2DSPnBk9Dcz5ORPF6pYw53hvmxbfy+7PPPjuaQvRzPnvx4sXRgfvve7MmaWJUpVIqCx+QPGPE2Vhm9uF44LggVGudEObzMlKuzP/tH67drZV0LyldlRd93OB0yEcPcxxRL35XSFWFG6H/z961x8pVnPfvN+fsnt29axtUDAbsxiF2aIsDDVAbhaqqS1QkqlZKq7giRGkV/ihUlMQFAZWIlLZS1bcKqFHSVFSyRP5o3okSoSjk4QC2kwAJJER5KARsJ44fXPveu+9zzuT7ze7sPXfv2b0P32uvDUfnd2bmm2++mfnmPXPObl+uimT5Ug4HpGHlTP9xBPPhsdrp83oSdMcm4WJBTwSCVH602nG/luVT74P1UodhIV20PrNtEGFopNVsnDLFtHnWJz7QDvs//+2f9s28evJbpaBgi7oiZEXl+zLsMNV/RJn6CjaCZcBrtLwB5oyTaco4+1ZYI/WZhnNXq1Xhqq5ail7acdXVH3PEsXkMVo1uwqyBEF3X3OfQPANiepAh17CwQ9jPCLl94sQrSDoHjS4n1mhZdZqtefGysWQxj6FHcINAz04DgLYx0OoAYI7bEXMeXo43PYtPA93UpQeUkXDuNI0vu2j9E9e85a3PkG+p2LNnz8TXvvnUeyanptdabXdRVJYwKIrEIroykkR3BSgTfAxB6jr5TDu07FJmwcULv6jgNnaoE7VyoSitWv3Q5vUXPzZE5HlH/s0Nlz2mfdtLqR7x8V0fv9PDhdLpZNbVEUmEhRUEgZZdIK1WR+fCVkyhYA4eObL7nR/8oHZKc2P5wv8+dug3Nr/hvkKS/NwkiZ2IisL/1Dpx/LgUtB7wd67accfVX61u4jFXilEnocY5dru2o7tkztS0M39q5N5OxxA3iNI+yMR2QszS065VT/nZTqOwUE+A73aJCz5HJSU3sMuDz8syzFyhZ4GoKpY8LJSU7helPZ2TOdv/qB1QqQouFLmhUo7KvzQNOzMWNXfT7/3hwY0bLtuXxJ02O1smslgsCmdpYOK1OmjymS1hZaIlrxKSvtLwFStPLgD3iS47CqZ18sRx98OFnVbrs/fffvt0XpizSQO8FmdTAcynzfqKW/1n3aPs1NUo/7Pt9553vOPVN2958/OS2jjVI0nNnEA7qLx0ARAAeV65NNvrdHI9RxCB0XFk5bJdEKRxVZ62Wo23XLHlM7ve9rbuzHtEPHlewaZNW0/VajcWy6WCCQLhrg+POyjbCISDabdTF3dpM3TmUh5Mb6EYCH+ri22302rL2qh04L7duxf8vHcp8Ywz79/v3n2yMT39+Wq5pBOTlqim3fs9wOiyX1SeAi2pMBAuuFherBtNPfIKy5FU1lXfVJV4+6AcAMm//sM/f3bbFVsejRA0W/WGsD2sqUwIJ2WcrBpjBIGRvOUS6wTLclDuuLupG2I10zmrr1Sguz1xq/3dP7r55mMLxmkDVgZiQdbziYEZJlY6T74c2JdZLg40Av7kQ21m+tX93/722T/q0vTITiDefv11T0UIa1bPwVM974MOSFwl0l/EdI2BpzUYoAx3AhAAwxmW6cNJj+sodFTgjk9Ntaur2seXKe6MBgMgmmxRxTjQ7iG9C1h5nfVEn3EDuru4ccOGZwMrrbYeOZQKYT8NnEgTJCgfjVwM6ocdKZFlptsjSx9mZ3wE/Qflk54FeQjSAmOOFaLKfrqXg0f3/N+WiQvWvCEslXVA7oguO7QqwO0cqGwJBJI3wLk0QifFGWTjZxgP7qqtq66RxkxN4nZboiBs1qemn/u1TmcyG+Z8t4dB8EWdnNQ4seTkgvWhfMkYAAAJvElEQVSvqLsrp5tv1jNjjFuAqXypRBU9QitKW/vPtkjxwHeev0V5tKTmxnTNhg21G7Zd/WFpx3vXlCdE0liiqKBrAesY+Z5aJ03cTgcHEQ9xfXG3P2YZO+bz4MFcEwtlhX0E4fnYDmn3NNV1X4ekF8LCT2656SYtCrpeR54GOJH2yPMfRaP+WTeH8bBtcEHAY+VSqWQrUTS98dJL290aPCzUGaTX28mTtdrMYdhErCLW8+eJ8txdWiqHSWJmCdoXAvmIhfiW688ZJSdorPCpHg2oQl98+L8eGb+Xmq2OYprJQV0w3R7q3b/JR/QJGYvnp5khnxPWq7du/VKxEB6KdEcxL/3D8jwsc5QxiGG8C9Hz4mbDzdIZF+WwIeu27Rf/54EHTtG9VHzv6NHqoV8eeft0vXkBf0Ii1tVpoVBwuzzsKDg4cxdzUK7v4Afp3q3131udyYUBv6BjHqqVipSDwtE77rhj//XXX99xDK+Rx4cefvilWq32A5Yn9VsqlYT2081+J4kFgXGyEj1KY/0wOhFK0lQ6Ng0btnPdh7/06fV58Tx4552Hb3r7TXc2arWfTERlmTp1SgJjdAIU6aaodbAakGVOqPWcvgEIgFXLA3XlhbMcODGcfPXYjzuXXPL6xMcrZsD0Y/oAeVFOr28gv0w5IeLmCF+b4XF7knaacZocvPuWW1qD/dSiIlwNpkfvv39at1qfYocehQVXQdkhr0ZcWZlU3nJBOZz0aLp1lRXypcAkTe3TcaVynH7nIgA43XudqEMIAJJ3sYHn0ceVdve73z1VKUYH+L6Fz9Fi8tDXx0DGAKh6hmOAfcnOwbTRTaiguAizV83l3tWZdvN3onIJhWJJyqUJHTxDaTWbQt1w96Co7XAh4RwQiWF8nEARRZ1UQY8DJycnf1Gx9rz90cJhetA9leOSpt+slMqp6G5Mo1Z3x0rD+BdDd3VSd71TneRw0gpAd9W6L6dzchUWIzk5NXXp3ie/9aZh8t5/772Hlfejuhs3yX4s1Z0ffqFKeaYQdnd8GNgaSd1uDx3ibGMzeHSTtOgngH6bHQxklUCosRJ3p1IuHblOemctKyHxPJfBiVAWi80ugD4rJ5x0sJ9k2+BCgB9ZlMuV5rXXXOvG5hWou4xiZbBh3YVPxI2W27bVUwnhez5ess8MMJtB77eaJpXnkRdPFBaEyuUESFI7Zev1Z2/WbeQ83rNKM+y4mIJukXOwWqiBA8N1ndVJ1s4Yxh0TxdLTSadtWW6j0goMz/+ocEvxG4zBaJxZmjtu0IENgOus3SpGB6eg0z6UtNvPLyWuLO+//PdDW0yp9FuU3+q0OWkXrw+2O9aPdtwRxpcNx05p0J2ldV92nuUIjHEvzLKOxO2OXBCVnrk8ipb99xpyjl43XnnlzG1/9s5nGrXpGX7qzJ0w6uR0s8MOnUftLDuWm05itJ4EOtJC+BtjF1588aYn9n71tzWubsMfiHAb0L7z1ls/mtZqD5pW82hJ61rVBGKbdYmUV4+F9Sn9epA6l3/MdXnqOJlAt90AWPVkuRh0gsiIqGzY9MRf3vqulwH3BQDJQ6Hlg9xz5aEhXvfAEBWwz1J9OnWq7rXuanvQet2YabR2XHut+19Als+Q4GeefOXmzQeM2J/qWZdLdBy3hYMzIWKUpr4uV0ZbYg+AaEvvg7weji7zL0DD9Mi0jQIHIiIwRmgSnp8iqOBOpyVhAFsUvPzAX9/1LOnjBi13sdDpo4GqRTs2TSDTrkb/BjBrp01X6KQQdALQsPORlUM70OVJ220WBYOOFTZfsvErBZifAXC7HBKEmq/AQcSIh7VQe/emjTAM0wPdXd/hTwAqdz76IbSjRM8BrqltKkbBrxUIAGJNF20ea4SQiXJka0eO7fv4nj3LnkD88KWf/UlHTCnRyE3BiAk0EXrEzIGUkyH3ezCFQFKNWzOgniLK2of0Lljj2iUnPEyvaB4EqbCqaZOQQCB8z6cYRZLGiey46prP7dq1K+kFf80YUIVsveiiF4qhOUw9NdsNCYJgwfxrOBkGA0iik0lOeCiIO2ussmyDVgkJjMw0m5WgUvndJ195ZZ2Scu+/u+22yZ9//esf+tPfv3H7lRetfyiqTb94gUWt2OmINJpSNN10UnZiY51UJVLQupErbIWJAFz+lyrW6cBaHUpmQRmeTjugstWCHCjJ3QB9nXXOgwsDa9QvMEK7QShGxwilSEH7ENptJz645Y1bD88JOMQBJFa9CE1z4qBVpp93gJKVo3dn89EjLWgA6MvzzMB8mvejyXhoArN8pBGke9BNeLc3gdlwnpY1qTuCuqSZBWlZ3qydcRFO+QxETy0Py5m6sVoCVtj/iNrCMFR9WgmDoBHGsfsLKUP+ccE973vfpG0l3yiViqyt/Y6BDc6nEYC3zivEvkfGAszyZ8gjrcDcMMBcdzYwV1ocLGyS2vrM1It65jV+7/doglO2IjV1FHV1pWudzRcwa6ffCsDCaA1cAUErLeJv7rlrshgEL8Rx7DqalZa/FHm+AXrtQ1Lhb0FRRqpE17jpcEiF73TMTE01Nq1fv+/Ec89NO/ISH///9NPl49NTO3QrRqz4FMwVwrgJYWei6aAvS9ODbgA6SRMH6V1sqxzYe07hkQ4/4Xbv+RgcjRvTy/r03ss7p01jftCsT72oZWrZZ2j9O+3sABDYuWLSnpNlISYUQfjWT33ykxfKAtd/3Pvgyw/dc999d7/39lurIT6QTNc+v64y8f12o17j13gMzgGdJhd7SaJT54G46TcOAHDmk2FNvy2wTLRlHas04AbaxSbGd9OL5V9tPmDpegSwqLH5dNIOYF5w9lce3pP9VdeupaFrMJOYOt3qojEeuGr9+kZQCA+cPHmyxY6BqQLglAh0zSyNdg8A3roiJrA4eZxNcqtZV13pju07Dvztrl3L+rR4RRI9SkiasouyAHL1OSroYvwAzGPTdUs8jzgGhPrll5+aqTX2pmnaXig5wPx8ZcMAmKNPYK47y7sUOwDHDsAtAAAI61qpVJJqtXr4D3bufG7nzp3L0u++/fuvqM/Ut/pBTFbx4pEOXy5cu3atxJ3Olz/2kY8saSBYxaStpuhc2fxfshu23/Cs9m1ps9l05ZrLuEwigHl1kWUMYNPjX35842LEbtu2rf3+d/3F8x/4zHsffuSRf/+rN/765j/XqdMfI07ugrX/qKvmT2j69xUKxRfWrFnTWYzMceJRXTgd+TR59zCTfPSjmYWn6SQ2S+7LVrouhe3hKhpL+XoRFEbZHt5NMwv6001zFMhDkIcmkbXTvRyshIzlxJsXJi8tWVrfbqVhUuP6n18BAAD//0b9eMkAAAAGSURBVAMAR7jCKy6c6M4AAAAASUVORK5CYII=" style="width:140px;height:auto;object-fit:contain;"></div>', unsafe_allow_html=True)
st.sidebar.markdown("## ⚡ Gestão UFAC")

# Menu de perfil, troca de senha e painel admin
auth.render_sidebar_menu()

with st.sidebar:
    # Botão de atualização
    if st.button("☁️ Atualizar", use_container_width=True, type="secondary", key="sidebar_refresh"):
        st.session_state.tarefas = buscar_todas_tarefas_ufac()
        st.rerun()
    st.caption(f"{len(st.session_state.tarefas)} registros • {agora_ac().strftime('%H:%M')}")

    st.divider()
    st.markdown("### 🔍 Filtros")

    # Contrato — botões individuais com gap
    df = pd.DataFrame(st.session_state.tarefas)
    contratos_disponiveis = sorted([x for x in df["Contrato"].dropna().unique().tolist() if x.strip()]) if not df.empty else []
    if "contratos_set" not in st.session_state:
        st.session_state.contratos_set = set(contratos_disponiveis)
    else:
        # Sanitize
        st.session_state.contratos_set = {c for c in st.session_state.contratos_set if c in contratos_disponiveis}
        if not st.session_state.contratos_set:
            st.session_state.contratos_set = set(contratos_disponiveis)
    st.markdown("**Contrato**")
    contratos_cols = st.columns(len(contratos_disponiveis), gap="small")
    for i, ct in enumerate(contratos_disponiveis):
        ativo = ct in st.session_state.contratos_set
        label = f"\u2705 {ct}" if ativo else ct
        with contratos_cols[i]:
            if st.button(label, key=f"ct_{ct}", use_container_width=True, type="primary" if ativo else "secondary"):
                if ativo:
                    st.session_state.contratos_set.discard(ct)
                else:
                    st.session_state.contratos_set.add(ct)
                # Se remover todos, volta ambos
                if not st.session_state.contratos_set:
                    st.session_state.contratos_set = set(contratos_disponiveis)
                st.rerun()
    contratos_selecionados = list(st.session_state.contratos_set)

    # Status
    status_disponiveis = ["TODOS", "EM ABERTO", "EM ORÇAMENTO", "PARA EXECUÇÃO",
                          "EM EXECUÇÃO", "FISCALIZAÇÃO", "CONCLUÍDA", "FECHADA", "CANCELADA"]
    status_selecionado = st.selectbox("Situação", status_disponiveis, key="filtro_status")

    # Número do processo (filtro universal)
    st.markdown("**🔢 Número do Processo**")
    processo_search = st.text_input("Buscar por Nº processo SEI", "", key="filtro_processo",
                                     placeholder="Ex: 23107.011272/2026-90", label_visibility="collapsed")

    # Local
    locais = sorted([x for x in df["Local do servico"].dropna().unique().tolist() if x.strip()]) if not df.empty else []
    local_selecionado = st.selectbox("Local do serviço", ["TODOS"] + locais, key="filtro_local")

    # Período
    st.markdown("**📅 Período (data de abertura)**")
    periodo_opts = ["Último mês", "Últimos 3 meses", "Últimos 6 meses", "Últimos 12 meses", "Personalizado"]
    periodo_sel = st.radio("Período", periodo_opts, index=2, key="filtro_periodo",
                           label_visibility="collapsed", horizontal=True)

    hoje = datetime.today().date()
    periodo_map = {
        "Último mês": (hoje - timedelta(days=30), hoje),
        "Últimos 3 meses": (hoje - timedelta(days=90), hoje),
        "Últimos 6 meses": (hoje - timedelta(days=180), hoje),
        "Últimos 12 meses": (hoje - timedelta(days=365), hoje),
    }

    if periodo_sel == "Personalizado":
        col1, col2 = st.columns(2)
        with col1:
            data_ini = st.date_input("De", hoje - timedelta(days=90), key="filtro_dt_ini")
        with col2:
            data_fim = st.date_input("Até", hoje, key="filtro_dt_fim")
    else:
        data_ini, data_fim = periodo_map[periodo_sel]
        st.caption(f"{data_ini.strftime('%d/%m')} a {data_fim.strftime('%d/%m/%Y')}")

    # Badges de filtros ativos
    badges = []
    if st.session_state.get("contratos_set"):
        sel = st.session_state.contratos_set
        if len(sel) < len(contratos_disponiveis):
            for c in sorted(sel):
                badges.append(f"\U0001f4cc {c}")
    if st.session_state.get("filtro_periodo", ""):
        p = st.session_state.filtro_periodo
        badges.append(f"\u23f1 {p}")
    if badges:
        st.markdown(
            " ".join(f'<span style="display:inline-block;background:#1e293b;border:1px solid #475569;border-radius:4px;padding:2px 8px;margin:2px 3px;font-size:11px;color:#e2e8f0;">{b}</span>'
                    for b in badges),
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown(f"**📊 Registros:** {len(st.session_state.tarefas)} O.S. UFAC")
    st.caption(f"Última atualização: {agora_ac().strftime('%d/%m/%Y às %H:%M')}")


# ── Aplicar filtros ─────────────────────────────────────────

def aplicar_filtros(tarefas: list, contratos, status, local, dt_ini, dt_fim, processo="") -> list:
    filtradas = []
    for os in tarefas:
        c = str(os.get("Contrato", "")).strip()
        if contratos and c not in contratos:
            continue
        if status != "TODOS":
            etapa = str(os.get("Etapa", "")).strip().upper()
            estado = str(os.get("Estado", "")).strip().upper()
            kanban_st = categorizar_status_kanban(os).upper()
            if status not in [etapa, estado, kanban_st]:
                # Tenta match parcial
                status_map = {
                    "EM ABERTO": ["EM ABERTO", "ABERTO", "SOLICITAÇÕES"],
                    "EM ORÇAMENTO": ["ORÇAMENTO", "ORÇAMENTO EM ANÁLISE"],
                    "PARA EXECUÇÃO": ["PARA EXECUÇÃO", "EXECUÇÃO"],
                    "EM EXECUÇÃO": ["EM EXECUÇÃO", "EXECUTANDO"],
                    "FISCALIZAÇÃO": ["FISCALIZAÇÃO", "CONFORMIDADE", "APROVADOS"],
                    "CONCLUÍDA": ["CONCLUÍDA", "FECHADA"],
                    "FECHADA": ["FECHADA", "CONCLUÍDA"],
                    "CANCELADA": ["CANCELADA"],
                }
                match_list = status_map.get(status, [status])
                if not any(m in etapa for m in match_list) and not any(m in estado for m in match_list):
                    continue
        # Filtro processo (busca parcial — universal)
        if processo:
            num_proc = str(os.get("Numero do processo", "")).strip()
            if processo not in num_proc:
                continue

        if local != "TODOS":
            loc = str(os.get("Local do servico", os.get("custom_187", ""))).strip()
            if loc != local:
                continue
        # Período (Criada em — data de abertura)
        if dt_ini is not None and dt_fim is not None:
            try:
                criada = str(os.get("created_at", "")).strip()[:10]
                if criada and len(criada) == 10:
                    dt = datetime.strptime(criada, "%Y-%m-%d").date()
                    if dt < dt_ini or dt > dt_fim:
                        continue
            except:
                pass
        filtradas.append(os)
    return filtradas

# ── Pendências (NUNCA usa filtro de período) ───────────────
tarefas_pendencias = aplicar_filtros(
    st.session_state.tarefas,
    contratos_selecionados,
    status_selecionado,
    local_selecionado,
    None, None,
    processo=st.session_state.get("filtro_processo", "")
)

# ── Main content (usa TODOS os filtros, incluindo período) ─
tarefas_filtradas = aplicar_filtros(
    st.session_state.tarefas,
    contratos_selecionados,
    status_selecionado,
    local_selecionado,
    data_ini, data_fim,
    processo=st.session_state.get("filtro_processo", "")
)

# ── FUNÇÃO AUXILIAR: DADOS FINANCEIROS ─────────────────────

def analisar_financeiro(tarefas: list) -> dict:
    """Agrega dados financeiros por competência"""
    from collections import defaultdict
    import re

    comps = defaultdict(lambda: {'total': 0.0, 'mo': 0.0, 'ma': 0.0, 'qtd': 0})

    def sf(v):
        if not v: return 0.0
        try: return float(str(v).replace('R$','').replace('.','').replace(',','.').strip())
        except: return 0.0

    def norm_compet(c):
        c = str(c).strip()
        m = re.match(r'(\d{1,2})/(\d{4})', c)
        if m: return f"{int(m.group(1)):02d}/{m.group(2)}"
        return c

    for os in tarefas:
        compet = os.get("Competencia", "")
        if compet:
            compet = norm_compet(compet)
            comps[compet]['total'] += sf(os.get('Valor total',''))
            comps[compet]['mo'] += sf(os.get('Valor M.O',''))
            comps[compet]['ma'] += sf(os.get('Valor M.A',''))
            comps[compet]['qtd'] += 1

    competencias_ordenadas = sorted(comps.keys(),
        key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))

    total_geral = sum(comps[c]['total'] for c in competencias_ordenadas)
    total_mo = sum(comps[c]['mo'] for c in competencias_ordenadas)
    total_ma = sum(comps[c]['ma'] for c in competencias_ordenadas)
    ultima = competencias_ordenadas[-1] if competencias_ordenadas else ""
    ultima_dados = comps[ultima] if ultima else {}

    return {
        'competencias': competencias_ordenadas,
        'dados': {c: comps[c] for c in competencias_ordenadas},
        'total_geral': total_geral,
        'total_mo': total_mo,
        'total_ma': total_ma,
        'ultima_competencia': ultima,
        'ultima_dados': ultima_dados
    }

def plot_medicoes(competencias, dados):
    """Gráfico de barras: valor medido por competência"""
    import plotly.graph_objects as go

    compet = list(competencias)
    totais = [dados[c]['total'] for c in compet]
    mos = [dados[c]['mo'] for c in compet]
    mas = [dados[c]['ma'] for c in compet]

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Mão de Obra', x=compet, y=mos,
                         marker_color='#4a90d9', hovertemplate='MO: R$ %{y:,.2f}<extra></extra>'))
    fig.add_trace(go.Bar(name='Material', x=compet, y=mas,
                         marker_color='#7ecb7e', hovertemplate='MA: R$ %{y:,.2f}<extra></extra>'))
    fig.add_trace(go.Bar(name='Total', x=compet, y=totais,
                         marker_color='#e6a817', opacity=0.5,
                         hovertemplate='Total: R$ %{y:,.2f}<extra></extra>'))

    fig.update_layout(
        barmode='group',
        template='plotly_dark',
        height=350,
        margin=dict(l=60, r=20, t=20, b=40),
        legend=dict(orientation='h', y=1.12, x=0.5, xanchor='center'),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor="#1e293b",
            bordercolor="#475569",
            font_size=12,
            font_color="#f1f5f9"
        ),
        yaxis=dict(
            title=dict(text="Valor (R$)", font=dict(size=11, color="#94a3b8")),
            tickprefix="R$ ",
            tickformat=",.0f",
            gridcolor="#1e293b",
            zerolinecolor="#334155",
            tickfont=dict(size=10, color="#94a3b8")
        ),
        xaxis=dict(
            tickfont=dict(size=10, color="#94a3b8"),
            gridcolor="rgba(0,0,0,0)"
        ),
        plot_bgcolor="#0f172a",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    return fig

# ── FINANCEIRO GERAL (saldo — só filtro de contrato, TODAS competências) ─
def _comp_sort_key(v):
    """Retorna YYYYMM para ordenação"""
    m = re.match(r'(\d{1,2})/(\d{4})', str(v).strip())
    if m: return int(m.group(2)) * 100 + int(m.group(1))
    return 0
_todas_comp = [t for t in st.session_state.tarefas if _comp_sort_key(t.get("Competencia", ""))]
if contratos_selecionados:
    _todas_comp = [t for t in _todas_comp if str(t.get("Contrato", "")).strip() in contratos_selecionados]
# Só competências a partir de 10/2025 (comparação numérica YYYYMM)
_todas_comp = [t for t in _todas_comp if _comp_sort_key(t.get("Competencia", "")) >= 202510]
fin_geral = analisar_financeiro(_todas_comp)

# ── FINANCEIRO DO PAINEL (últimos 12 meses, respeita filtros) ─
tarefas_comp = [t for t in tarefas_pendencias if str(t.get("Competencia", "")).strip()]
fin = analisar_financeiro(tarefas_comp)

# Trava no período de 12 meses (out a out do contrato)
FIN_12M = fin['competencias'][-12:] if len(fin['competencias']) > 12 else fin['competencias']
fin = {
    'competencias': FIN_12M,
    'dados': {c: fin['dados'][c] for c in FIN_12M},
    'total_geral': sum(fin['dados'][c]['total'] for c in FIN_12M),
    'total_mo': sum(fin['dados'][c]['mo'] for c in FIN_12M),
    'total_ma': sum(fin['dados'][c]['ma'] for c in FIN_12M),
    'ultima_competencia': FIN_12M[-1] if FIN_12M else '',
}



# ── SEÇÃO 2: ALERTAS E PENDÊNCIAS ──────────────────────────

# ── Header + Saldo do Contrato (sempre em evid├¬ncia no topo) ─
hcol1, hcol2 = st.columns([2, 1])
with hcol1:
    st.markdown("# ⚡ Gestão Contratual UFAC")
    st.caption("Portal Operacional — Vivace Engenharia")
    # Filtros ativos abaixo do título
    _badges_top = []
    if contratos_selecionados and len(contratos_selecionados) < len(contratos_disponiveis):
        for c in sorted(contratos_selecionados):
            _badges_top.append(c)
    if st.session_state.get("filtro_periodo", ""):
        _badges_top.append(f"⏱ {st.session_state.filtro_periodo}")
    if _badges_top:
        st.markdown(
            " ".join(f'<span style="display:inline-block;background:#1e293b;border:1px solid #475569;border-radius:4px;padding:2px 8px;margin:2px 3px;font-size:11px;color:#e2e8f0;">📌 {b}</span>'
                    for b in _badges_top),
            unsafe_allow_html=True
        )
    # ── Barra de ações (3 botões lado a lado) ──
    ac1, ac2, ac3 = st.columns(3, gap="small")

    estilo_btn = (
        "display:flex;align-items:center;justify-content:center;gap:6px;"
        "background:#1e293b;border:1px solid #334155;border-radius:6px;"
        "padding:10px 12px;color:#e2e8f0;text-decoration:none;"
        "font-size:13px;font-weight:500;width:100%;text-align:center;"
        "transition:all 0.15s;cursor:pointer;"
    )

    with ac1:
        st.markdown(f"""
        <a href="https://{GUEST_HASH}-share.runrun.it/pt-BR/guest/tasks/" target="_blank"
           style="{estilo_btn}"
           onmouseover="this.style.borderColor='#4a90d9';this.style.color='#f1f5f9'"
           onmouseout="this.style.borderColor='#334155';this.style.color='#e2e8f0'">
            👉 Ver O.S. no RUNRUN.it
        </a>
        """, unsafe_allow_html=True)

    with ac2:
        st.markdown(f"""
        <a href="https://runrun.it/share/form/oJUZ2dYeVZhxikEK" target="_blank"
           style="{estilo_btn}"
           onmouseover="this.style.borderColor='#4a90d9';this.style.color='#f1f5f9'"
           onmouseout="this.style.borderColor='#334155';this.style.color='#e2e8f0'">
            ➕ Nova O.S.
        </a>
        """, unsafe_allow_html=True)

    with ac3:
        # Botão toggle para exportador — mesma estética
        if st.button("📄 Exportar Relatório", key="toggle_exportador", use_container_width=True,
                     type="secondary",
                     help="Exportar relatório Excel para fiscalização"):
            st.session_state.mostrar_exportador = not st.session_state.get("mostrar_exportador", False)

    # ── Expansão do exportador ──
    if st.session_state.get("mostrar_exportador", False):
        if tarefas_filtradas:
            _df_export = pd.DataFrame(tarefas_filtradas)
            render_exportacao_fiscal(_df_export)
        else:
            st.info("Nenhuma O.S. nos filtros atuais.")
with hcol2:
    contratos_ativos = contratos_selecionados if contratos_selecionados else list(CONTRATOS.keys())
    _st = sum(
        CONTRATOS.get(ct, {}).get('orcamento_aditivo', CONTRATOS.get(ct, {}).get('orcamento', 0))
        for ct in contratos_ativos
    )
    _usado = fin_geral['total_geral']  # tudo medido, independe de filtro local/fiscal/período
    _sr = _st - _usado
    _pt = (_usado / _st * 100) if _st else 0
    st.markdown(f'''
    <div style="background:#0d2818;border:2px solid #2a6a3a;border-radius:12px;padding:12px 16px;text-align:center;">
        <div style="color:#5ab85a;font-size:10px;text-transform:uppercase;letter-spacing:1px;">🏦 Saldo do Contrato</div>
        <div style="color:#fff;font-size:26px;font-weight:700;margin:2px 0;">
            R$ {_sr:,.2f}
        </div>
        <div style="color:#aaa;font-size:11px;">
            {_pt:.1f}% utilizado &middot; R$ {_st:,.0f} orçamento
        </div>
        <div style="color:#5a8a5a;font-size:9px;margin-top:4px;">
            📅 período {fin_geral['competencias'][0]} a {fin_geral['competencias'][-1]} &middot; competências >= 10/2025
        </div>
    </div>
    ''', unsafe_allow_html=True)

# Mapeamento de etapas para cada coluna
VIVACE_ETAPAS = ["PARA LEVANTAMENTO", "PARA EXECUÇÃO", "ATRASADAS", "ELABORAR CONFORMIDADE",
                  "ELABORAR RELATÓRIO/ORÇAMENTO", "EM ABERTO", "PENDÊNCIAS"]
UFAC_ETAPAS = ["CONFORMIDADE EM ANÁLISE DA FISCALIZAÇÃO", "ORÇAMENTO EM ANÁLISE DA FISCALIZAÇÃO",
               "APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO"]

# Classifica tarefas (apenas das pendências, sem filtro de período)
# Ordena por Entrega desejada (mais antiga primeiro)
def _sort_oldest(os):
    d = str(os.get("Entrega desejada", ""))[:10]
    try:
        return datetime.strptime(d, "%Y-%m-%d").timestamp() if len(d) == 10 else 9999999999
    except:
        return 9999999999

pend_vivace = []
pend_fiscal = []
for os in tarefas_pendencias:
    etapa = str(os.get("Etapa", "") or os.get("board_stage_name", "")).strip().upper()
    if etapa in VIVACE_ETAPAS:
        pend_vivace.append(os)
    elif etapa in UFAC_ETAPAS:
        pend_fiscal.append(os)

# Mais antigas primeiro
pend_vivace.sort(key=_sort_oldest)
pend_fiscal.sort(key=_sort_oldest)

# CSS de cores
st.markdown("""
<style>
.pend-card {
    border-radius: 6px; padding: 8px 10px; margin-bottom: 4px;
    font-size: 12px;
}
.vivace-card { background: #1a2e1a; border-left: 3px solid #5ab85a; }
.ufac-card { background: #2e1a1a; border-left: 3px solid #d94a4a; }
.counter-bar {
    text-align: center; padding: 6px; border-radius: 6px;
    font-size: 12px; font-weight: 600; margin: 4px 0;
}
.vivace-bar { background: #1a2e1a; color: #7ecb7e; border: 1px solid #2a4a2a; }
.ufac-bar { background: #2e1a1a; color: #e66c6c; border: 1px solid #4a2a2a; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 🚨 Alertas e Pendências")

col_vivace, col_ufac = st.columns(2)

# ── Helper para renderizar card (apenas Abrir via guest link) ──
def render_pend_card(os, side):
    os_id = os.get("ID", "")
    titulo = str(os.get("Titulo", os.get("title", "")))[:60]
    local = str(os.get("Local do servico", ""))[:35]
    etapa = str(os.get("Etapa", ""))
    contrato = os.get("Contrato", "—")
    valor = extrair_valor_total(os)
    entrega = str(os.get("Entrega desejada", ""))[:10]
    guest_url = f"https://{GUEST_HASH}-share.runrun.it/pt-BR/guest/tasks/{os_id}"

    # Links
    link_sit = str(os.get("Link do relatorio situacional", "")).strip()
    link_fin = str(os.get("Link do relatorio final", "")).strip()
    link_orcp = str(os.get("Link do orcamento previo", "")).strip()
    link_orcf = str(os.get("Link do orcamento final", "")).strip()

    with st.expander(f"#{os_id} — {titulo[:40]}...", expanded=False):
        st.markdown(f'''
        <style>
        .plink-row {{
            margin-bottom:3px;
        }}
        .plink-a {{
            display:inline-flex;align-items:center;gap:4px;
            background:#1a2a1a;border:1px solid #2a4a2a;
            border-radius:4px;padding:3px 8px;
            color:#7ecb7e;font-size:11px;text-decoration:none;
            width:100%;
        }}
        .pinfo-row {{
            display:flex;justify-content:space-between;
            padding:2px 0;border-bottom:1px solid #222;
            font-size:11px;
        }}
        .pinfo-label {{ color:#888; }}
        .pinfo-value {{ color:#ddd; font-weight:500; }}
        </style>
        ''', unsafe_allow_html=True)

        st.markdown(f'''
        <div class="pend-card {side}-card">
            <div style="color:#999;font-size:11px;">{etapa}{' | ' + local if local else ''}</div>
        </div>
        ''', unsafe_allow_html=True)

        # ── Links estilo ──
        links_html = ""
        for lbl, url, ico in [
            ("Relat. Situacional", link_sit, "📋"),
            ("Relat. Final", link_fin, "✅"),
            ("Orç. Prévio", link_orcp, "💰"),
            ("Orç. Final", link_orcf, "📊"),
        ]:
            if url and url not in ("", "-", "#N/A"):
                links_html += f'''
                <div class="plink-row">
                    <a href="{url}" target="_blank" class="plink-a">{ico} {lbl}</a>
                </div>'''

        if links_html:
            st.markdown(f'<div style="margin:6px 0;"><div style="color:#7ecb7e;font-weight:600;font-size:11px;margin-bottom:3px;">🔗 Documentos</div>{links_html}</div>', unsafe_allow_html=True)
        else:
            st.caption("📎 Nenhum documento vinculado")

        # ── Info b├ísicas ──
        info_items = [
            ("📋 Etapa", etapa or "—"),
            ("🏢 Contrato", contrato or "—"),
            ("💰 Valor Total", formatar_moeda(valor) if valor else "—"),
            ("📅 Entrega", entrega or "—"),
        ]
        rows = ""
        for lbl, val in info_items:
            rows += f'<div class="pinfo-row"><span class="pinfo-label">{lbl}</span><span class="pinfo-value">{val}</span></div>'

        st.markdown(f'<div style="background:#151515;border:1px solid #2a2a2a;border-radius:6px;padding:4px 8px;margin-bottom:6px;">{rows}</div>', unsafe_allow_html=True)

        # Link guest
        st.link_button("🔗 Abrir no Runrun.it (guest)", guest_url, use_container_width=True)
        st.caption("⚠️ Link para o fiscal — abre sem login.")


with col_vivace:
    st.markdown("<h4 style='color:#7ecb7e;margin:0 0 4px 0;'>🏗️ Vivace (Contratada)</h4>",
                unsafe_allow_html=True)
    total_v = len(pend_vivace)
    with st.container(height=300):
        for os in pend_vivace:
            render_pend_card(os, "vivace")
    st.markdown(f"<div class='counter-bar vivace-bar'>+{total_v} pendência{'s' if total_v != 1 else ''}</div>",
                unsafe_allow_html=True)

with col_ufac:
    st.markdown("<h4 style='color:#e66c6c;margin:0 0 4px 0;'>🏛️ UFAC (Fiscalização)</h4>",
                unsafe_allow_html=True)
    total_u = len(pend_fiscal)
    with st.container(height=300):
        for os in pend_fiscal:
            render_pend_card(os, "ufac")
    st.markdown(f"<div class='counter-bar ufac-bar'>+{total_u} pendência{'s' if total_u != 1 else ''}</div>",
                unsafe_allow_html=True)

if not pend_vivace and not pend_fiscal:
    st.success("🎯 Todas as O.S. estão em dia. Nenhuma pendência crítica.")

st.divider()


# ── SEÇÃO 3: FORMULÁRIO DE ABERTURA DE O.S. ───────────────




# ── SEÇÃO 4: DADOS FINANCEIROS ─────────────────────────────

with st.container():
    st.markdown("### 💰 Painel Financeiro")
    st.caption(f"📅 Período de fechamento: **{fin['competencias'][0]} a {fin['competencias'][-1]}** · últimos 12 meses")

    # Multi-select de competências (pode selecionar mais de uma)
    competencias_opcoes = fin['competencias']  # TODAS é implícito (desmarcar = todas)
    compet_selecionadas = st.multiselect(
        "🔎 Filtrar por competência de fechamento",
        competencias_opcoes,
        default=[],
        key="filtro_competencia",
        placeholder="Todas as competências"
    )

    # Se nenhuma selecionada → usa TODAS
    usar_todas = len(compet_selecionadas) == 0
    if usar_todas:
        compet_selecionadas = competencias_opcoes

    # Agrega dados das competências selecionadas
    total_exibir = sum(fin['dados'].get(c, {}).get('total', 0) for c in compet_selecionadas)
    mo_exibir = sum(fin['dados'].get(c, {}).get('mo', 0) for c in compet_selecionadas)
    ma_exibir = sum(fin['dados'].get(c, {}).get('ma', 0) for c in compet_selecionadas)
    qtd_exibir = sum(fin['dados'].get(c, {}).get('qtd', 0) for c in compet_selecionadas)
    # Média: total de todas as O.S. / quantidade de competências selecionadas
    valor_medio = total_exibir / len(compet_selecionadas) if compet_selecionadas else 0

    # Saldo contratual (respeita filtro de contrato)
    contratos_ativos = contratos_selecionados if contratos_selecionados else list(CONTRATOS.keys())
    saldo_total = sum(
        CONTRATOS.get(ct, {}).get('orcamento_aditivo', CONTRATOS.get(ct, {}).get('orcamento', 0))
        for ct in contratos_ativos
    )
    saldo_restante = saldo_total - total_exibir
    pct_usado = (total_exibir / saldo_total * 100) if saldo_total else 0

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        st.metric(
            "💰 Valor Total Medido",
            f"R$ {total_exibir:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            help=f"Total acumulado{' em ' + ', '.join(compet_selecionadas) if not usar_todas else ''}"
        )
    with col_f2:
        st.metric(
            "🔧 Mão de Obra",
            f"R$ {mo_exibir:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            help=f"Total MO{' em ' + ', '.join(compet_selecionadas) if not usar_todas else ' acumulado'}"
        )
    with col_f3:
        st.metric(
            "📦 Material",
            f"R$ {ma_exibir:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            help=f"Total MA{' em ' + ', '.join(compet_selecionadas) if not usar_todas else ' acumulado'}"
        )
    with col_f4:
        st.metric(
            "📊 Valor Médio Medido / Competência",
            f"R$ {valor_medio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            delta=f"{qtd_exibir} O.S. em {len(compet_selecionadas)} competências",
            help=f"(R$ total de O.S.) / (qtde competências) — filtrado por contrato, fiscal e local"
        )

    # Gráfico
    if competencias_opcoes:
        comp_list = fin['competencias']
        dados_c = fin['dados']
        import plotly.graph_objects as go
        compet = list(comp_list)
        totais = [dados_c[c]['total'] for c in compet]
        mos = [dados_c[c]['mo'] for c in compet]
        mas = [dados_c[c]['ma'] for c in compet]
        cores = ['#4a90d9' if c in compet_selecionadas else '#2a2a3e' for c in compet]

        media_med = sum(totais) / len(totais) if totais else 0
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Mão de Obra', x=compet, y=mos,
                             marker_color='#4a90d9',
                             hovertemplate='MO: R$ %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Bar(name='Material', x=compet, y=mas,
                             marker_color='#7ecb7e',
                             hovertemplate='MA: R$ %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Scatter(name='Valor Total', x=compet, y=totais,
                                 mode='lines+markers',
                                 line=dict(color='#ffd700', width=2.5),
                                 marker=dict(size=8, symbol='diamond'),
                                 hovertemplate='Total: R$ %{y:,.2f}<extra></extra>'))
        fig.add_hline(y=media_med, line_dash='dash',
                      line_color='#ff6b6b', line_width=2,
                      annotation_text=f'Média: R$ {media_med:,.0f}',
                      annotation_position='top right',
                      annotation_font=dict(size=12, color='#ff6b6b'))
        fig.update_layout(
            barmode='stack',
            template='plotly_dark',
            height=350,
            margin=dict(l=60, r=20, t=20, b=40),
            legend=dict(orientation='h', y=1.12),
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor="#1e293b",
                bordercolor="#475569",
                font_size=12,
                font_color="#f1f5f9"
            ),
            yaxis=dict(
                title=dict(text="Valor (R$)", font=dict(size=11, color="#94a3b8")),
                tickprefix="R$ ",
                tickformat=",.0f",
                gridcolor="#1e293b",
                zerolinecolor="#334155",
                tickfont=dict(size=10, color="#94a3b8")
            ),
            xaxis=dict(
                tickfont=dict(size=10, color="#94a3b8"),
                gridcolor="rgba(0,0,0,0)"
            ),
            plot_bgcolor="#0f172a",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig, use_container_width=True, key="grafico_comp_detalhe")

st.divider()



# ── SEÇÃO 5: INDICADORES GERAIS E POR CONTRATO ────────────

with st.container():
    st.markdown("### 📊 Indicadores Gerais e Por Contrato")
    st.caption("Filtros globais: Contrato · Status · Fiscal · Local do serviço · Período (data de abertura)")

    if tarefas_filtradas:
        df_f = pd.DataFrame(tarefas_filtradas)

        # ── A. Fila de Execução Operacional ──
        STATUS_FILA_OP = ['PARA LEVANTAMENTO', 'PARA EXECUÇÃO', 'ATRASADAS']
        mask_fila_op = df_f['Estado'].str.strip().str.upper().isin(STATUS_FILA_OP)
        fila_op_count = int(mask_fila_op.sum())

        # ── B. Demandas Emergenciais/Urgentes Ativas ──
        TIPOS_CRITICOS = ['DEMANDA EMERGENCIAL', 'DEMANDA URGENTE']
        STATUS_ATIVAS = ['EM ABERTO', 'PARA LEVANTAMENTO', 'PARA EXECUÇÃO', 'ATRASADAS',
                         'ELABORAR RELATÓRIO/ORÇAMENTO', 'PENDÊNCIAS']
        mask_emerg_tipo = df_f['Tipo'].str.strip().str.upper().isin(TIPOS_CRITICOS)
        mask_emerg_estado = df_f['Estado'].str.strip().str.upper().isin(STATUS_ATIVAS)
        emerg_count = int((mask_emerg_tipo & mask_emerg_estado).sum())

        # ── C. O.S. Atrasadas (Alerta Vermelho) ──
        mask_atras = df_f['Estado'].str.strip().str.upper() == 'ATRASADAS'
        atras_count = int(mask_atras.sum())

        # ── D. Total de O.S. ──
        total_os = len(df_f)

        # ── E. Taxa de Conclusão ──
        STATUS_CONCLUIDO = ['CONCLUÍDAS', 'ENCERRADAS', 'CONCLUÍDA', 'FECHADA']
        concluidas_count = int(df_f['Estado'].str.strip().str.upper().isin(STATUS_CONCLUIDO).sum())
        taxa_conclusao = (concluidas_count / total_os * 100) if total_os else 0

        # ── Render cards topo (5 colunas) ──
        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric(
                "📋 Fila de Execução Operacional",
                f"{fila_op_count}",
                help="O.S. em PARA LEVANTAMENTO, PARA EXECUÇÃO ou ATRASADAS"
            )
        with c2:
            st.metric(
                "⚡ Demandas Emergenciais/Urgentes Ativas",
                f"{emerg_count}",
                help="Tipo EMERGENCIAL/URGENTE · Estado em aberto, execução, atrasadas ou pendências"
            )
        with c3:
            st.metric(
                "🔴 O.S. Atrasadas",
                f"{atras_count}",
                help="Estado = ATRASADAS",
            )
        with c4:
            st.metric(
                "📋 Total de O.S.",
                f"{total_os}",
                help="Total de O.S. após aplicação dos filtros globais"
            )
        with c5:
            st.metric(
                "✅ Taxa de Conclusão",
                f"{taxa_conclusao:.1f}%",
                delta=f"{concluidas_count}/{total_os}",
                help="(Concluídas + Encerradas) / Total de O.S. × 100"
            )

        # ── Seção: Por Contrato ──
        st.markdown("#### 📑 Por Contrato")

        # Estados para cada indicador
        STATUS_MEDICAO = ['PARA PAGAMENTO', 'FINALIZADAS EM FECHAMENTO DE MEDIÇÃO']
        STATUS_CONFORMIDADE = ['CONFORMIDADE EM ANÁLISE DA FISCALIZAÇÃO', 'CONFORMIDADE DEMANDANTE']

        cols_ct = st.columns(len(contratos_selecionados) if contratos_selecionados else 2)
        for i, ct in enumerate(contratos_selecionados if contratos_selecionados else []):
            df_ct = df_f[df_f['Contrato'].str.strip() == ct]

            # A. O.S. para Medição (soma financeira)
            mask_med = df_ct['Estado'].str.strip().str.upper().isin(STATUS_MEDICAO)
            df_med = df_ct[mask_med]
            valor_med = df_med['Valor total'].apply(
                lambda x: extrair_valor_total({"Valor total": x}) if pd.notna(x) else 0
            ).sum()
            qtd_med = len(df_med)

            # B. O.S. Faltando Conformidade (CONFORMIDADE EM ANÁLISE + CONFORMIDADE DEMANDANTE)
            mask_conf = df_ct['Estado'].str.strip().str.upper().isin(STATUS_CONFORMIDADE)
            qtd_conf = int(mask_conf.sum())

            with cols_ct[i % len(cols_ct)]:
                # Card O.S. para Medição
                st.metric(
                    f"📋 {ct} — O.S. para Medição",
                    formatar_moeda(valor_med) if qtd_med else "R$ 0,00",
                    delta=f"{qtd_med} O.S." if qtd_med else "0 O.S.",
                    delta_color="normal"
                )
                # Card Faltando Conformidade (logo abaixo)
                kpi_conformidade(ct, qtd_conf)
    else:
        st.info("Nenhuma O.S. encontrada com os filtros atuais.")

st.divider()


# ── SEÇÃO 6: KANBAN OPERACIONAL ────────────────────────────

st.markdown("### Kanban Operacional")

# Colunas Kanban (ordenadas por fluxo operacional)
KANBAN_COLUNAS = [
    "EM ABERTO",
    "ELABORAÇÃO DE ORÇAMENTO OU CONFORMIDADE",
    "FISCALIZAÇÃO",
    "EM EXECUÇÃO",
    "CONCLUÍDA",
    "ENCERRADAS",
]

def _limpar_texto(s):
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").strip().upper()

def get_kanban_data(tarefas):
    """Separa tarefas por coluna Kanban"""
    colunas = {col: [] for col in KANBAN_COLUNAS}
    colunas_clean = {_limpar_texto(col): col for col in KANBAN_COLUNAS}
    for os in tarefas:
        cat = categorizar_status_kanban(os)
        if cat in colunas:
            colunas[cat].append(os)
        else:
            cat_clean = _limpar_texto(cat)
            col_target = colunas_clean.get(cat_clean)
            if col_target:
                colunas[col_target].append(os)
            else:
                colunas["EM ABERTO"].append(os)
    return colunas

if tarefas_filtradas:
    kanban = get_kanban_data(tarefas_filtradas)

    # ── Filtro por ID (só para o Kanban) ──
    col_s, _ = st.columns([2, 6])
    with col_s:
        kanban_search = st.text_input("Buscar", placeholder="ID, Local ou Descrição", label_visibility="collapsed")
    if kanban_search:
        termo = kanban_search.strip().lower()
        for col_nome in list(kanban.keys()):
            kanban[col_nome] = [os for os in kanban[col_nome] 
                                if termo in str(os.get("ID", "")).lower()
                                or termo in str(os.get("Titulo", "")).lower()
                                or termo in str(os.get("Local do servico", "")).lower()
                                or termo in str(os.get("Descricao detalhada", "")).lower()]
        kanban = {k: v for k, v in kanban.items() if v}

    def _sort_kanban_items(items):
        """Ordena: atrasadas primeiro, depois por Entrega desejada (mais antiga primeiro)"""
        def _key(os):
            atras = 0 if _is_overdue(os) else 1
            dt = str(os.get("Entrega desejada", "")).strip()[:10]
            return (atras, dt or "9999-12-31")
        return sorted(items, key=_key)

    # Container com scroll horizontal
    st.markdown('<div class="kanban-scroll">', unsafe_allow_html=True)

    # Cabeçalho das colunas (com contador)
    kcols = st.columns(len(kanban))
    for i, (nome_coluna, items) in enumerate(kanban.items()):
        total = len(items)
        with kcols[i]:
            st.markdown(f"""<div class="kanban-title">{nome_coluna} <span class="badge-count">{total}</span></div>""",
                        unsafe_allow_html=True)

    # Cards (ordenados por atraso)
    for col_idx, (nome_coluna, items) in enumerate(kanban.items()):
        with kcols[col_idx]:
            st.markdown(f"""<div class="kanban-column">""", unsafe_allow_html=True)
            if not items:
                st.caption("Nenhuma O.S.")
            sorted_items = _sort_kanban_items(items)
            for os_item in sorted_items[:10]:
                render_os_card(os_item)
            if len(sorted_items) > 10:
                restantes = sorted_items[10:]
                with st.expander(f"📦 +{len(restantes)} O.S.", expanded=False):
                    for os_item in restantes:
                        render_os_card(os_item)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

st.divider()


# ── SEÇÃO 7: DETALHES COM EXPANDER ────────────────────────

if tarefas_filtradas:
    st.caption("⚡ Portal de Gestão Contratual UFAC — Vivace Engenharia")
st.caption(f"Dados carregados da planilha Google Sheets \u2022 Atualizado em {agora_ac().strftime('%d/%m/%Y \u00e0s %H:%M')}")
st.caption("Desenvolvido por Marco Aurélio (COO Digital)")
