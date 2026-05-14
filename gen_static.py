"""
gen_static.py — Gera dashboard HTML estático + JSON de dados
Roda sob demanda ou via cron. Saída: /var/www/ufac/
"""
import json, os, sys
from datetime import datetime

from api_client import buscar_todas_tarefas_ufac, parse_tarefa
from transformer import calcular_kpis, inferir_status_execucao, gerar_resumo_tarefa, extrair_mes_medicao

OUTDIR = "/var/www/ufac"
os.makedirs(OUTDIR, exist_ok=True)


def gerar_dados_json():
    raw = buscar_todas_tarefas_ufac()
    tarefas = [parse_tarefa(t) for t in raw]
    kpis = calcular_kpis(tarefas)
    resumos = [gerar_resumo_tarefa(t) for t in tarefas]
    return {"kpis": kpis, "tarefas": resumos, "gerado_em": datetime.now().isoformat()}


def gerar_html(data: dict):
    k = data["kpis"]
    tarefas = data["tarefas"]

    # Templates de cards
    tarefas_html = ""
    for t in tarefas:
        sla_icon = {"Atrasado": "🔴", "Próximo do vencimento": "🟡"}.get(t["sla"], "🟢")
        status_icon = {"Executado": "✅", "Em Andamento": "🔄"}.get(t["status_execucao"], "⏳")
        atrasado_cls = 'class="atrasado"' if t["sla"] == "Atrasado" else ""

        tarefas_html += f"""
        <details {atrasado_cls}>
            <summary>{status_icon} <b>O.S. #{t["id"]}</b> — {t["titulo_curto"]}</summary>
            <div class="os-detail">
                <div class="os-grid">
                    <span><b>Contrato:</b> {t["contrato"]}</span>
                    <span><b>Status:</b> {t["status_execucao"]}</span>
                    <span><b>SLA:</b> {sla_icon} {t["sla"]}</span>
                    <span><b>Local:</b> {t["local"] or "—"}</span>
                    <span><b>Mão de Obra:</b> R$ {t["valor_mao_obra"]:,.2f}</span>
                    <span><b>Material:</b> R$ {t["valor_material"]:,.2f}</span>
                    <span><b>Total:</b> R$ {t["valor_total"]:,.2f}</span>
                    {f'<span><b>Medição:</b> {t["mes_medicao"]}</span>' if t["mes_medicao"] else ""}
                </div>
            </div>
        </details>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gestão Contratual UFAC</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f0f1a; color: #e0e0f0; padding: 20px; }}
h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; color: #00d4aa; }}
.sub {{ color: #8888aa; margin-bottom: 2rem; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 2rem; }}
.kpi-card {{ background: #1a1a2e; border-radius: 12px; padding: 1.2rem; border: 1px solid #2a2a4e; text-align: center; }}
.kpi-value {{ font-size: 1.8rem; font-weight: 700; color: #00d4aa; }}
.kpi-label {{ font-size: 0.8rem; color: #8888aa; margin-top: 0.3rem; }}
.charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 2rem; }}
.chart-box {{ background: #1a1a2e; border-radius: 12px; padding: 1rem; border: 1px solid #2a2a4e; }}
.chart-box h3 {{ margin-bottom: 0.8rem; font-size: 0.95rem; color: #aaaacc; }}
.contrato-row {{ background: #1a1a2e; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem; border: 1px solid #2a2a4e; }}
.contrato-row h3 {{ color: #00d4aa; }}
.contrato-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 0.5rem; }}
.contrato-grid span {{ font-size: 0.9rem; }}
details {{ background: #1a1a2e; border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 6px; border: 1px solid #2a2a4e; cursor: pointer; }}
details.atrasado {{ border-left: 4px solid #ff4b4b; }}
summary {{ cursor: pointer; font-size: 0.9rem; }}
.os-detail {{ margin-top: 0.8rem; }}
.os-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 6px; font-size: 0.85rem; }}
.os-grid span {{ padding: 4px 0; }}
.footer {{ margin-top: 2rem; font-size: 0.75rem; color: #555; text-align: center; }}
.med-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(120px,1fr)); gap: 6px; margin-top: 0.5rem; }}
.med-item {{ background: #2a2a4e; border-radius: 6px; padding: 6px; text-align: center; font-size: 0.85rem; }}
@media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} .contrato-grid {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<h1>⚡ Gestão Contratual UFAC</h1>
<p class="sub">Contratos 60/2024 (Rio Branco) • 61/2024 (Cruzeiro do Sul) — Atualizado: {data['gerado_em']}</p>

<div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-value">R$ {k['saldo_contratual']:,.2f}</div><div class="kpi-label">Saldo Contratual</div></div>
    <div class="kpi-card"><div class="kpi-value">R$ {k['total_executado']:,.2f}</div><div class="kpi-label">Total Executado</div></div>
    <div class="kpi-card"><div class="kpi-value">{k['pct_utilizado']:.1f}%</div><div class="kpi-label">% Orçamento Utilizado</div></div>
    <div class="kpi-card"><div class="kpi-value">{k['os_concluidas']}</div><div class="kpi-label">O.S. Concluídas</div></div>
    <div class="kpi-card"><div class="kpi-value">{k['os_abertas']}</div><div class="kpi-label">O.S. Abertas</div></div>
</div>

<div class="charts">
    <div class="chart-box">
        <h3>💰 Executado vs Orçado</h3>
        <canvas id="chartOrcado"></canvas>
    </div>
    <div class="chart-box">
        <h3>📈 Evolução das Medições</h3>
        <canvas id="chartMedicoes"></canvas>
    </div>
</div>

<h2>📋 Saldo por Contrato</h2>
"""

    for cod, info in k["saldos"].items():
        html += f"""
<div class="contrato-row">
    <h3>{cod} — {info["local"]}</h3>
    <div class="contrato-grid">
        <span><b>Orçamento:</b> R$ {info["orcamento"]:,.2f}</span>
        <span><b>Executado:</b> R$ {info["executado"]:,.2f}</span>
        <span><b>Saldo:</b> R$ {info["saldo"]:,.2f}</span>
        <span><b>O.S.:</b> {info["qtd_executadas"]}/{info["qtd_total"]}</span>
    </div>
</div>"""

    html += """
<h2 style="margin-top: 2rem;">📋 Ordens de Serviço</h2>
""" + tarefas_html

    # Status distribution
    status_ct = {"Executado": 0, "Em Andamento": 0, "Aguardando": 0}
    for t in tarefas:
        s = t["status_execucao"]
        if s in status_ct:
            status_ct[s] += 1

    html += """
<h2 style="margin-top: 2rem;">📊 Distribuição por Status</h2>
<div class="chart-box">
    <canvas id="chartStatus" height="200"></canvas>
</div>

<script>
const chartOrcado = new Chart(document.getElementById('chartOrcado'), {
    type: 'bar',
    data: {"""
    labels = json.dumps(list(k["saldos"].keys()))
    orc = [s["orcamento"] for s in k["saldos"].values()]
    exec_vals = [s["executado"] for s in k["saldos"].values()]
    html += f"""
        labels: {labels},
        datasets: [
            {{ label: 'Orçamento', data: {json.dumps(orc)}, backgroundColor: '#2a2a5e' }},
            {{ label: 'Executado', data: {json.dumps(exec_vals)}, backgroundColor: '#00d4aa' }}
        ]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#aaa' }} }} }},
        scales: {{ y: {{ ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }} }}
}});

new Chart(document.getElementById('chartStatus'), {{
    type: 'doughnut',
    data: {{
        labels: {json.dumps(list(status_ct.keys()))},
        datasets: [{{ data: {json.dumps(list(status_ct.values()))},
            backgroundColor: ['#00d4aa', '#ffa500', '#4a90d9'] }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#aaa' }} }} }} }}
}});
"""

    # Medições chart
    medicoes = k.get("medicoes", [])
    if medicoes:
        meses = [m["mes"] for m in medicoes]
        vals = [m["valor"] for m in medicoes]
        html += f"""
new Chart(document.getElementById('chartMedicoes'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(meses)},
        datasets: [{{ label: 'Valor Medido', data: {json.dumps(vals)}, backgroundColor: '#00d4aa' }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#aaa' }} }} }},
        scales: {{ y: {{ ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }} }}
}});
"""
    else:
        html += """
new Chart(document.getElementById('chartMedicoes'), {
    type: 'bar', data: { labels: [], datasets: [] },
    options: { plugins: { legend: { display: false } } }
});
"""

    html += "</script>"
    html += '<div class="footer">⚡ Sistema de Gestão Contratual UFAC — Vivace Engenharia | Dados do Runrun.it</div>'
    html += "</body></html>"

    return html


if __name__ == "__main__":
    print("🔄 Gerando dados...")
    data = gerar_dados_json()
    print(f"✅ {len(data['tarefas'])} tarefas carregadas")
    print("🔄 Gerando HTML...")
    html = gerar_html(data)
    with open(os.path.join(OUTDIR, "index.html"), "w") as f:
        f.write(html)
    with open(os.path.join(OUTDIR, "dados.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ HTML salvo em {OUTDIR}/index.html")
    print(f"✅ JSON salvo em {OUTDIR}/dados.json")
    k = data["kpis"]
    print(f"📊 KPIs: R$ {k['total_executado']:,.2f} executado | {k['pct_utilizado']:.1f}% | {k['os_abertas']} abertas / {k['os_concluidas']} concluídas")
