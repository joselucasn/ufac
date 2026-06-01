/**
 * Runrun.it → Google Sheets (Status Report Geral)
 * SCRIPT CONSOLIDADO v15.3 (Polling + Bulk Insert + Colunas API + Paginacao Numerica)
 */

/* ====================== PARAMETROS ====================== */
var API_BASE      = 'https://secure.runrun.it';
var API_VERSION   = '/api/v1.0';
var SHEET_NAME    = 'Status Report Geral';
var LOG_SHEET     = 'Log Execucoes';
var METRIC_SHEET  = 'Metricas';
var TS_SHEET      = 'RR_Timestamps_Cache';
var SPREADSHEET_ID = '1Z-2zFKhuSHecdIRWyt6RLzKrE2dtpFomsmf7O4abj6k';

var EXECUTION_LIMIT_MS = 5 * 60 * 1000;
var SAFETY_MS          = 60 * 1000;
var MAX_ROWS_PER_FLUSH = 500;
var PAGE_LIMIT         = 1000;

var STATE_KEY        = 'RR_STATE_v84';
var RESUME_HANDLER   = 'resumeFullRR_';
var WATCHDOG_HANDLER = 'watchdogFullRR_';

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
  "custom_249":"Categoria de manutencao","custom_255":"Observacoes do veiculo","custom_256":"Autorizado?",
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

/****************************************************************************
 * MENU E CREDENCIAIS
 ****************************************************************************/
function initTimestampSheet_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sh = ss.getSheetByName(TS_SHEET);
  if (!sh) {
    sh = ss.insertSheet(TS_SHEET);
    sh.getRange(1,1,1,2).setValues([['Task_ID', 'Updated_At']]);
    try { sh.setFrozenRows(1); } catch(_) {}
    try { sh.hideSheet(); } catch(_) {}
  }
  return sh;
}

function getTimestamp_(id) {
  try {
    var sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(TS_SHEET);
    if (!sh) return null;
    var lr = sh.getLastRow();
    if (lr < 2) return null;
    var tf = sh.getRange(2, 1, lr - 1, 1).createTextFinder(String(id));
    tf.matchEntireCell(true);
    var cell = tf.findNext();
    if (!cell) return null;
    return sh.getRange(cell.getRow(), 2).getValue();
  } catch(_) { return null; }
}

function setTimestamp_(id, ts) {
  try {
    var sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(TS_SHEET);
    if (!sh) return;
    var lr = sh.getLastRow();
    if (lr >= 2) {
      var tf = sh.getRange(2, 1, lr - 1, 1).createTextFinder(String(id));
      tf.matchEntireCell(true);
      var cell = tf.findNext();
      if (cell) { sh.getRange(cell.getRow(), 2).setValue(ts); return; }
    }
    if (sh.getMaxRows() < sh.getLastRow() + 2) sh.insertRowsAfter(sh.getLastRow(), 100);
    var nr = sh.getLastRow() + 1;
    sh.getRange(nr, 1, 1, 2).setValues([[String(id), ts]]);
  } catch(_) {}
}

function logInit_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sh = ss.getSheetByName(LOG_SHEET);
  if (!sh) {
    sh = ss.insertSheet(LOG_SHEET);
    sh.getRange(1,1,1,6).setValues([['Timestamp', 'Tipo', 'Task ID', 'Status', 'Mensagem', 'Duracao (s)']]);
    try { sh.setFrozenRows(1); } catch(_) {}
  }
  return sh;
}

function logRegistrar_(tipo, taskId, status, msg, duracao) {
  try {
    var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    var sh = ss.getSheetByName(LOG_SHEET);
    if (!sh) sh = logInit_();
    var now = new Date();
    var ts = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
    var lr = sh.getLastRow() + 1;
    sh.getRange(lr, 1, 1, 6).setValues([[ts, tipo || '', taskId || '', status || '', msg || '', duracao || '']]);
    if (lr > 5000) { sh.deleteRows(2, lr - 5000); }
  } catch(e) { Logger.log('Falha log: '+e.message); }
}

function metricasInit_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sh = ss.getSheetByName(METRIC_SHEET);
  if (!sh) {
    sh = ss.insertSheet(METRIC_SHEET);
    sh.getRange(1,1,1,5).setValues([['Timestamp', 'Operacao', 'Task ID', 'Duracao (ms)', 'Resultado']]);
    try { sh.setFrozenRows(1); } catch(_) {}
  }
  return sh;
}

function metricasRegistrar_(op, taskId, duracaoMs, resultado) {
  try {
    var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    var sh = ss.getSheetByName(METRIC_SHEET);
    if (!sh) sh = metricasInit_();
    var now = new Date();
    var ts = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
    var lr = sh.getLastRow() + 1;
    sh.getRange(lr, 1, 1, 5).setValues([[ts, op || '', taskId || '', duracaoMs || 0, resultado || '']]);
    if (lr > 10000) { sh.deleteRows(2, lr - 10000); }
  } catch(e) { Logger.log('Falha metrica: '+e.message); }
}

function logClear_() {
  try {
    var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    var sh = ss.getSheetByName(LOG_SHEET);
    if (sh) {
      sh.clear();
      sh.getRange(1,1,1,6).setValues([['Timestamp', 'Tipo', 'Task ID', 'Status', 'Mensagem', 'Duracao (s)']]);
    }
  } catch(_) {}
}

function logInitCmd_() { logInit_(); SpreadsheetApp.getUi().alert('Aba \''+LOG_SHEET+'\' criada ou verificada.'); }
function metricasInitCmd_() { metricasInit_(); SpreadsheetApp.getUi().alert('Aba \''+METRIC_SHEET+'\' criada.'); }

function logClearCmd_() {
  if (SpreadsheetApp.getUi().alert('Limpar log?',SpreadsheetApp.getUi().ButtonSet.OK_CANCEL)===SpreadsheetApp.getUi().Button.OK) {
    logClear_(); SpreadsheetApp.getUi().alert('Log limpo.');
  }
}

function testTextFinder_() {
  var ui = SpreadsheetApp.getUi();
  var res = ui.prompt('Test TextFinder', 'Digite o ID da task para buscar:', ui.ButtonSet.OK_CANCEL);
  if (res.getSelectedButton() !== ui.Button.OK) return;
  var id = res.getResponseText().trim();
  if (!id) { ui.alert('ID vazio'); return; }
  var t0 = Date.now();
  try {
    var sh = getSh_();
    if (!sh) { ui.alert('Planilha nao encontrada'); return; }
    var row = findRowFast_(sh, id);
    var ms = Date.now() - t0;
    if (row) {
      ui.alert('Task '+id+' encontrada na linha '+row+' em '+ms+'ms');
    } else {
      ui.alert('Task '+id+' NAO encontrada em '+ms+'ms');
    }
  } catch(e) {
    ui.alert('Erro: '+e.message);
  }
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Runrun.it')
    .addItem(' Configurar Credenciais', 'confCreds_')
    .addSeparator()
    .addItem(' Full Load (agora)', 'fullAgora_')
    .addSeparator()
    .addItem(' Instalar Full Load noturno (03:00)', 'cronFullInstalar_')
    .addItem(' Remover Full Load noturno', 'cronFullRemover_')
    .addSeparator()
    .addItem(' Instalar Rastreador Ativo (5 min)', 'installActiveSync_')
    .addItem(' Remover Rastreador Ativo', 'uninstallActiveSync_')
    .addSeparator()
    .addItem(' Inicializar aba de Log', 'logInitCmd_')
    .addItem(' Limpar Log', 'logClearCmd_')
    .addSeparator()
    .addItem(' Inicializar aba de Metricas', 'metricasInitCmd_')
    .addItem(' Testar TextFinder', 'testTextFinder_')
    .addToUi();
}

function confCreds_() {
  var ui = SpreadsheetApp.getUi();
  var ak = ui.prompt('Runrun.it', 'App-Key:', ui.ButtonSet.OK_CANCEL);
  if (ak.getSelectedButton() !== ui.Button.OK) return;
  var ut = ui.prompt('Runrun.it', 'User-Token:', ui.ButtonSet.OK_CANCEL);
  if (ut.getSelectedButton() !== ui.Button.OK) return;
  PropertiesService.getScriptProperties().setProperties({
    'RR_APP_TOKEN': ak.getResponseText().trim(),
    'RR_USER_TOKEN': ut.getResponseText().trim()
  });
  ui.alert('Credenciais salvas!');
}

function creds_() {
  var p = PropertiesService.getScriptProperties();
  return { KEY: p.getProperty('RR_APP_TOKEN'), TOKEN: p.getProperty('RR_USER_TOKEN') };
}

function fullAgora_() {
  var ok = SpreadsheetApp.getUi().alert('Full Load agora? Isso vai recriar a planilha do zero e ler o historico completo.', SpreadsheetApp.getUi().ButtonSet.OK_CANCEL);
  if (ok !== SpreadsheetApp.getUi().Button.OK) return;
  PropertiesService.getScriptProperties().deleteProperty('RR_LAST_SYNC_FULL');
  fullIniciar_();
}

/****************************************************************************
 * FULL LOAD (1x ao dia - 03:00) — Paginacao Numerica e Lote
 ****************************************************************************/
function cronFullInstalar_() {
  ScriptApp.getProjectTriggers().filter(function(t) {
    return t.getHandlerFunction() === 'cronFullRodar_';
  }).forEach(function(t) { ScriptApp.deleteTrigger(t); });

  ScriptApp.newTrigger('cronFullRodar_').timeBased().atHour(3).nearMinute(0).everyDays(1).create();
  SpreadsheetApp.getUi().alert('Full Load noturno instalado! Roda todo dia as 03:00.');
}

function cronFullRemover_() {
  ScriptApp.getProjectTriggers().filter(function(t) {
    return t.getHandlerFunction() === 'cronFullRodar_';
  }).forEach(function(t) { ScriptApp.deleteTrigger(t); });
  SpreadsheetApp.getUi().alert('Full Load noturno removido.');
}

function cronFullRodar_() {
  PropertiesService.getScriptProperties().deleteProperty('RR_LAST_SYNC_FULL');
  fullIniciar_();
}

function fullIniciar_() {
  lockExec_(function() {
    resetEst_();
    saveEst_({
      initialized: false,
      page: 1,
      nextWriteRow: 2,
      isFull: true,
      itemsProcessedThisRun: 0
    });
    fullCore_();
  });
}

function resumeFullRR_() {
  lockExec_(function() {
    var s = loadEst_();
    if (!s || !s.page) { fin_(); return; }
    fullCore_();
  });
}

function fullCore_() {
  var cr = creds_();
  if (!cr.KEY || !cr.TOKEN) {
    logRegistrar_('FULL', '', 'ERRO', 'Credenciais nao encontradas', 0);
    throw new Error('Credenciais nao encontradas');
  }
  logInit_();
  logRegistrar_('FULL', '', 'INICIO', 'Full load iniciado', 0);

  var tsSh = initTimestampSheet_();
  var tsLr = tsSh.getLastRow();
  if (tsLr > 1) { tsSh.getRange(2, 1, tsLr - 1, 2).clearContent(); }

  var start = Date.now();
  var st = loadEst_();
  var tsInicio = st.startTime || start;
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);

  if (!st.initialized) {
    var lr = sh.getLastRow();
    if (lr > 1) {
      sh.getRange(2, 1, lr - 1, sh.getLastColumn()).clearContent();
    }
    try { sh.getFilter() && sh.getFilter().remove(); } catch(_) {}
    try { sh.clearNotes(); } catch(_) {}

    var ch = CUSTOM_IDS.map(function(id) { return CUSTOM_NAME_MAP[id] || id; });
    var hdr = BASE_HEADERS.concat(ch);
    sh.getRange(1, 1, 1, hdr.length).setValues([hdr]);
    try { sh.setFrozenRows(1); } catch(_) {}

    var bc = BASE_HEADERS.length;
    CUSTOM_IDS.forEach(function(id, idx) {
      if (NUMERIC_CUSTOMS.has(id)) {
        try { sh.getRange(2, bc+idx+1, sh.getMaxRows()-1, 1).setNumberFormat('#,##0.00'); } catch(_) {}
      }
    });

    st.initialized = true;
    st.nextWriteRow = 2;
    saveEst_(st);
  }

  var tsBuf = [];
  var pg = st.page, nwr = st.nextWriteRow;
  var ip = st.itemsProcessedThisRun || 0;
  var buf = [];

  try {
    while (true) {
      if (Date.now() - start > (EXECUTION_LIMIT_MS - SAFETY_MS)) {
        saveEst_({initialized:true, page:pg, nextWriteRow:nwr, isFull:true, itemsProcessedThisRun:ip+buf.length, startTime:tsInicio});
        logRegistrar_('FULL', '', 'PAUSA', 'Limite, retomando. Proc: '+(ip+buf.length), Math.round((Date.now()-tsInicio)/1000));
        schedRet_(30);
        return;
      }

      var url = urlTasks_(pg);
      var r = fetchRetry_(url, {headers: {'App-Key':cr.KEY, 'User-Token':cr.TOKEN}, muteHttpExceptions: true}, 3);
      var d = JSON.parse(r.getContentText());
      var its = d.tasks || d.data || [];

      if (!Array.isArray(its) || its.length === 0) break;

      var mc = [pg, '', its.length, ''];

      for (var i = 0; i < its.length; i++) {
        var t = its[i], tid = String(t.id);
        var rd = mc.concat(mapBase_(t)).concat(mapCustom_(t));
        buf.push(rd);

        var ts = t.updated_at || t.created_at || '';
        if (ts) tsBuf.push([tid, ts]);

        if (buf.length >= MAX_ROWS_PER_FLUSH) {
          flush_(sh, buf, nwr);
          nwr += buf.length;
          buf = [];
          if (tsBuf.length > 0) {
            var tsSh_local = initTimestampSheet_();
            var tsNr = tsSh_local.getLastRow() + 1;
            tsSh_local.getRange(tsNr, 1, tsBuf.length, 2).setValues(tsBuf);
            tsBuf = [];
          }
        }
      }
      pg++;
    }

    if (buf.length > 0) { flush_(sh, buf, nwr); }

    if (tsBuf.length > 0) {
      var tsSh_end = initTimestampSheet_();
      var tsNr_end = tsSh_end.getLastRow() + 1;
      tsSh_end.getRange(tsNr_end, 1, tsBuf.length, 2).setValues(tsBuf);
      tsBuf = [];
    }

    PropertiesService.getScriptProperties().setProperty('RR_LAST_SYNC_FULL', fmtData_(new Date()));
    fin_();

    var total = ip + nwr - 2;
    sh.getRange(2,1).setNote('Full Load | '+new Date().toLocaleString()+' | '+total+' regs');
    Logger.log('Full Load concluido: '+total+' registros');

  } catch(e) {
    saveEst_({initialized:true, page:pg, nextWriteRow:nwr, isFull:true, itemsProcessedThisRun:ip+buf.length, startTime:tsInicio});
    logRegistrar_('FULL', '', 'ERRO', e.message.substring(0,250), Math.round((Date.now()-tsInicio)/1000));
    schedRet_(60);
    throw e;
  }
}

/****************************************************************************
 * RASTREADOR ATIVO (Polling 5 min) — OTIMIZADO: BULK INSERT
 ****************************************************************************/
function syncAlteracoesRecentes_() {
 var lock = LockService.getScriptLock();
 try {
 if (!lock.tryLock(30000)) { logRegistrar_('SYNC', '', 'SKIP', 'Lock ocupado', 0); return; }
 } catch(e) { return; }

 try {
 var tsInicio = Date.now();
 var props = PropertiesService.getScriptProperties();
 var ultimoSync = props.getProperty('LAST_SYNC_TS') || '';
 var agora = new Date();
 var cr = creds_();

 var url = API_BASE + API_VERSION + '/tasks?bypass_status_default=true&include=assignments&include_custom_fields=true&limit=50';
 if (ultimoSync) {
 var dtPartida = new Date(ultimoSync);
 dtPartida.setSeconds(dtPartida.getSeconds() - 10);
 url += '&updated_at_after=' + encodeURIComponent(dtPartida.toISOString());
 } else {
 url += '&updated_at_after=' + encodeURIComponent(new Date(agora.getTime() - 3600000).toISOString());
 }

 var sh = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
 if (!sh) { logRegistrar_('SYNC', '', 'ERRO', 'Sheet nao encontrada', 0); return; }

 var processados = 0;
 var MAIS_RECENTE_TS = ultimoSync;
 var SAFETY_EXIT = 280000;
 var MAX_PAGINAS = 20;
 var nextUrl = url;

 // BULK INSERT: acumula novas tarefas para inserir em lote
 var novasTarefas = [];

 while (nextUrl) {
 paginasLidas++;
 if (paginasLidas > MAX_PAGINAS) { if (MAIS_RECENTE_TS) props.setProperty('LAST_SYNC_TS', MAIS_RECENTE_TS); break; }
 if ((Date.now() - tsInicio) > SAFETY_EXIT) { if (MAIS_RECENTE_TS) props.setProperty('LAST_SYNC_TS', MAIS_RECENTE_TS); break; }

 var r = fetchRetry_(nextUrl, {
 headers: {'App-Key': cr.KEY, 'User-Token': cr.TOKEN},
 muteHttpExceptions: true
 }, 3);

 var body = JSON.parse(r.getContentText());
 var tasks = body.tasks || body.data || [];
 if (tasks.length === 0) break;

 for (var i = 0; i < tasks.length; i++) {
 try {
 var td = tasks[i];
 var tid = String(td.id);
 var taskTs = td.updated_at || td.created_at || '';

 if (taskTs) {
 try {
 var cachedTs = getTimestamp_(tid);
 if (cachedTs) {
 var incoming = new Date(taskTs).getTime();
 var cached = new Date(cachedTs).getTime();
 if (!isNaN(incoming) && !isNaN(cached) && incoming <= cached) continue;
 }
 } catch(_) {}
 }

 var ex = findRowFast_(sh, tid);
 var rd = ['', '', '', ''].concat(mapBase_(td)).concat(mapCustom_(td));

 if (ex) {
 // Existe → atualiza direto na linha
 try { sh.getRange(ex, 1, 1, rd.length).setValues([rd]); } catch(_) {}
 } else {
 // Nova → guarda no array para bulk insert
 novasTarefas.push(rd);
 }

 processados++;
 if (taskTs) {
 try { setTimestamp_(tid, taskTs); } catch(_) {}
 if (taskTs > MAIS_RECENTE_TS || !MAIS_RECENTE_TS) MAIS_RECENTE_TS = taskTs;
 }
 } catch(e) {
 try { logRegistrar_('SYNC', tid, 'ERRO', String(e).substring(0,200), 0); } catch(_) {}
 }
 }

 if (MAIS_RECENTE_TS) props.setProperty('LAST_SYNC_TS', MAIS_RECENTE_TS);

 var pag = body.pagination || {};
 var prox = pag.next || '';
 nextUrl = prox ? API_BASE + API_VERSION + prox : null;
 }

 // BULK INSERT: insere todas as novas tarefas em unica operacao
 if (novasTarefas.length > 0) {
 sh.insertRowsBefore(2, novasTarefas.length);
 sh.getRange(2, 1, novasTarefas.length, novasTarefas[0].length).setValues(novasTarefas);
 }

 if (MAIS_RECENTE_TS) props.setProperty('LAST_SYNC_TS', MAIS_RECENTE_TS);
 var msg = processados + ' tasks (' + novasTarefas.length + ' novas em lote)';
 logRegistrar_('SYNC', '', 'OK', msg, Math.round((Date.now()-tsInicio)/1000));
 try { metricasRegistrar_('SYNC', String(processados), Date.now()-tsInicio, msg); } catch(_) {}

 } catch(e) {
 try { logRegistrar_('SYNC', '', 'ERRO', 'Geral: '+String(e).substring(0,200), 0); } catch(_) {}
 } finally {
 try { lock.releaseLock(); } catch(_) {}
 }
}

function installActiveSync_() {
 try {
 var triggers = ScriptApp.getProjectTriggers();
 for (var i = 0; i < triggers.length; i++) {
 if (triggers[i].getHandlerFunction() === 'syncAlteracoesRecentes_') {
 return 'Rastreador ja instalado';
 }
 }
 ScriptApp.newTrigger('syncAlteracoesRecentes_').timeBased().everyMinutes(5).create();
 SpreadsheetApp.getUi().alert('Rastreador ativo instalado! Sincroniza a cada 5 minutos.');
 } catch(e) {
 SpreadsheetApp.getUi().alert('Erro: '+String(e));
 }
}

function uninstallActiveSync_() {
 try {
 var triggers = ScriptApp.getProjectTriggers();
 for (var i = 0; i < triggers.length; i++) {
 if (triggers[i].getHandlerFunction() === 'syncAlteracoesRecentes_') {
 ScriptApp.deleteTrigger(triggers[i]);
 }
 }
 SpreadsheetApp.getUi().alert('Rastreador removido.');
 } catch(e) {
 SpreadsheetApp.getUi().alert('Erro: '+String(e));
 }
}

/****************************************************************************
 * FUNCOES COMPARTILHADAS
 ****************************************************************************/
function getSh_() { return SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME); }

function findRowFast_(sh, taskId) {
  var lr = sh.getLastRow();
  if (lr < 2 || !taskId) return null;
  var tf = sh.getRange(2, 15, lr - 1, 1).createTextFinder(String(taskId));
  tf.matchEntireCell(true);
  var cell = tf.findNext();
  return cell ? cell.getRow() : null;
}

function updRow_(sh, r, d) { sh.getRange(r, 1, 1, d.length).setValues([d]); }

function addRow_(sh, d) {
  if (sh.getMaxRows() < sh.getLastRow() + 2) sh.insertRowsAfter(sh.getLastRow(), 100);
  sh.getRange(sh.getLastRow() + 1, 1, 1, d.length).setValues([d]);
}

function flush_(sh, rows, sr) {
  if (!rows.length) return;
  sh.getRange(sr, 1, rows.length, rows[0].length).setValues(rows);
}

function mapBase_(t) {
  var as = (t.assignments||[]).map(function(a){return a.assignee_name}).filter(Boolean).join(', ');
  var tg = (t.tags||[]).join(', ');
  return [
    t.board_name||'', t.client_name||'', t.project_group_name||'', t.project_name||'',
    t.parent_task_id||'', t.parent_task_title||'', t.type_name||'', t.team_name||'',
    t.cost_center||'', as, t.id||'', t.title||'', t.is_urgent?'Sim':'Nao',
    t.priority||'', t.user_name||'', t.created_at||'', t.desired_date||'',
    t.estimated_delivery_date||'', t.close_date||'',
    t.current_estimate_seconds ? t.current_estimate_seconds/3600 : '',
    t.first_estimate||'', t.time_worked ? t.time_worked/3600 : '',
    t.all_subtasks_time_total ? t.all_subtasks_time_total/3600 : '',
    t.time_progress||'', t.task_state_name||'', t.board_stage_name||'',
    t.was_reopened?'Sim':'Nao', tg, t.client_custom_code||'',
    t.time_pending ? t.time_pending/3600 : ''
  ];
}

function mapCustom_(t) {
  var cf = (t && t.custom_fields) || {}, arr = [];
  for (var j=0; j<CUSTOM_IDS.length; j++) {
    var id = CUSTOM_IDS[j], v = cf[id];
    if (DOCUMENT_FIELDS.has(id)) {
      arr.push(Array.isArray(v)&&v.length ? v.map(function(d){return d&&d.name?d.name:''}).filter(Boolean).join(', ') : '');
    } else if (v===null||v===undefined) { arr.push(''); }
    else if (Array.isArray(v)) { arr.push(v.map(function(x){return (x&&(x.label||x.name||x.value))||''}).filter(Boolean).join(', ')); }
    else if (typeof v==='object') { arr.push(v.label||v.name||v.value||''); }
    else if (NUMERIC_CUSTOMS.has(id)) { arr.push(num_(v)); }
    else { arr.push(String(v)); }
  }
  return arr;
}

function num_(v) {
  if (v===null||v===undefined) return '';
  if (typeof v==='number'&&Number.isFinite(v)) return v;
  var s = String(v).trim().replace(/\u00A0/g,' ').replace(/\s+/g,'').replace(/[^0-9,.\-]/g,'');
  if (!s) return '';
  var lc=s.lastIndexOf(','),ld=s.lastIndexOf('.');
  if (lc!==-1&&ld!==-1) s=(lc>ld)?s.replace(/\./g,'').replace(/,/g,'.'):s.replace(/,/g,'');
  else if (lc!==-1) s=s.replace(/\./g,'').replace(/,/g,'.');
  var n=Number(s); return Number.isFinite(n)?n:'';
}

function urlTasks_(p) {
  return API_BASE + API_VERSION + '/tasks?bypass_status_default=true&include=assignments&include_custom_fields=true&limit=' + PAGE_LIMIT + '&page=' + (p || 1);
}

function fetchRetry_(url, opts, tries) {
  var w = 400;
  for (var i=0; i<tries; i++) {
    var r = UrlFetchApp.fetch(url, opts);
    if (r.getResponseCode()>=200&&r.getResponseCode()<300) return r;
    Utilities.sleep(w); w=Math.min(w*2,8000);
  }
  return UrlFetchApp.fetch(url, opts);
}

function fmtData_(d) {
  var pad=function(n){return String(n).padStart(2,'0');};
  return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds());
}

function resp_(c,m) { return ContentService.createTextOutput(JSON.stringify({status:c, message:m})).setMimeType(ContentService.MimeType.JSON); }
function loadEst_() { var r=PropertiesService.getScriptProperties().getProperty(STATE_KEY); return r?JSON.parse(r):null; }
function saveEst_(o) { PropertiesService.getScriptProperties().setProperty(STATE_KEY, JSON.stringify(o)); }
function resetEst_() { PropertiesService.getScriptProperties().deleteProperty(STATE_KEY); }

function schedRet_(s) {
  delRes_();
  ScriptApp.newTrigger(RESUME_HANDLER).timeBased().after(s*1000).create();
  if (!temTrig_(WATCHDOG_HANDLER)) ScriptApp.newTrigger(WATCHDOG_HANDLER).timeBased().everyMinutes(1).create();
}

function delRes_() { ScriptApp.getProjectTriggers().filter(function(t){return t.getHandlerFunction()===RESUME_HANDLER}).forEach(function(t){ScriptApp.deleteTrigger(t)}); }
function delWatch_() { ScriptApp.getProjectTriggers().filter(function(t){return t.getHandlerFunction()===WATCHDOG_HANDLER}).forEach(function(t){ScriptApp.deleteTrigger(t)}); }
function temTrig_(h) { return ScriptApp.getProjectTriggers().some(function(t){return t.getHandlerFunction()===h}); }
function lockExec_(fn) {
  var lk = LockService.getScriptLock();
  if (!lk.tryLock(10000)) return;
  try { fn(); } finally { lk.releaseLock(); }
}
function fin_() { delRes_(); delWatch_(); resetEst_(); }

function watchdogFullRR_() {
  var s = loadEst_();
  if (!(s && s.page)) { delWatch_(); return; }
  if (!temTrig_(RESUME_HANDLER)) ScriptApp.newTrigger(RESUME_HANDLER).timeBased().after(10*1000).create();
}
