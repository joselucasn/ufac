/**
 * Runrun.it → Google Sheets (Status Report Geral)
 * v7.2 - Estrategia: Timestamp Diff (bypass do updated_after quebrado)
 *
 * CORRECOES v7.2:
 *   - API_BASE corrigido: https://secure.runrun.it (estava api.runrun.it - 401)
 *   - updated_after REMOVIDO: API ignora o parametro (confirmado via teste)
 *   - Incremental via diff de timestamps: salva updated_at por task,
 *     percorre todas as tasks paginadas mas so escreve na planilha as que mudaram
 *   - SAFETY_MAX_ITEMS_PER_PAGE removido (ja que todas as tasks sao lidas)
 *   - Cache de timestamps em PropertiesService (RR_TIMESTAMPS)
 *   - Processa em lotes de 1000 para nao estourar memoria do GAS
 *   - Full load preservado (funciona igual)
 */

/* ====================== PARAMETROS ====================== */
var API_BASE     = 'https://secure.runrun.it';
var API_VERSION  = '/api/v1.0';
var SHEET_NAME   = 'Status Report Geral';

var EXECUTION_LIMIT_MS = 5 * 60 * 1000;  // 5 min
var SAFETY_MS          = 60 * 1000;       // 1 min de margem
var MAX_ROWS_PER_FLUSH = 500;
var PAGE_LIMIT         = 1000;

var STATE_KEY        = 'RR_STATE_v72';
var RESUME_HANDLER   = 'atualizarRunRunIt_Resume_v72';
var WATCHDOG_HANDLER = 'watchdogRunRunIt_v72_';
var TIMESTAMPS_KEY   = 'RR_TIMESTAMPS';  // JSON: { taskId: "YYYY-MM-DD HH:MM:SS", ... }

/* ====================== CUSTOM FIELDS ====================== */
var CUSTOM_IDS = [
  "custom_137","custom_144","custom_168","custom_194","custom_59","custom_78","custom_127","custom_245","custom_266",
  "custom_10","custom_11","custom_15","custom_17","custom_19","custom_21",
  "custom_23","custom_24","custom_25","custom_30","custom_32","custom_56",
  "custom_130","custom_170","custom_183","custom_184",
  "custom_223","custom_230","custom_231",
  "custom_264","custom_286",
  "custom_31","custom_52","custom_55","custom_58","custom_141","custom_142",
  "custom_143","custom_145","custom_275","custom_277","custom_278",
  "custom_63","custom_64","custom_108","custom_147","custom_267",
  "custom_94","custom_95","custom_96","custom_112","custom_113",
  "custom_114","custom_115","custom_116","custom_246","custom_247",
  "custom_248","custom_249","custom_255","custom_256",
  "custom_73","custom_80","custom_81","custom_82","custom_83",
  "custom_109","custom_250","custom_251","custom_252","custom_253",
  "custom_165","custom_166",
  "custom_239","custom_240","custom_268","custom_269","custom_270",
  "custom_271","custom_272",
  "custom_120","custom_121","custom_129","custom_138","custom_139",
  "custom_151","custom_152","custom_160","custom_161","custom_163",
  "custom_164","custom_167","custom_169","custom_173","custom_174",
  "custom_180","custom_181","custom_187","custom_188","custom_192",
  "custom_193","custom_195","custom_196","custom_198","custom_199",
  "custom_200","custom_241","custom_254","custom_273","custom_280",
  "custom_281","custom_283",
  "custom_66","custom_76","custom_227","custom_229","custom_233"
];

var CUSTOM_NAME_MAP = {
  "custom_10":"Tipo de acionamento","custom_11":"Valor total","custom_15":"Prefixo",
  "custom_17":"Nome da agencia","custom_19":"Ordem de Servico","custom_21":"Chamado",
  "custom_23":"Matricula/nome do responsavel pelo acionamento","custom_24":"Endereco da agencia",
  "custom_25":"Contato do responsavel pelo acionamento","custom_30":"Localidade",
  "custom_32":"Equipe de fechamento","custom_56":"Regiao","custom_130":"Sinistro",
  "custom_170":"Cooparticipacao do terceirizado","custom_183":"Valor M.O","custom_184":"Valor M.A",
  "custom_223":"Contratante","custom_230":"Empresa","custom_231":"Contrato",
  "custom_264":"Descricao detalhada da solicitacao","custom_286":"Descricao previa",
  "custom_31":"Competencia","custom_52":"Fornecedor","custom_55":"Meio de pagamento",
  "custom_58":"Categoria","custom_141":"Forma de pagamento","custom_142":"Quantidade de parcelas",
  "custom_143":"Valor da parcela","custom_145":"Meio de restituicao","custom_275":"Conta de pagamento",
  "custom_277":"Data de pagamento","custom_278":"Data de vencimento",
  "custom_63":"Nota Fiscal","custom_64":"Comprovante de pagamento","custom_108":"CRLV",
  "custom_147":"Fotos","custom_267":"Anexos",
  "custom_94":"Marca","custom_95":"Modelo","custom_96":"Ano",
  "custom_112":"Quilometragem atual","custom_113":"Placas - AC","custom_114":"Placas - PB",
  "custom_115":"Placas - RN","custom_116":"Placas - RO","custom_246":"Origem da solicitacao",
  "custom_247":"Tipo de servico veicular","custom_248":"Descricao do servico",
  "custom_249":"Categoria de manutencao","custom_255":"Observacoes do veiculo",
  "custom_256":"Autorizado?",
  "custom_73":"Vagas","custom_80":"Colaboradores - AC","custom_81":"Colaboradores - PB",
  "custom_82":"Colaboradores - RO","custom_83":"Colaboradores - RN","custom_109":"Filiacao",
  "custom_250":"CPF ou CNPJ","custom_251":"Chave PIX / documento","custom_252":"Tipo de chave",
  "custom_253":"Nome do favorecido","custom_165":"Cargo","custom_166":"EPI's",
  "custom_239":"Material","custom_240":"Previsao de chegada do material","custom_268":"Quantidade",
  "custom_269":"Motorista","custom_270":"Validade CNH","custom_271":"Km atual",
  "custom_272":"Situacao da entrega",
  "custom_120":"Setor","custom_121":"Tipo de solicitacao","custom_129":"Tipo do atendimento",
  "custom_138":"Numero do processo","custom_139":"Fiscal responsavel","custom_151":"Cliente",
  "custom_152":"Tipo de proposta","custom_160":"Uso designado","custom_161":"Motivo da solicitacao",
  "custom_163":"Especificacao do equipamento","custom_164":"Equipamentos","custom_167":"Estado de uso",
  "custom_169":"Estorno/cancelamento","custom_173":"Patrimonio","custom_174":"Especificacao do patrimonio",
  "custom_180":"Valor da entrada","custom_181":"Emissao de nota fiscal?","custom_187":"Local do servico",
  "custom_188":"Unidade solicitante","custom_192":"Proposta elaborada?","custom_193":"Categoria da tarefa",
  "custom_195":"Cadastrado na planilha de controle (UFAC)?","custom_196":"Tipo de compra",
  "custom_198":"Link do relatorio situacional","custom_199":"Link do relatorio final",
  "custom_200":"Link do orcamento previo","custom_241":"Link do orcamento final",
  "custom_254":"Permissoes de sistema","custom_273":"Parecer/complemento","custom_280":"Setor responsavel",
  "custom_281":"Solicitante","custom_283":"Tipo de despesa",
  "custom_59":"Vencimento","custom_78":"Solicitada documentacao?","custom_127":"Contador",
  "custom_137":"Necessario analise da diretoria?","custom_144":"Nome do prestador",
  "custom_168":"Fardamentos","custom_194":"Solicitacao de pagamento","custom_245":"Tipo de feedback",
  "custom_266":"N de referencia","custom_66":"Lancado no Omie?","custom_76":"Processo concluido?",
  "custom_227":"Abrangencia","custom_229":"Departamento","custom_233":"Lancado no Conta Simples?"
};

var DOCUMENT_FIELDS = new Set(["custom_63","custom_64","custom_108","custom_147","custom_267"]);
var NUMERIC_CUSTOMS = new Set(["custom_11","custom_143","custom_180","custom_183","custom_184"]);

var BASE_HEADERS = [
  'nPagina','nTotPaginas','nRegistros','nTotRegistros',
  'Quadro','Cliente','Grupo','Projeto','ID da tarefa principal',
  'Tarefa principal','Tipo','Equipes','Centro de custo','Alocados',
  'ID','Titulo','Urgente','Prioridade','Criada por','Criada em',
  'Entrega desejada','Entrega estimada','Data de entrega','Esforco estimado (h)',
  'Primeiro esforco estimado (h)','Horas trabalhadas (h)','Ja registradas em subtarefas (h)','Progresso',
  'Etapa','Estado','Reaberta?','Tags','Codigo customizado de cliente','Horas restantes (h)'
];

/* ====================== MENU E CREDENCIAIS ====================== */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Runrun.it')
    .addItem('Configurar Credenciais', 'configurarCredenciaisRR')
    .addSeparator()
    .addItem('Atualizar (Apenas Modificadas - Rapido)', 'atualizarIncrementalRR')
    .addItem('Atualizar Tudo (Completo - Lento)', 'atualizarCompletoRR')
    .addToUi();
}

function configurarCredenciaisRR() {
  var ui = SpreadsheetApp.getUi();
  var appToken = ui.prompt('Credenciais Seguras', 'Insira o APP-TOKEN do Runrun.it:', ui.ButtonSet.OK_CANCEL);
  if (appToken.getSelectedButton() !== ui.Button.OK) return;

  var userToken = ui.prompt('Credenciais Seguras', 'Insira o USER-TOKEN do Runrun.it:', ui.ButtonSet.OK_CANCEL);
  if (userToken.getSelectedButton() !== ui.Button.OK) return;

  PropertiesService.getScriptProperties().setProperties({
    'RR_APP_TOKEN': appToken.getResponseText().trim(),
    'RR_USER_TOKEN': userToken.getResponseText().trim()
  });
  ui.alert('Credenciais salvas!');
}

function getCredentials_() {
  var props = PropertiesService.getScriptProperties();
  return { KEY: props.getProperty('RR_APP_TOKEN'), TOKEN: props.getProperty('RR_USER_TOKEN') };
}

/* ====================== CONTROLE DE SINCRONIZACAO ====================== */
function atualizarIncrementalRR() {
  startSync_(true);
}

function atualizarCompletoRR() {
  // Limpa cache de timestamps para forcar full refresh
  PropertiesService.getScriptProperties().deleteProperty(TIMESTAMPS_KEY);
  startSync_(false);
}

function startSync_(isIncremental) {
  withScriptLockRR(function() {
    resetStateRR_();
    var now = new Date();
    now.setMinutes(now.getMinutes() - 5);

    saveStateRR_({
      initialized: false,
      nextUrl: buildTasksUrl_(1),
      page: 1,
      totalItems: null,
      totalPages: null,
      nextWriteRow: 2,
      isIncremental: isIncremental,
      itemsProcessedThisRun: 0,
      apiCallsThisMinute: 0,
      rateLimitReset: Date.now() + 60000
    });

    _resumeCoreRR_();
  });
}

function atualizarRunRunIt_Resume_v72() {
  withScriptLockRR(function() {
    var st = loadStateRR_();
    if (!st || !st.nextUrl) { finalizeRR_(); return; }
    _resumeCoreRR_();
  });
}

function formatDateRR_(date) {
  var pad = function(n) { return String(n).padStart(2, '0'); };
  return date.getFullYear() + '-' +
         pad(date.getMonth() + 1) + '-' +
         pad(date.getDate()) + ' ' +
         pad(date.getHours()) + ':' +
         pad(date.getMinutes()) + ':' +
         pad(date.getSeconds());
}

function ensureTargetSheet_(isIncremental) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
  } else if (!isIncremental) {
    sh.clear({ contentsOnly: false });
    try { sh.getFilter() && sh.getFilter().remove(); } catch (_) {}
    try { sh.clearNotes(); } catch (_) {}
  }
  return sh;
}

/* ====================== NUCLEO DE EXECUCAO ====================== */
function _resumeCoreRR_() {
  var creds = getCredentials_();
  if (!creds.KEY || !creds.TOKEN) throw new Error('Credenciais nao encontradas. Use o menu primeiro.');

  var started = Date.now();
  var state = loadStateRR_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);

  if (!state.initialized) {
    sheet = ensureTargetSheet_(state.isIncremental);
    if (state.isIncremental && sheet.getLastRow() === 0) {
      state.isIncremental = false;
      state.nextUrl = buildTasksUrl_(1);
    }

    if (!state.isIncremental || sheet.getLastRow() === 0) {
      var customHeaders = CUSTOM_IDS.map(function(id) { return CUSTOM_NAME_MAP[id] || id; });
      var header = BASE_HEADERS.concat(customHeaders);
      sheet.getRange(1, 1, 1, header.length).setValues([header]);
      try { sheet.setFrozenRows(1); } catch (_) {}

      var baseCols = BASE_HEADERS.length;
      CUSTOM_IDS.forEach(function(id, idx) {
        if (NUMERIC_CUSTOMS.has(id)) {
          try { sheet.getRange(2, baseCols + idx + 1, sheet.getMaxRows()-1, 1).setNumberFormat('#,##0.00'); } catch (_) {}
        }
      });
    }
    state.initialized = true;
    state.nextWriteRow = state.isIncremental ? sheet.getLastRow() + 1 : 2;
    saveStateRR_(state);
  }

  // Carrega cache de timestamps (para diff incremental)
  var timestampsCache = {};
  if (state.isIncremental) {
    try {
      var raw = PropertiesService.getScriptProperties().getProperty(TIMESTAMPS_KEY);
      if (raw) { timestampsCache = JSON.parse(raw); }
    } catch(_) {}
  }

  var nextUrl = state.nextUrl;
  var page = state.page;
  var totalItems = state.totalItems;
  var totalPages = state.totalPages;
  var nextWriteRow = state.nextWriteRow;
  var isIncremental = state.isIncremental;
  var itemsProcessedThisRun = state.itemsProcessedThisRun || 0;
  var apiCallsThisMinute = state.apiCallsThisMinute || 0;
  var rateLimitReset = state.rateLimitReset || (Date.now() + 60000);

  var rowsBuffer = [];
  var updates = [];        // { row: N, data: [...] }
  var hasNewRows = false;   // se alguma task nova apareceu (precisa append)

  try {
    while (true) {
      if (Date.now() - started > (EXECUTION_LIMIT_MS - SAFETY_MS)) {
        saveStateRR_({
          initialized: true, nextUrl: nextUrl, page: page,
          totalItems: totalItems, totalPages: totalPages,
          nextWriteRow: nextWriteRow, isIncremental: isIncremental,
          itemsProcessedThisRun: itemsProcessedThisRun + rowsBuffer.length,
          apiCallsThisMinute: apiCallsThisMinute, rateLimitReset: rateLimitReset
        });
        // Salva timestamps atualizados
        PropertiesService.getScriptProperties().setProperty(TIMESTAMPS_KEY, JSON.stringify(timestampsCache));
        scheduleResumeRR_(30);
        return;
      }

      if (!nextUrl) break;

      // Rate limit: max 55 chamadas/minuto
      if (apiCallsThisMinute >= 55) {
        var wait = Math.max(rateLimitReset - Date.now(), 1000);
        if (wait > 0) {
          saveStateRR_({
            initialized: true, nextUrl: nextUrl, page: page,
            totalItems: totalItems, totalPages: totalPages,
            nextWriteRow: nextWriteRow, isIncremental: isIncremental,
            itemsProcessedThisRun: itemsProcessedThisRun + rowsBuffer.length,
            apiCallsThisMinute: 0, rateLimitReset: Date.now() + 60000
          });
          PropertiesService.getScriptProperties().setProperty(TIMESTAMPS_KEY, JSON.stringify(timestampsCache));
          scheduleResumeRR_(Math.ceil(wait / 1000) + 5);
          return;
        }
        apiCallsThisMinute = 0;
        rateLimitReset = Date.now() + 60000;
      }

      var lote = fetchRunrunPage_(nextUrl, creds);
      apiCallsThisMinute++;

      var items = lote.items;
      var meta = lote.meta;
      var next = lote.nextUrl;

      if (meta && meta.total != null) {
        totalItems = meta.total;
        totalPages = Math.ceil(totalItems / PAGE_LIMIT);
        page = meta.start ? Math.floor((Math.max(1, meta.start) - 1) / PAGE_LIMIT) + 1 : page;
      }

      if (!Array.isArray(items) || items.length === 0) {
        nextUrl = next;
        if (!nextUrl) break;
        continue;
      }

      var pageMetaCols = [ page || '', totalPages || '', items.length || 0, totalItems || '' ];

      for (var i = 0; i < items.length; i++) {
        var task = items[i];
        var taskId = String(task.id);
        var base = mapTaskBase_(task);
        var custom = mapTaskCustom_(task);
        var rowData = pageMetaCols.concat(base, custom);

        // Timestamp da task (created_at como fallback se nao tiver updated_at)
        var taskUpdatedAt = task.updated_at || task.created_at || '';

        if (isIncremental) {
          // Verifica se ja existe na planilha
          var existingRow = findTaskRow_(sheet, taskId);

          if (existingRow) {
            // Verifica se mudou pelo timestamp
            var cachedTs = timestampsCache[taskId] || '';
            if (cachedTs !== taskUpdatedAt) {
              updates.push({ row: existingRow, data: rowData });
              timestampsCache[taskId] = taskUpdatedAt;
            }
            // Se nao mudou, apenas ignora
          } else {
            // Task nova: adiciona ao buffer
            rowsBuffer.push(rowData);
            timestampsCache[taskId] = taskUpdatedAt;
            hasNewRows = true;
          }
        } else {
          // Full load: adiciona tudo ao buffer
          rowsBuffer.push(rowData);
          // Salva timestamp
          if (taskUpdatedAt) {
            timestampsCache[taskId] = taskUpdatedAt;
          }
        }

        // Flush do buffer a cada X linhas
        if (!isIncremental && rowsBuffer.length >= MAX_ROWS_PER_FLUSH) {
          flushRows_(sheet, rowsBuffer, nextWriteRow);
          nextWriteRow += rowsBuffer.length;
          rowsBuffer.length = 0;
        }
      }

      nextUrl = next;
    }

    // Aplica updates incrementais na planilha (se houver)
    if (isIncremental && updates.length > 0) {
      applyUpdates_(sheet, updates);
    }

    // Append linhas novas se houver
    if (rowsBuffer.length > 0) {
      flushRows_(sheet, rowsBuffer, nextWriteRow);
    } else if (isIncremental && updates.length === 0 && !hasNewRows) {
      // Nada mudou
    }

    // Salva cache de timestamps
    if (isIncremental) {
      PropertiesService.getScriptProperties().setProperty(TIMESTAMPS_KEY, JSON.stringify(timestampsCache));
    }

    finalizeRR_();

    var mode = isIncremental ? 'Incremental (Timestamp Diff)' : 'Completa';
    var totalProcessed = itemsProcessedThisRun + rowsBuffer.length + updates.length;
    var now = new Date();

    PropertiesService.getScriptProperties().setProperty('RR_LAST_SYNC_v72', formatDateRR_(now));
    SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME)
      .getRange(2, 1).setNote('Atualizacao ' + mode + ' em ' + now.toLocaleString() +
        ' | Processados: ' + totalProcessed +
        ' | Atualizadas: ' + updates.length +
        ' | Novas: ' + rowsBuffer.length);

  } catch (e) {
    saveStateRR_({
      initialized: true, nextUrl: nextUrl, page: page,
      totalItems: totalItems, totalPages: totalPages,
      nextWriteRow: nextWriteRow, isIncremental: isIncremental,
      itemsProcessedThisRun: itemsProcessedThisRun + rowsBuffer.length,
      apiCallsThisMinute: apiCallsThisMinute, rateLimitReset: rateLimitReset
    });
    PropertiesService.getScriptProperties().setProperty(TIMESTAMPS_KEY, JSON.stringify(timestampsCache));
    scheduleResumeRR_(60);
    throw e;
  }
}

/* ====================== LOCALIZACAO DE LINHA POR ID ====================== */
function findTaskRow_(sheet, taskId) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;

  // Coluna O (15) = ID
  var idCol = sheet.getRange(2, 15, lastRow - 1, 1).getValues();
  for (var i = 0; i < idCol.length; i++) {
    var val = String(idCol[i][0]).trim();
    if (val === taskId) return i + 2;
  }
  return null;
}

/* ====================== ATUALIZACAO EM MASSA ====================== */
function applyUpdates_(sheet, updateList) {
  if (updateList.length === 0) return;

  var totalRows = sheet.getLastRow();
  var totalCols = sheet.getLastColumn();
  var fullData = sheet.getRange(1, 1, totalRows, totalCols).getValues();

  for (var i = 0; i < updateList.length; i++) {
    var u = updateList[i];
    for (var c = 0; c < u.data.length; c++) {
      fullData[u.row - 1][c] = u.data[c];
    }
  }

  // Escreve tudo de volta (inclui header)
  sheet.getRange(1, 1, totalRows, totalCols).setValues(fullData);
}

/* ====================== MAPS ====================== */
function mapTaskBase_(task) {
  var assignees = (task.assignments || []).map(function(a) { return a.assignee_name; }).filter(Boolean).join(', ');
  var tags = (task.tags || []).join(', ');
  return [
    task.board_name || '', task.client_name || '', task.project_group_name || '', task.project_name || '',
    task.parent_task_id || '', task.parent_task_title || '', task.type_name || '', task.team_name || '',
    task.cost_center || '', assignees, task.id || '', task.title || '', task.is_urgent ? 'Sim' : 'Nao',
    task.priority || '', task.user_name || '', task.created_at || '', task.desired_date || '',
    task.estimated_delivery_date || '', task.close_date || '',
    task.current_estimate_seconds ? task.current_estimate_seconds/3600 : '',
    task.first_estimate || '', task.time_worked ? task.time_worked/3600 : '',
    task.all_subtasks_time_total ? task.all_subtasks_time_total/3600 : '',
    task.time_progress || '', task.task_state_name || '', task.board_stage_name || '',
    task.was_reopened ? 'Sim' : 'Nao',
    tags, task.client_custom_code || '', task.time_pending ? task.time_pending/3600 : ''
  ];
}

function toNumberSafe_(val) {
  if (val === null || val === undefined) return '';
  if (typeof val === 'number' && Number.isFinite(val)) return val;
  var s = String(val).trim().replace(/\u00A0/g, ' ').replace(/\s+/g, '').replace(/[^0-9,.\-]/g, '');
  if (!s) return '';
  var lastComma = s.lastIndexOf(','), lastDot = s.lastIndexOf('.');
  if (lastComma !== -1 && lastDot !== -1) {
    s = (lastComma > lastDot) ? s.replace(/\./g, '').replace(/,/g, '.') : s.replace(/,/g, '');
  } else if (lastComma !== -1) { s = s.replace(/\./g, '').replace(/,/g, '.'); }
  else { var parts = s.split('.'); if (parts.length > 2) { var dec = parts.pop(); s = parts.join('') + '.' + dec; } }
  var n = Number(s); return Number.isFinite(n) ? n : '';
}

function mapTaskCustom_(task) {
  var cf = task.custom_fields || {};
  var arr = [];
  for (var j = 0; j < CUSTOM_IDS.length; j++) {
    var id = CUSTOM_IDS[j];
    var v = cf[id];
    var pushNormalized = function(val) {
      if (NUMERIC_CUSTOMS.has(id)) arr.push(toNumberSafe_(val));
      else arr.push(String(val ?? ''));
    };
    if (DOCUMENT_FIELDS.has(id)) {
      if (Array.isArray(v) && v.length) pushNormalized(v.map(function(d) {
        return (d && d.name) ? d.name : '';
      }).filter(Boolean).join(', '));
      else pushNormalized('');
    } else if (v === null || v === undefined) { pushNormalized('');
    } else if (Array.isArray(v)) { pushNormalized(v.map(function(x) {
        return (x?.label || x?.name || x?.value || '');
      }).filter(Boolean).join(', '));
    } else if (typeof v === 'object') { pushNormalized(v.label || v.name || v.value || '');
    } else { pushNormalized(v); }
  }
  return arr;
}

/* ====================== FETCH & PAGINACAO ====================== */
function buildTasksUrl_(page1Based) {
  var base = API_BASE + API_VERSION + '/tasks';
  var q = [
    'bypass_status_default=true',
    'include=assignments',
    'include_custom_fields=true',
    'limit=' + PAGE_LIMIT,
    'page=' + (page1Based || 1)
  ];
  return base + '?' + q.join('&');
}

function fetchRunrunPage_(url, creds) {
  var headers = { 'App-Key': creds.KEY, 'User-Token': creds.TOKEN };
  var res = fetchWithBackoffRR_(url, { headers: headers, muteHttpExceptions: true }, 3);
  var code = res.getResponseCode();
  var txt = res.getContentText();

  if (code === 401) throw new Error('Credenciais invalidas (401).');
  if (code < 200 || code >= 300) throw new Error('Bad request (' + code + '): ' + txt.substring(0, 200));

  var data = JSON.parse(txt);
  if (!Array.isArray(data)) throw new Error('Resposta nao e array.');

  var allHeaders = res.getAllHeaders();
  var meta = parseItemRange_(String(allHeaders['X-Item-Range'] || allHeaders['x-item-range'] || ''));
  var nextRel = extractNextPageUrl_(allHeaders['Link'] || allHeaders['link'] || '');
  return { items: data, meta: meta, nextUrl: nextRel ? absolutize_(nextRel) : null };
}

function fetchWithBackoffRR_(url, options, tries) {
  var wait = 400;
  for (var i = 0; i < tries; i++) {
    var res = UrlFetchApp.fetch(url, options);
    var code = res.getResponseCode();
    if (code >= 200 && code < 300) return res;
    if ((code === 429 || (code >= 500 && code <= 599)) && i < tries - 1) {
      Utilities.sleep(wait);
      wait = Math.min(wait * 2, 8000);
      continue;
    }
    return res;
  }
}

function extractNextPageUrl_(linkHeader) {
  if (!linkHeader) return null;
  var parts = linkHeader.split(',');
  for (var i = 0; i < parts.length; i++) {
    var p = parts[i].trim();
    if (/rel="?next"?/i.test(p)) {
      var m = p.match(/<([^>]+)>/);
      if (m) return m[1];
    }
  }
  return null;
}

function absolutize_(maybePath) {
  return /^https?:\/\//i.test(maybePath) ? maybePath : API_BASE + (maybePath.charAt(0) === '/' ? '' : '/') + maybePath;
}

function parseItemRange_(xir) {
  if (!xir) return null;
  var m = xir.match(/items\s+