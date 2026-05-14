# 🏛️ Portal de Gestão Contratual UFAC — Vivace Engenharia

Dashboard interativo para gestão de contratos da UFAC (Universidade Federal do Acre), integrado com Runrun.it e Google Sheets.

## 📋 Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| **Kanban de O.S.** | 6 etapas do fluxo: Vencendo Hoje, Em Curso, Atrasadas, Pendentes, Concluídas, Bloqueadas |
| **Indicadores financeiros** | Total contratado, valor liquidado, medido, a medir por contrato |
| **Alertas e Pendências** | Destaques automáticos de O.S. com SLA vencido ou próximas do vencimento |
| **Filtros** | Por contrato, número de processo, período de abertura |
| **Chat interno** | Banco SQLite de notas/comentários vinculados ao dashboard |
| **Planilha de medição** | Importação de CSV de medição UFAC |
| **Dark/Light mode** | Alternável no header |

## 🏗️ Arquitetura

```
ufac-dashboard/
├── dashboard.py          # Frontend Streamlit (1305 linhas)
├── transformer.py        # Lógica de negócio (SLA, formatação, categorias Kanban)
├── api_client.py         # Integração com API Runrun.it
├── models.py             # Modelos de dados (dataclasses)
├── chat_repository.py    # Chat interno SQLite
├── run.py                # Entrypoint de execução
├── gen_static.py         # Gerador de CSV estático
├── seed.py               # Sementes de dados para teste
├── seed_concluidas.json  # Dados de tasks concluídas
├── requirements.txt      # Dependências Python
├── planilha_dados.csv    # Cache CSV de tarefas
├── planilha_medicao.csv  # Dados de medição
├── chat_ufac.db          # Banco SQLite do chat
├── scripts/
│   ├── consolidado_v153.js  # Google Apps Script — coleta tasks do Runrun.it
│   └── sync_v7.2.js        # Google Apps Script — webhook de sincronização
└── README.md             # Este arquivo
```

## 🚀 Deploy

### Pré-requisitos
- Python 3.10+
- Streamlit
- Acesso à API Runrun.it (App-key + User-token)

### Instalação

```bash
pip install -r requirements.txt

# Configurar credenciais Runrun.it (via variáveis de ambiente ou config)
export RUNRUNIT_APP_KEY="seu_app_key"
export RUNRUNIT_USER_TOKEN="seu_user_token"

# Executar
streamlit run dashboard.py
```

### Dependências (`requirements.txt`)
```
streamlit>=1.28
plotly>=5.15
pandas>=2.0
requests>=2.31
```

## 🔗 Integrações

### Runrun.it (MCP + API REST)
- **MCP**: Busca de tarefas UFAC via ferramenta `ufac_ordens_servico` (retorna 300+ tasks)
- **API REST v1.0**: Consultas complementares via `/api/v1.0/tasks/{id}` com header `App-key`
- **Google Apps Script**: Script `consolidado_v153.js` roda no Google Sheets para consolidar dados mensalmente

### Google Sheets
- Planilha "Status Report Geral — Runrun.it" como fonte de backup
- Webhook `sync_v7.2.js` para sincronização de deleções

## ⚙️ Manutenção

### Atualizar cache CSV
```bash
# Gerar planilha_dados.csv atualizada
python gen_static.py
```

### Recriar índices Kanban
```python
# Em transformer.py — categorizar_status_kanban() define as 6 colunas
MAPA_ETAPA_KANBAN = {
    "Vencendo Hoje": azul,
    "Em Curso": verde,
    "Atrasadas": vermelho,
    "Pendentes": laranja,
    "Concluídas": cinza,
    "Bloqueadas": preto,
}
```

## 🧠 Observações Técnicas

- Fuso horário: **America/Rio_Branco (UTC-5)**
- O dashboard usa **cache CSV** como fonte principal e Runrun.it como fallback em tempo real
- SLA calculado a partir de `custom_17` (prazo em dias) + data de abertura
- Total contratual: R$ 34.282.008,35 (Contrato 60/2024 UFAC)
- Valor liquidado via `custom_135`, medido via `custom_134`, a medir via `custom_139`

---

**Desenvolvido por:** Marco Aurélio (COO Digital) para Vivace Engenharia
**Stack:** Python + Streamlit + Plotly + Runrun.it API
