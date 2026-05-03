"""
dashboard.py — Portal de Gestão Contratual UFAC (Vivace Engenharia)
Estratégia Híbrida: CSV (bulk) + Runrun.it API (pontual)
Foco: Ferramenta operacional de decisão com Kanban visual
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os, re, json
import pytz
import base64
from urllib.parse import urlencode

# Fuso Brasília (UTC-3)
BRASILIA_TZ = pytz.timezone("America/Sao_Paulo")


def agora_br() -> datetime:
    """Retorna datetime atual em Brasília"""
    return datetime.now(BRASILIA_TZ)

from api_client import (
    buscar_todas_tarefas_ufac, CONTRATOS,
    API_BASE, HEADERS
)
from chat_repository import get_messages, add_message as add_chat_message
from transformer import (
    calcular_sla_os, formatar_moeda, categorizar_status_kanban,
    extrair_valor_total, extrair_valor_mo, extrair_valor_ma
)

# ── Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Gestão Contratual UFAC",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Constantes ──────────────────────────────────────────────
GUEST_HASH = "2388c490fbf8e2"

# ── Botão header (cinza escuro, SEM vermelho) ──
st.markdown("""
<style>
/* Reset genérico — não conflita com primary/secondary */
div.stButton > button {
 border-radius: 8px;
 padding: 6px 20px;
 font-size: 0.875rem;
 white-space: nowrap !important;
 width: auto;
 transition: background-color 0.15s, border-color 0.15s;
}
</style>
""", unsafe_allow_html=True)

# ── Estilos customizados ────────────────────────────────────
st.markdown("""
<style>
    /* ── TIPOGRAFIA (Lei 6) ── */
    .main-title { font-size: 1.75rem; font-weight: 800; color: #f9fafb; margin-bottom: 0; }
    .section-title { font-size: 1.125rem; font-weight: 700; color: #e5e7eb; margin: 24px 0 12px 0; }
    .kpi-label { font-size: 0.75rem; font-weight: 500; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.75rem; font-weight: 800; color: #f9fafb; }
    .card-text { font-size: 0.875rem; font-weight: 400; color: #d1d5db; }
    .meta-text { font-size: 0.75rem; font-weight: 400; color: #6b7280; }

    /* ── CARD PADRÃO (Lei 6) ── */
    .card-base {
        background: #1f2937;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.4);
    }

    /* ── CORES SEMÂNTICAS (Lei 1) ── */
    .txt-verde { color: #22c55e; }
    .txt-amarelo { color: #f59e0b; }
    .txt-vermelho { color: #ef4444; }
    .txt-azul { color: #3b82f6; }
    .txt-cinza { color: #9ca3af; }

    /* ── CONTRATOS: ativo (primary) vs inativo (secondary) ── */
    div[data-testid="stButton"]:has(button[kind="primary"]) button {
        background: #166534 !important;
        border: 1.5px solid #22c55e !important;
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    div[data-testid="stButton"]:has(button[kind="secondary"]) button {
        background: #1e293b !important;
        border: 1.5px solid #334155 !important;
        color: #94a3b8 !important;
        font-weight: 500 !important;
    }
    .bg-verde { background: #22c55e; }
    .bg-amarelo { background: #f59e0b; }
    .bg-vermelho { background: #ef4444; }
    .bg-azul { background: #3b82f6; }
    .bg-cinza { background: #374151; }

    /* ── BADGES (Lei 1 - semântica estrita) ── */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        margin-right: 4px;
        font-weight: 500;
    }
    .badge-verde { background: #14532d; color: #22c55e; }
    .badge-amarelo { background: #422006; color: #f59e0b; }
    .badge-vermelho { background: #450a0a; color: #ef4444; }
    .badge-azul { background: #1e3a5f; color: #3b82f6; }
    .badge-cinza { background: #374151; color: #9ca3af; }

    /* ── KANBAN (Lei 3 - borda esquerda SLA) ── */
    .kanban-scroll {
        overflow-x: auto !important;
        overflow-y: hidden;
        padding-bottom: 12px;
        scroll-behavior: smooth;
        width: 100%;
    }
    .kanban-scroll::-webkit-scrollbar { height: 8px; }
    .kanban-scroll::-webkit-scrollbar-thumb { background: #3b82f6; border-radius: 4px; }
    .kanban-scroll::-webkit-scrollbar-track { background: #1f2937; border-radius: 4px; }
    .kanban-scroll .row-widget.stHorizontal { flex-wrap: nowrap !important; overflow-x: visible !important; }
    .kanban-scroll .row-widget.stHorizontal > div {
        min-width: 270px !important;
        flex-shrink: 0 !important;
    }
    .kanban-column {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 8px;
        overflow-y: auto;
        max-height: 65vh;
    }
    .kanban-column::-webkit-scrollbar { width: 6px; }
    .kanban-column::-webkit-scrollbar-thumb { background: #3b82f6; border-radius: 3px; }
    .kanban-column::-webkit-scrollbar-track { background: #1f2937; border-radius: 3px; }
    .kanban-title {
        font-weight: 700;
        font-size: 0.75rem;
        padding: 8px;
        border-bottom: 2px solid #374151;
        margin-bottom: 8px;
        text-align: center;
        position: sticky;
        top: 0;
        background: #1f2937;
        z-index: 1;
        color: #e5e7eb;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }

    /* ── KANBAN CARD (Lei 3 — borda esquerda 4px) ── */
    .kanban-card {
        background: #1f2937;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 8px;
        font-size: 0.875rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.3);
        position: relative;
        border-left: 4px solid #374151;
    }
    .kanban-card.overdue { border-left-color: #ef4444; }
    .kanban-card.warning { border-left-color: #f59e0b; }
    .kanban-card.ontime { border-left-color: #22c55e; }
    .kanban-card.progress { border-left-color: #3b82f6; }
    .kanban-card.nodate { border-left-color: #374151; }
    .kanban-card.estado-atrasadas { border-left-color: #ef4444; }

    /* ── CARDS UNIFORMES (altura/tamanho padronizado) ── */
    div[data-testid="metric-container"] {
        min-height: 110px !important;
        padding: 1rem 1rem 0.75rem !important;
        background: #1a1d2e !important;
        border: 1px solid #2d3148 !important;
        border-radius: 8px !important;
    }
    div.stAlert {
        background: #1a1d2e !important;
        border: 1px solid #2d3148 !important;
        border-radius: 8px !important;
        padding: 1rem 1rem 0.75rem !important;
    }
    div:has(> div.stLinkButton):has(+ div.element-container) {
        background: #1a1d2e;
        border: 1px solid #2d3148;
        border-radius: 8px;
        padding: 0.75rem 1rem;
    }
    .kanban-card.estado-concluidas { border-left-color: #22c55e; }
    .kanban-card.estado-encerradas { border-left-color: #22c55e; }
    .kanban-card .card-id {
        color: #3b82f6;
        font-weight: 700;
        font-size: 0.875rem;
    }
    .kanban-card .card-title {
        color: #d1d5db;
        font-size: 0.8125rem;
        margin: 2px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .kanban-card .card-meta {
        color: #6b7280;
        font-size: 0.75rem;
    }
    .kanban-card .card-valor {
        color: #22c55e;
        font-weight: 600;
        font-size: 0.8125rem;
    }

    /* ── KPI METRIC (Lei 8) ── */
    div[data-testid="stMetric"] {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 16px;
    }
    div[data-testid="stMetric"] > div > div:first-child {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: #9ca3af !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stMetric"] > div > div:nth-child(2) {
        font-size: 1.75rem !important;
        font-weight: 800 !important;
        color: #f9fafb !important;
    }

    /* ── SIDEBAR COUNTER BADGE (Lei 7) ── */
    .filter-badge {
        display: inline-block;
        background: #374151;
        border: 1px solid #4b5563;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        color: #d1d5db;
        margin-right: 4px;
    }

    /* ── PENDÊNCIA CARDS ── */
    .pend-card {
        border-radius: 6px; padding: 8px 10px; margin-bottom: 4px;
        font-size: 12px;
    }
    .vivace-card { background: #1a2e1a; border-left: 3px solid #22c55e; }
    .ufac-card { background: #2e1a1a; border-left: 3px solid #ef4444; }
    .counter-bar {
        text-align: center; padding: 6px; border-radius: 6px;
        font-size: 12px; font-weight: 600; margin: 4px 0;
    }
    .vivace-bar { background: #1a2e1a; color: #22c55e; border: 1px solid #2a4a2a; }
    .ufac-bar { background: #2e1a1a; color: #ef4444; border: 1px solid #4a2a2a; }

    /* ── PENDÊNCIA EXPANDER LINKS ── */
    .plink-row { margin-bottom:3px; }
    .plink-a {
        display:inline-flex;align-items:center;gap:4px;
        background:#1f2937;border:1px solid #374151;
        border-radius:4px;padding:3px 8px;
        color:#22c55e;font-size:11px;text-decoration:none;
        width:100%;
    }
    .pinfo-row {
        display:flex;justify-content:space-between;
        padding:2px 0;border-bottom:1px solid #1f2937;
        font-size:11px;
    }
    .pinfo-label { color:#6b7280; }
    .pinfo-value { color:#d1d5db; font-weight:500; }

    /* ── SALDO CONTAINER (Lei 2 - topo) ── */
    .saldo-card {
        background: #0f172a;
        border: 1px solid #22c55e;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .saldo-card.saude { border-color: #22c55e; }
    .saldo-card.atencao { border-color: #f59e0b; }
    .saldo-card.critico { border-color: #ef4444; }
</style>
""", unsafe_allow_html=True)

# ── State ───────────────────────────────────────────────────
# Força recarga se trocou a URL do CSV (evita dados antigos do session state)
if "tarefas" not in st.session_state or st.button("🔄 Recarregar", key="reload_btn"):
    st.session_state.tarefas = buscar_todas_tarefas_ufac()
    if "contratos_set" in st.session_state:
        del st.session_state.contratos_set
    if "contrato_filtro" in st.session_state:
        del st.session_state.contrato_filtro

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
        hoje = agora_br().date()
        return dt < hoje
    except ValueError:
        return False

def _sla_class(os: dict) -> str:
    """Lei 3: Retorna classe CSS da borda SLA (4px) baseada na urgência do prazo"""
    estado = str(os.get("Estado", "")).strip().upper()
    if estado in ("CONCLUÍDAS", "ENCERRADAS", "CONCLUÍDA", "FECHADA"):
        return "estado-concluidas"
    if estado == "ATRASADAS" or _is_overdue(os):
        return "estado-atrasadas"
    dt_str = str(os.get("Entrega desejada", "")).strip()[:10]
    if not dt_str or dt_str in ("", "-", "N/A"):
        return "nodate"
    try:
        hoje = agora_br().date()
        dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        dias = (dt - hoje).days
        if dias < 0:
            return "estado-atrasadas"
        elif dias <= 3:
            return "warning"
        elif dias <= 14:
            return "ontime"
        else:
            return "progress"
    except ValueError:
        return "nodate"

def _sla_label(os: dict) -> str:
    """Lei 3: Texto SLA com dias restantes"""
    estado = str(os.get("Estado", "")).strip().upper()
    if estado in ("CONCLUÍDAS", "ENCERRADAS", "CONCLUÍDA", "FECHADA"):
        return "✅ Concluída"
    if _is_overdue(os):
        dt_str = str(os.get("Entrega desejada", "")).strip()[:10]
        if dt_str and len(dt_str) == 10:
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
                hoje = agora_br().date()
                diff = (hoje - dt).days
                return f"🔴 ATRASADA — {diff}d"
            except:
                pass
        return "🔴 ATRASADA"
    dt_str = str(os.get("Entrega desejada", "")).strip()[:10]
    if not dt_str or dt_str in ("", "-", "N/A"):
        return "⚫ Prazo não definido"
    try:
        hoje = agora_br().date()
        dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        dias = (dt - hoje).days
        if dias <= 3:
            return f"🟡 {dias}d restantes"
        elif dias <= 14:
            return f"🟢 {dias}d restantes"
        else:
            return f"🔵 {dias}d restantes"
    except ValueError:
        return "⚫ Prazo não definido"

def kpi_card(label, valor, delta=None, cor_delta="green"):
    """Card KPI padronizado — label visível em dark/light mode"""
    delta_html = ""
    if delta:
        cor = "#22c55e" if cor_delta == "green" else "#ef4444"
        delta_html = f'<p style="font-size:0.75rem; color:{cor}; margin:4px 0 0 0;">{delta}</p>'
    st.markdown(f"""
    <div style="background:#1e293b; border-radius:10px; 
                padding:16px; border:1px solid #334155;">
      <p style="font-size:0.7rem; font-weight:600; 
                color:#94a3b8; text-transform:uppercase; 
                letter-spacing:0.05em; margin:0 0 6px 0;">
        {label}
      </p>
      <p style="font-size:1.6rem; font-weight:800; 
                color:#f1f5f9; margin:0;">
        {valor}
      </p>
      {delta_html}
    </div>
    """, unsafe_allow_html=True)


def kpi_critico(label, valor, subtexto=""):
    """Card KPI para dados críticos — borda vermelha esquerda"""
    st.markdown(f"""
    <div style="background:#1e293b; border-radius:10px; 
                padding:16px; border-left:4px solid #ef4444;
                border-top:1px solid #334155;
                border-right:1px solid #334155;
                border-bottom:1px solid #334155;">
      <p style="font-size:0.7rem; font-weight:600; 
                color:#fca5a5; text-transform:uppercase; 
                letter-spacing:0.05em; margin:0 0 6px 0;">
        🔴 {label}
      </p>
      <p style="font-size:2rem; font-weight:800; 
                color:#ef4444; margin:0;">
        {valor}
      </p>
      <p style="font-size:0.75rem; color:#6b7280; margin:4px 0 0 0;">
        {subtexto}
      </p>
    </div>
    """, unsafe_allow_html=True)


def kpi_critico_conformidade(contrato, quantidade):
    """Card Conformidade com subtexto orientado à ação (Correção 3)"""
    if quantidade == 0:
        cor = "#22c55e"
        icone = "✅"
        subtexto = "Todas as OS em conformidade"
    elif quantidade <= 5:
        cor = "#f59e0b"
        icone = "⚠️"
        subtexto = f"Revisar {quantidade} OS com o fiscal"
    else:
        cor = "#ef4444"
        icone = "🔴"
        subtexto = f"Ação urgente: {quantidade} OS fora do padrão"

    st.markdown(f"""
    <div style="background:#1e293b; border-radius:10px;
                padding:16px; border-left:4px solid {cor};
                border:1px solid #334155;">
      <p style="font-size:0.7rem; font-weight:600; 
                color:#94a3b8; text-transform:uppercase; 
                margin:0 0 4px 0;">
        {icone} Falhando Conformidade — {contrato}
      </p>
      <p style="font-size:2rem; font-weight:800; 
                color:{cor}; margin:0 0 4px 0;">
        {quantidade}
      </p>
      <p style="font-size:0.75rem; color:#6b7280; margin:0;">
        {subtexto}
      </p>
    </div>
    """, unsafe_allow_html=True)


def _data_prevista_dias(os: dict):
    """Retorna (cor_hex, texto_sla) para o card Kanban"""
    estado = str(os.get("Estado", "")).strip().upper()
    if estado in ("CONCLUÍDAS", "ENCERRADAS", "CONCLUÍDA", "FECHADA"):
        return "#22c55e", "✅ Concluída"
    dt_str = str(os.get("Entrega desejada", "")).strip()[:10]
    if not dt_str or dt_str in ("", "-", "N/A"):
        return "#475569", "⬜ Sem prazo"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d").date()
        dias = (dt - agora_br().date()).days
        if dias < 0:
            return "#ef4444", f"🔴 {abs(dias)}d atrasada"
        elif dias <= 3:
            return "#f59e0b", f"🟡 {dias}d restantes"
        else:
            return "#22c55e", f"🟢 {dias}d restantes"
    except ValueError:
        return "#475569", "⬜ Sem prazo"


def render_os_card(os: dict):
    """Card Kanban ultra-compacto — 3 linhas, SLA visual (Correção 1)"""
    os_id = os.get("ID", "")
    contrato = str(os.get("Contrato", ""))[:15]
    local = str(os.get("Local do servico", ""))[:50]
    local_curto = (local[:28] + "…") if len(local) > 28 else local
    cor_borda, texto_sla = _data_prevista_dias(os)

    st.markdown(f"""
    <div style="background:#1e293b; border-radius:8px;
                border-left:4px solid {cor_borda};
                border-top:1px solid #334155;
                border-right:1px solid #334155;
                border-bottom:1px solid #334155;
                padding:8px 10px; margin-bottom:6px; cursor:pointer;"
         onclick="document.querySelector('[data-testid=\"stExpander\"]').click()">
      <p style="font-size:0.7rem; font-weight:700; color:#94a3b8;
                margin:0 0 2px 0; line-height:1.2;">
        #{os_id} · {contrato}
      </p>
      <p style="font-size:0.8rem; color:#e2e8f0; margin:0 0 5px 0; line-height:1.3;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
        {local_curto}
      </p>
      <span style="font-size:0.68rem; color:{cor_borda}; font-weight:600; letter-spacing:0.02em;">
        {texto_sla}
      </span>
    </div>
    """, unsafe_allow_html=True)

    # Expander (collapsed por padrão) com detalhes completos
    with st.expander(f"#{os_id} — {local_curto}", expanded=False, key=f"exp_{os_id}"):
        titulo = str(os.get("Titulo", ""))[:80]
        valor = extrair_valor_total(os)
        responsavel = str(os.get("Fiscal responsavel", ""))[:25]
        data_entrega = str(os.get("Entrega desejada", "")).strip()[:10]
        guest_url = f"https://{GUEST_HASH}-share.runrun.it/pt-BR/guest/tasks/{os_id}"
        val_fmt = formatar_moeda(valor) if valor else ""

        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;">
            <span style="font-size:0.9rem; font-weight:700; color:#f1f5f9;">{titulo or '—'}</span>
            <span style="font-size:0.85rem; font-weight:700; color:#22c55e;">{val_fmt}</span>
        </div>
        <div style="color:#94a3b8; font-size:0.75rem; margin:4px 0;">
            📅 {data_entrega or '—'} · 👤 {responsavel or '—'}
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── Links documentos ──
        docs_found = False
        for lbl, url_key, ico in [
            ("Relat. Situacional", "Link do relatorio situacional", "📋"),
            ("Relat. Final", "Link do relatorio final", "✅"),
            ("Orç. Prévio", "Link do orcamento previo", "💰"),
            ("Orç. Final", "Link do orcamento final", "📊"),
        ]:
            url = str(os.get(url_key, "")).strip()
            if url and url not in ("", "-", "#N/A"):
                if not docs_found:
                    st.markdown("**📎 Documentos**")
                    docs_found = True
                st.markdown(f"[{ico} {lbl}]({url})")

        # ── Info grid ──
        info_items = [
            ("📋 Etapa", os.get("Etapa", "") or "—"),
            ("🏢 Local", local or "—"),
            ("👤 Fiscal", responsavel or "—"),
        ]
        for k, v in [
            ("👤 Solicitante", str(os.get("Solicitante", ""))[:20]),
            ("🏢 Setor", str(os.get("Setor responsavel", ""))[:20]),
            ("📍 Abrangência", str(os.get("Abrangencia", ""))[:15]),
            ("💳 Despesa", str(os.get("Tipo de despesa", ""))[:15]),
            ("📝 Parecer", str(os.get("Parecer/complemento", ""))[:30]),
            ("🔐 Permissões", str(os.get("Permissoes de sistema", ""))[:20]),
            ("📊 Omie", str(os.get("Lancado no Omie?", ""))[:5]),
            ("✅ Proc.Concluído", str(os.get("Processo concluido?", ""))[:5]),
        ]:
            if v and v.upper() not in ("", "—", "NÃO", "NAO", "NAN", "NONE"):
                info_items.append((k, v))

        for lbl, val in info_items:
            st.markdown(f"{lbl}: **{val}**")

        st.link_button("🔗 Abrir no Runrun.it (guest)", guest_url, use_container_width=True)


# ── SIDEBAR — Filtros ──────────────────────────────────────

# Logo com fundo claro fixo (visível em qualquer tema)
with open("logo_vivace.png", "rb") as f:
    b64_logo = base64.b64encode(f.read()).decode()
st.sidebar.markdown(f"""
<div style="padding:4px;text-align:center;">
    <img src="data:image/png;base64,{b64_logo}" style="max-width:100%;height:auto;display:block;margin:0 auto;">
</div>
""", unsafe_allow_html=True)
st.sidebar.markdown("## ⚡ Painel UFAC")

with st.sidebar:
    # Botão de atualização — cinza escuro, SEM primary (sem vermelho)
    total = len(st.session_state.tarefas)
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;">
        <span style="color:#9ca3af;font-size:0.75rem;">{total} registros • {agora_br().strftime('%d/%m/%Y às %H:%M')}</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔄 Atualizar", use_container_width=False, type="secondary"):
        st.session_state.tarefas = buscar_todas_tarefas_ufac()
        st.rerun()

    st.divider()
    st.markdown("### 🔍 Filtros de consulta")

    # Contrato — toggle multi-seleção (selecionar 1, 2 ou nenhum)
    df = pd.DataFrame(st.session_state.tarefas)
    contratos_disponiveis = sorted([x for x in df["Contrato"].dropna().unique().tolist() if x.strip()]) if not df.empty else ["60/2024"]
    # Migração: session state antigo 'contrato_filtro' (single-select) → 'contratos_set' (multi-select)
    if "contrato_filtro" in st.session_state and "contratos_set" not in st.session_state:
        st.session_state.contratos_set = {st.session_state.contrato_filtro}
        del st.session_state.contrato_filtro
    if "contratos_set" not in st.session_state:
        st.session_state.contratos_set = set(contratos_disponiveis)
    if not st.session_state.contratos_set:
        st.session_state.contratos_set = set(contratos_disponiveis)

    cols_ct_btn = st.columns(len(contratos_disponiveis))
    for i, ct in enumerate(contratos_disponiveis):
        with cols_ct_btn[i]:
            ativo = ct in st.session_state.contratos_set
            tipo = "primary" if ativo else "secondary"
            if st.button(ct, type=tipo, key=f"btn_ct_{ct}", use_container_width=True):
                if ct in st.session_state.contratos_set:
                    st.session_state.contratos_set.discard(ct)
                else:
                    st.session_state.contratos_set.add(ct)
                if not st.session_state.contratos_set:
                    st.session_state.contratos_set = set(contratos_disponiveis)
                st.rerun()

    contratos_selecionados = list(st.session_state.contratos_set)

    # Status
    status_disponiveis = ["TODOS", "EM ABERTO", "EM ORÇAMENTO", "PARA EXECUÇÃO",
                          "EM EXECUÇÃO", "FISCALIZAÇÃO", "CONCLUÍDA", "FECHADA", "CANCELADA"]
    status_selecionado = st.selectbox("Situação", status_disponiveis, key="filtro_status")

    # Fiscal
    fiscais = sorted([x for x in df["Fiscal responsavel"].dropna().unique().tolist() if x.strip()]) if not df.empty else []
    fiscal_selecionado = st.selectbox("Fiscal", ["TODOS"] + fiscais, key="filtro_fiscal")

    # Local
    locais = sorted([x for x in df["Local do servico"].dropna().unique().tolist() if x.strip()]) if not df.empty else []
    local_selecionado = st.selectbox("Local do serviço", ["TODOS"] + locais, key="filtro_local")

    # Período (pela data de abertura/criação)
    st.markdown("**📅 Período (Data de abertura)**")
    periodo_opts = ["Último mês", "Últimos 3 meses", "Últimos 6 meses", "Últimos 12 meses", "Personalizado"]
    periodo_sel = st.radio("Período (abertura)", periodo_opts, index=2, key="filtro_periodo",
                           label_visibility="collapsed", horizontal=True)

    hoje = agora_br().date()
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

    st.divider()
    st.markdown(f"**📊 Registros:** {len(st.session_state.tarefas)} O.S. UFAC")
    st.caption(f"Última atualização: {agora_br().strftime('%d/%m/%Y às %H:%M')}")


# ── Aplicar filtros ─────────────────────────────────────────

def aplicar_filtros(tarefas: list, contratos, status, local, dt_ini, dt_fim, fiscal=None) -> list:
    filtradas = []
    for os in tarefas:
        # Filtro fiscal
        if fiscal and fiscal != "TODOS":
            f = str(os.get("Fiscal responsavel", "")).strip()
            if f != fiscal:
                continue
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
        if local != "TODOS":
            loc = str(os.get("Local do servico", os.get("custom_187", ""))).strip()
            if loc != local:
                continue
        # Período (pela data de criação, não entrega)
        if dt_ini is not None and dt_fim is not None:
            try:
                criada = str(os.get("Criada em", "")).strip()[:10]
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
    fiscal=fiscal_selecionado
)

# ── Main content (usa TODOS os filtros, incluindo período) ─
tarefas_filtradas = aplicar_filtros(
    st.session_state.tarefas,
    contratos_selecionados,
    status_selecionado,
    local_selecionado,
    data_ini, data_fim,
    fiscal=fiscal_selecionado
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
    fig.add_trace(go.Bar(name='Mão de Obra (MO)', x=compet, y=mos,
                         marker_color='#4a90d9', hovertemplate='MO: R$ %{y:,.2f}<extra></extra>'))
    fig.add_trace(go.Bar(name='Material (MA)', x=compet, y=mas,
                         marker_color='#7ecb7e', hovertemplate='MA: R$ %{y:,.2f}<extra></extra>'))
    fig.add_trace(go.Bar(name='Valor Total', x=compet, y=totais,
                         marker_color='#e6a817', opacity=0.5,
                         hovertemplate='Total: R$ %{y:,.2f}<extra></extra>'))

    fig.update_layout(
        barmode='group',
        template='plotly_dark',
        height=350,
        margin=dict(l=40, r=20, t=30, b=40),
        legend=dict(orientation='h', y=1.12, x=0.5, xanchor='center'),
        yaxis=dict(tickprefix='R$ ', tickformat=',.0f'),
        hovermode='x unified'
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



# ── SEÇÃO 2: TOPO — Z-PATTERN (Lei 2) ─────────────────────

contratos_ativos = contratos_selecionados if contratos_selecionados else list(CONTRATOS.keys())
_st = sum(
    CONTRATOS.get(ct, {}).get('orcamento_aditivo', CONTRATOS.get(ct, {}).get('orcamento', 0))
    for ct in contratos_ativos
)
_usado = fin_geral['total_geral']
_sr = _st - _usado
_pt = (_usado / _st * 100) if _st else 0

# Badge de filtros ativos (Lei 7)
filtro_badges = []
if contratos_selecionados:
    filtro_badges.append(f"📍 {', '.join(contratos_selecionados)}")
if status_selecionado != 'TODOS':
    filtro_badges.append(f"🔍 {status_selecionado}")
if fiscal_selecionado != 'TODOS':
    filtro_badges.append(f"👤 {fiscal_selecionado}")
if periodo_sel != 'Personalizado':
    filtro_badges.append(f"⏱ {periodo_sel}")

# Saldo bicolor: saudável ou crítico
_cls_saldo = "saude"
if _pt > 75:
    _cls_saldo = "atencao"
elif _pt > 90:
    _cls_saldo = "critico"
_saldo_border = {"saude": "#22c55e", "atencao": "#f59e0b", "critico": "#ef4444"}[_cls_saldo]

hcol1, hcol2 = st.columns([2, 1])
with hcol1:
    st.markdown(f"""
    <div style="display:flex; flex-direction:column; gap:2px;">
        <span style="font-size:1.4rem; font-weight:800; color: var(--text-color, #f9fafb);">
            ⚡ Gestão Contratual UFAC
        </span>
        <span style="font-size:0.8rem; color:#9ca3af;">
            Portal Operacional — Vivace Engenharia
        </span>
    </div>
    """, unsafe_allow_html=True)
    # Badges de filtro ativos (Lei 7)
    if filtro_badges:
        st.markdown('<div style="margin:6px 0;">' + ' '.join(f'<span class="filter-badge">{b}</span>' for b in filtro_badges) + '</div>', unsafe_allow_html=True)

with hcol2:
    # Saldo do Contrato — POSIÇÃO 1 (topo esquerda = lado direito do header)
    # Cor da borda segue saúde financeira
    _pct_class = "txt-verde" if _cls_saldo == "saude" else ("txt-amarelo" if _cls_saldo == "atencao" else "txt-vermelho")
    _badge_saude = '<span class="badge badge-verde">✅ Saudável</span>' if _cls_saldo == "saude" else (
        '<span class="badge badge-amarelo">⚠️ Atenção</span>' if _cls_saldo == "atencao" else '<span class="badge badge-vermelho">🔴 Crítico</span>')
    
    st.markdown(f'''
    <div class="saldo-card {_cls_saldo}" style="border-color:{_saldo_border};">
        <div class="kpi-label">🏦 Saldo do Contrato {_badge_saude}</div>
        <div class="kpi-value">R$ {_sr:,.2f}</div>
        <div class="card-text" style="color:#9ca3af;font-size:0.8125rem;margin:4px 0;">
            {_pt:.1f}% utilizado · R$ {_st:,.0f} orçamento
        </div>
        <div class="meta-text">
            📅 {fin_geral['competencias'][0]} a {fin_geral['competencias'][-1]}
        </div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown("<hr style='border-color:#374151;margin:16px 0;'>", unsafe_allow_html=True)

# Mapeamento de etapas para cada coluna
VIVACE_ETAPAS = ["PARA LEVANTAMENTO", "PARA EXECUÇÃO", "ATRASADAS", "CONFORMIDADE DEMANDANTE"]
UFAC_ETAPAS = ["CONFORMIDADE EM ANÁLISE DA FISCALIZAÇÃO", "ORÇAMENTO EM ANÁLISE DA FISCALIZAÇÃO",
               "APROVADOS AGUARDANDO LIBERAÇÃO FISCALIZAÇÃO", "PENDÊNCIAS"]

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

st.markdown("### 🚨 Alertas e Pendências Operacionais")

# Botão portal guest acima das duas colunas (mantém alinhamento)
portal_url = f"https://{GUEST_HASH}-share.runrun.it/pt-BR/guest/tasks"
st.link_button("👁️ Ver O.S. no RUNRUN.it", portal_url, use_container_width=True,
                help="Abre o portal de tarefas compartilhadas — o fiscal da UFAC acessa sem precisar de login.")

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

    with st.expander(f"#{os_id} — {titulo[:40]}...", expanded=False, key=f"pend_{os_id}"):
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
            ("Relat. Situacional", link_sit, "📋")
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
            st.caption("📎 Nenhum documento anexado")

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
        st.caption("⚠️ Link para o fiscal da UFAC — abre sem login.")


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
    st.success("🎯 Todas as O.S. estão em dia — nenhuma pendência crítica.")

st.divider()


# ── SEÇÃO 3: FORMULÁRIO DE ABERTURA DE O.S. ───────────────

st.markdown("### ➕ Abertura de Nova O.S.")
form_url = "https://runrun.it/share/form/oJUZ2dYeVZhxikEK"
st.link_button("📋 Abrir solicitação", form_url, use_container_width=True,
                help="Abre o formulário público do Runrun.it para criar uma nova O.S. — o fiscal da UFAC preenche e a O.S. é gerada automaticamente.")


# ── SEÇÃO 4: DADOS FINANCEIROS ─────────────────────────────

with st.container():
    st.markdown("### 💰 Painel Financeiro — Medições por Competência")
    st.caption(f"📅 Período de fechamento: **{fin['competencias'][0]} a {fin['competencias'][-1]}** — últimos 12 meses")

    # Multi-select de competências (pode selecionar mais de uma)
    competencias_opcoes = fin['competencias']  # TODAS é implícito (desmarcar = todas)
    compet_selecionadas = st.multiselect(
        "🔎 Filtrar por competência de fechamento",
        competencias_opcoes,
        default=[],
        key="filtro_competencia",
        placeholder="Todas"
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
            help=f"Valor total acumulado{' em ' + ', '.join(compet_selecionadas) if not usar_todas else ''}"
        )
    with col_f2:
        st.metric(
            "🔧 Mão de Obra",
            f"R$ {mo_exibir:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            help=f"Total Mão de Obra (MO){' em ' + ', '.join(compet_selecionadas) if not usar_todas else ' acumulado'}"
        )
    with col_f3:
        st.metric(
            "📦 Material",
            f"R$ {ma_exibir:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            help=f"Total Material (MA){' em ' + ', '.join(compet_selecionadas) if not usar_todas else ' acumulado'}"
        )
    with col_f4:
        st.metric(
            "📊 Valor Médio Medido / Competência",
            f"R$ {valor_medio:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            delta=f"{qtd_exibir} O.S. em {len(compet_selecionadas)} competências",
            help=f"Média do valor total dividido pela quantidade de competências selecionadas — respeita os filtros de contrato, fiscal e local"
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
        fig.add_trace(go.Bar(name='Mão de Obra (MO)', x=compet, y=mos,
                             marker_color='#4a90d9',
                             hovertemplate='MO: R$ %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Bar(name='Material (MA)', x=compet, y=mas,
                             marker_color='#7ecb7e',
                             hovertemplate='MA: R$ %{y:,.2f}<extra></extra>'))
        fig.add_trace(go.Scatter(name='Valor Total', x=compet, y=totais,
                                 mode='lines+markers',
                                 line=dict(color='#ffd700', width=2.5),
                                 marker=dict(size=8, symbol='diamond'),
                                 hovertemplate='Total: R$ %{y:,.2f}<extra></extra>'))
        fig.add_hline(y=media_med, line_dash='dot',
                      line_color='#94a3b8', line_width=1,
                      annotation_text=f'Média: R$ {media_med:,.0f}',
                      annotation_position='top right',
                      annotation_font=dict(size=11, color='#94a3b8'))
        fig.update_layout(
            barmode='stack',
            template='plotly_dark',
            height=350,
            margin=dict(l=40, r=20, t=30, b=40),
            legend=dict(orientation='h', y=1.12),
            yaxis=dict(tickprefix='R$ ', tickformat=',.0f'),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True, key="grafico_comp_detalhe")

st.divider()



# ── SEÇÃO 5: INDICADORES GERAIS E POR CONTRATO ────────────

with st.container():
    st.markdown("### 📊 Indicadores Gerais por Contrato")
    st.caption("Filtros globais: Contrato · Situação · Fiscal · Local do serviço · Período (data de abertura)")

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

        # ── Render cards topo (5 colunas) — kpi_card() ──
        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            kpi_card("Fila de Execução Operacional", f"{fila_op_count}")
        with c2:
            kpi_card("Demandas Emergenciais Ativas", f"{emerg_count}",
                     delta="⚠ Requer atenção", cor_delta="red")
        with c3:
            kpi_card("OS Atrasadas", f"{atras_count}",
                     delta="⚠ Verificar", cor_delta="red")
        with c4:
            kpi_card("Total de OS", f"{total_os}")
        with c5:
            taxa_str = f"{taxa_conclusao:.1f}%".replace('.', ',')
            kpi_card("Taxa de Conclusão", taxa_str,
                     delta=f"{concluidas_count}/{total_os} concluídas", cor_delta="green")

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
                val_fmt = formatar_moeda(valor_med) if qtd_med else "R$ 0,00"
                kpi_card(f"📌 {ct} — O.S. em Fechamento", val_fmt,
                         delta=f"{qtd_med} O.S.", cor_delta="green")
                # Card Faltando Conformidade — CRÍTICO (borda vermelha)
                kpi_critico_conformidade(ct, qtd_conf)
    else:
        st.info("Nenhuma O.S. encontrada — ajuste os filtros.")

st.divider()


# ── SEÇÃO 6: KANBAN OPERACIONAL ────────────────────────────

st.markdown("### 📌 Kanban — Fluxo Operacional")

# Colunas Kanban (ordenadas por fluxo operacional)
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

def get_kanban_data(tarefas):
    """Separa tarefas por coluna Kanban (8 colunas, mesmo fluxo do Runrun.it)"""
    colunas = {col: [] for col in KANBAN_COLUNAS}
    for os in tarefas:
        cat = categorizar_status_kanban(os)
        if cat in colunas:
            colunas[cat].append(os)
        else:
            colunas["📥 Em Aberto"].append(os)
    return colunas

if tarefas_filtradas:
    kanban = get_kanban_data(tarefas_filtradas)

    # ── Filtro no Kanban: busca em ID, Local e Descrição ──
    col_s, _ = st.columns([2, 6])
    with col_s:
        kanban_search = st.text_input("🔍 Buscar", placeholder="ID, Local ou descrição", label_visibility="collapsed")
    if kanban_search:
        termo = kanban_search.strip().lower()
        for col_nome in list(kanban.keys()):
            kanban[col_nome] = [
                os for os in kanban[col_nome]
                if termo in str(os.get("ID", "")).lower()
                or termo in str(os.get("Local do servico", os.get("custom_187", ""))).lower()
                or termo in str(os.get("Titulo", "")).lower()
                or termo in str(os.get("Descricao detalhada da solicitacao", os.get("custom_264", ""))).lower()
            ]
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

    # Mapa de cores por estágio do Kanban (Correção 4)
    COR_KANBAN = {
        "📥 EM ABERTO": "#64748b",
        "🔍 ORÇAMENTO": "#3b82f6",
        "🔧 PARA EXECUÇÃO": "#8b5cf6",
        "🔴 ATRASADAS": "#ef4444",
        "🔍 APROVAÇÃO": "#f59e0b",
        "📄 CONFORMIDADE": "#f59e0b",
        "💰 FECHAMENTO": "#22c55e",
        "✅ CONCLUÍDAS": "#16a34a",
    }

    # Cabeçalho das colunas com badge de contagem
    kcols = st.columns(len(kanban))
    for i, (nome_coluna, items) in enumerate(kanban.items()):
        total = len(items)
        cor_badge = COR_KANBAN.get(nome_coluna, "#64748b")
        label_clean = nome_coluna.split(" ", 1)[1] if " " in nome_coluna else nome_coluna
        with kcols[i]:
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px;
                        padding:6px 0 10px 0;
                        border-bottom:2px solid {cor_badge};
                        margin-bottom:8px;">
              <span style="font-size:0.75rem; font-weight:700;
                           color:#e2e8f0; text-transform:uppercase;
                           letter-spacing:0.06em;">
                {label_clean}
              </span>
              <span style="background:{cor_badge}22;
                           color:{cor_badge};
                           border:1px solid {cor_badge}44;
                           border-radius:12px; padding:1px 8px;
                           font-size:0.7rem; font-weight:700;">
                {total}
              </span>
            </div>
            """, unsafe_allow_html=True)

    # Cards (ordenados por atraso)
    for col_idx, (nome_coluna, items) in enumerate(kanban.items()):
        with kcols[col_idx]:
            st.markdown(f"""<div class="kanban-column">""", unsafe_allow_html=True)
            if not items:
                st.caption("Nenhuma O.S. encontrada")
            sorted_items = _sort_kanban_items(items)
            for os_item in sorted_items[:10]:
                render_os_card(os_item)
            if len(sorted_items) > 10:
                restantes = sorted_items[10:]
                with st.expander(f"📦 +{len(restantes)} O.S.", expanded=False, key=f"rest_{col_idx}"):
                    for os_item in restantes:
                        render_os_card(os_item)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# Seção 7 removida: Kanban já mostra tudo em cards com expander


# ── FOOTER ──────────────────────────────────────────────────

st.divider()
st.caption("⚡ Portal de Gestão Contratual UFAC | Vivace Engenharia Ltda.")
st.caption(f"Dados carregados da planilha Google Sheets • Atualizado em {agora_br().strftime('%d/%m/%Y às %H:%M')}")
st.caption("Desenvolvido por Marco Aurélio — COO Digital")
