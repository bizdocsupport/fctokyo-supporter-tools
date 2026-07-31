/**
 * FC東京 試合日程カレンダー同期
 * Version 0.1.0
 *
 * Googleスプレッドシートの「schedule」シートをマスターとして、
 * FC東京トップチーム / FC東京U-21 の公開Googleカレンダーを更新します。
 *
 * 重要:
 * - calendar_event_id を保存し、日時確定後も同じイベントを更新します。
 * - 候補日が複数ある場合は、候補期間の終日イベントを1件作成します。
 */

const SHEET_NAME = 'schedule';
const TIMEZONE = 'Asia/Tokyo';

const HEADERS = [
  'match_id',
  'team',
  'competition',
  'round',
  'status',
  'candidate_start',
  'candidate_end',
  'candidate_dates',
  'confirmed_date',
  'kickoff',
  'duration_minutes',
  'home_away',
  'opponent',
  'venue',
  'official_url',
  'ticket_url',
  'note',
  'enabled',
  'calendar_event_id',
  'last_synced',
  'sync_result',
];

const PUBLIC_HEADERS = HEADERS.filter((name) => ![
  'calendar_event_id',
  'last_synced',
  'sync_result',
].includes(name));


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('FC東京カレンダー')
    .addItem('1. 初期シートを作成', 'setupMasterSheet')
    .addItem('2. カレンダーへ同期', 'syncAllCalendars')
    .addSeparator()
    .addItem('自動同期を設定', 'installTriggers')
    .addItem('自動同期を解除', 'removeTriggers')
    .addSeparator()
    .addItem('設定状況を確認', 'showSettings')
    .addToUi();
}


function setupMasterSheet() {
  const ss = SpreadsheetApp.getActive();
  let sheet = ss.getSheetByName(SHEET_NAME);

  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }

  if (sheet.getLastRow() > 0) {
    const answer = SpreadsheetApp.getUi().alert(
      '確認',
      'scheduleシートを初期化します。既存データは消えます。続けますか？',
      SpreadsheetApp.getUi().ButtonSet.YES_NO
    );
    if (answer !== SpreadsheetApp.getUi().Button.YES) {
      return;
    }
    sheet.clear();
  }

  const sampleRows = getSampleRows_();
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  sheet.getRange(2, 1, sampleRows.length, HEADERS.length).setValues(sampleRows);

  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, HEADERS.length)
    .setBackground('#003b7a')
    .setFontColor('#ffffff')
    .setFontWeight('bold')
    .setWrap(true);

  sheet.getDataRange().setVerticalAlignment('middle');
  sheet.getRange(2, 1, Math.max(sampleRows.length, 1), HEADERS.length).setWrap(true);

  const widths = {
    1: 175, 2: 72, 3: 155, 4: 120, 5: 100,
    6: 105, 7: 105, 8: 185, 9: 105, 10: 82,
    11: 95, 12: 85, 13: 190, 14: 175, 15: 220,
    16: 220, 17: 280, 18: 75, 19: 250, 20: 150, 21: 220,
  };
  Object.keys(widths).forEach((column) => {
    sheet.setColumnWidth(Number(column), widths[column]);
  });

  const rows = Math.max(sheet.getMaxRows() - 1, 1);
  setValidation_(sheet, 2, 2, rows, ['TOP', 'U21']);
  setValidation_(sheet, 2, 5, rows, [
    '確定', '候補日あり', '進出時', '開催未定', '延期', '中止'
  ]);
  setValidation_(sheet, 2, 12, rows, ['HOME', 'AWAY']);
  setValidation_(sheet, 2, 18, rows, ['TRUE', 'FALSE']);

  sheet.getRange('F:G').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('I:I').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('J:J').setNumberFormat('hh:mm');
  sheet.getRange('T:T').setNumberFormat('yyyy-mm-dd hh:mm:ss');

  sheet.getRange(2, 19, sheet.getMaxRows() - 1, 3)
    .setBackground('#f3f4f6')
    .setFontColor('#5f6368');

  SpreadsheetApp.getUi().alert(
    '初期シートを作成しました。\n'
    + '次にApps Scriptの「プロジェクトの設定」→「スクリプト プロパティ」で、'
    + 'TOP_CALENDAR_ID と U21_CALENDAR_ID を設定してください。'
  );
}


function setValidation_(sheet, startRow, column, numRows, values) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(values, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(startRow, column, numRows, 1).setDataValidation(rule);
}


function syncAllCalendars() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {
    throw new Error('別の同期処理が実行中です。少し待ってから再実行してください。');
  }

  try {
    const ss = SpreadsheetApp.getActive();
    const sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet || sheet.getLastRow() < 2) {
      throw new Error('scheduleシートにデータがありません。');
    }

    const settings = getSettings_();
    if (!settings.TOP_CALENDAR_ID || !settings.U21_CALENDAR_ID) {
      throw new Error(
        'スクリプト プロパティに TOP_CALENDAR_ID と U21_CALENDAR_ID を設定してください。'
      );
    }

    const values = sheet.getDataRange().getValues();
    const headers = values[0].map(String);
    validateHeaders_(headers);
    const index = createIndex_(headers);

    for (let i = 1; i < values.length; i++) {
      const rowNumber = i + 1;
      const row = values[i];
      const enabled = parseBoolean_(row[index.enabled]);

      if (!enabled) {
        sheet.getRange(rowNumber, index.sync_result + 1).setValue('無効のため同期対象外');
        continue;
      }

      try {
        syncOneRow_(sheet, rowNumber, row, index, settings);
      } catch (error) {
        sheet.getRange(rowNumber, index.last_synced + 1).setValue(new Date());
        sheet.getRange(rowNumber, index.sync_result + 1)
          .setValue(`ERROR: ${error.message}`);
      }
    }
  } finally {
    lock.releaseLock();
  }
}


function syncOneRow_(sheet, rowNumber, row, index, settings) {
  const matchId = clean_(row[index.match_id]);
  if (!matchId) {
    throw new Error('match_id が空です。');
  }

  const team = clean_(row[index.team]).toUpperCase();
  const calendarId = team === 'TOP'
    ? settings.TOP_CALENDAR_ID
    : team === 'U21'
      ? settings.U21_CALENDAR_ID
      : '';

  if (!calendarId) {
    throw new Error(`team は TOP または U21 を指定してください: ${team}`);
  }

  const calendar = CalendarApp.getCalendarById(calendarId);
  if (!calendar) {
    throw new Error(`カレンダーを取得できません: ${team}`);
  }

  const payload = buildEventPayload_(row, index, settings);
  const storedEventId = clean_(row[index.calendar_event_id]);
  let event = null;

  if (storedEventId) {
    event = calendar.getEventById(storedEventId);
  }

  let action = '更新';
  if (!event) {
    event = createEvent_(calendar, payload);
    action = '新規作成';
  } else {
    updateEvent_(event, payload);
  }

  sheet.getRange(rowNumber, index.calendar_event_id + 1).setValue(event.getId());
  sheet.getRange(rowNumber, index.last_synced + 1).setValue(new Date());
  sheet.getRange(rowNumber, index.sync_result + 1)
    .setValue(`${action}：${payload.title}`);
}


function buildEventPayload_(row, index, settings) {
  const team = clean_(row[index.team]).toUpperCase();
  const status = clean_(row[index.status]) || '候補日あり';
  const opponent = clean_(row[index.opponent]) || '対戦相手未定';
  const teamName = team === 'TOP' ? 'FC東京' : 'FC東京U-21';

  let prefix = '';
  if (status === '候補日あり' || status === '延期' || status === '開催未定') {
    prefix = '【日時未定】';
  } else if (status === '進出時') {
    prefix = '【進出時・日時未定】';
  } else if (status === '中止') {
    prefix = '【中止】';
  }

  const title = `${prefix}${teamName} vs ${opponent}`;
  const confirmedDate = parseDate_(row[index.confirmed_date]);
  const candidateStart = parseDate_(row[index.candidate_start]);
  const candidateEnd = parseDate_(row[index.candidate_end]);
  const timeValue = parseTime_(row[index.kickoff]);
  const duration = Number(row[index.duration_minutes]) || 120;

  let allDay = true;
  let start;
  let end;

  if (status === '確定' && confirmedDate) {
    if (timeValue) {
      allDay = false;
      start = new Date(
        confirmedDate.getFullYear(),
        confirmedDate.getMonth(),
        confirmedDate.getDate(),
        timeValue.hour,
        timeValue.minute,
        0
      );
      end = new Date(start.getTime() + duration * 60 * 1000);
    } else {
      start = confirmedDate;
      end = addDays_(confirmedDate, 1);
    }
  } else {
    start = candidateStart || confirmedDate;
    const inclusiveEnd = candidateEnd || candidateStart || confirmedDate;
    if (!start || !inclusiveEnd) {
      throw new Error('確定日または候補期間を入力してください。');
    }
    end = addDays_(inclusiveEnd, 1);
  }

  const description = buildDescription_(row, index, settings);
  return {
    title,
    description,
    location: clean_(row[index.venue]),
    allDay,
    start,
    end,
  };
}


function buildDescription_(row, index, settings) {
  const lines = [];
  const add = (label, value) => {
    const text = clean_(value);
    if (text) lines.push(`${label}：${text}`);
  };

  add('試合ID', row[index.match_id]);
  add('ステータス', row[index.status]);
  add('大会', row[index.competition]);
  add('節・ラウンド', row[index.round]);
  add('HOME/AWAY', row[index.home_away]);
  add('候補日', row[index.candidate_dates]);
  add('会場', row[index.venue]);
  add('備考', row[index.note]);

  const officialUrl = clean_(row[index.official_url]);
  const ticketUrl = clean_(row[index.ticket_url]) || settings.TICKET_APP_URL;

  if (officialUrl) {
    lines.push(`公式情報：${officialUrl}`);
  }
  if (ticketUrl) {
    lines.push(`チケット発売日ナビ：${ticketUrl}`);
  }

  lines.push('');
  lines.push('※FC東京公式サービスではありません。');
  lines.push('※最新情報はクラブ・大会主催者の公式発表をご確認ください。');

  return lines.join('\n');
}


function createEvent_(calendar, payload) {
  let event;
  if (payload.allDay) {
    event = calendar.createAllDayEvent(
      payload.title,
      payload.start,
      payload.end,
      {
        description: payload.description,
        location: payload.location,
      }
    );
  } else {
    event = calendar.createEvent(
      payload.title,
      payload.start,
      payload.end,
      {
        description: payload.description,
        location: payload.location,
      }
    );
  }
  event.setVisibility(CalendarApp.Visibility.PUBLIC);
  return event;
}


function updateEvent_(event, payload) {
  event.setTitle(payload.title);
  event.setDescription(payload.description);
  event.setLocation(payload.location || '');
  event.setVisibility(CalendarApp.Visibility.PUBLIC);

  if (payload.allDay) {
    event.setAllDayDates(payload.start, payload.end);
  } else {
    event.setTime(payload.start, payload.end);
  }
}


function syncOnEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== SHEET_NAME || e.range.getRow() === 1) return;
  syncAllCalendars();
}


function installTriggers() {
  removeTriggers();

  const ss = SpreadsheetApp.getActive();
  ScriptApp.newTrigger('syncOnEdit')
    .forSpreadsheet(ss)
    .onEdit()
    .create();

  ScriptApp.newTrigger('syncAllCalendars')
    .timeBased()
    .everyHours(6)
    .create();

  SpreadsheetApp.getUi().alert(
    '自動同期を設定しました。\n'
    + '・scheduleシート編集時\n'
    + '・6時間ごとの保険同期'
  );
}


function removeTriggers() {
  const targets = new Set(['syncOnEdit', 'syncAllCalendars']);
  ScriptApp.getProjectTriggers().forEach((trigger) => {
    if (targets.has(trigger.getHandlerFunction())) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}


function showSettings() {
  const settings = getSettings_();
  const mask = (value) => value
    ? `${value.substring(0, 6)}...${value.substring(Math.max(value.length - 8, 6))}`
    : '未設定';

  SpreadsheetApp.getUi().alert(
    `TOP_CALENDAR_ID：${mask(settings.TOP_CALENDAR_ID)}\n`
    + `U21_CALENDAR_ID：${mask(settings.U21_CALENDAR_ID)}\n`
    + `TICKET_APP_URL：${settings.TICKET_APP_URL || '未設定'}`
  );
}


/**
 * Streamlitアプリ向けの公開JSON API。
 * Apps Scriptをウェブアプリとしてデプロイすると利用できます。
 */
function doGet() {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  if (!sheet || sheet.getLastRow() < 2) {
    return jsonOutput_({updated_at: '', data: []});
  }

  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(String);
  validateHeaders_(headers);
  const index = createIndex_(headers);

  const data = [];
  for (let i = 1; i < values.length; i++) {
    if (!parseBoolean_(values[i][index.enabled])) continue;

    const record = {};
    PUBLIC_HEADERS.forEach((name) => {
      record[name] = serializeValue_(values[i][index[name]], name);
    });
    data.push(record);
  }

  return jsonOutput_({
    updated_at: Utilities.formatDate(new Date(), TIMEZONE, 'yyyy/MM/dd HH:mm'),
    data,
  });
}


function jsonOutput_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}


function getSettings_() {
  const props = PropertiesService.getScriptProperties();
  return {
    TOP_CALENDAR_ID: clean_(props.getProperty('TOP_CALENDAR_ID')),
    U21_CALENDAR_ID: clean_(props.getProperty('U21_CALENDAR_ID')),
    TICKET_APP_URL: clean_(
      props.getProperty('TICKET_APP_URL')
      || 'https://club-ticket-navi-fctokyo-test.streamlit.app/'
    ),
  };
}


function createIndex_(headers) {
  const index = {};
  headers.forEach((name, i) => {
    index[name] = i;
  });
  return index;
}


function validateHeaders_(headers) {
  const missing = HEADERS.filter((name) => !headers.includes(name));
  if (missing.length) {
    throw new Error(`scheduleシートの列が不足しています: ${missing.join(', ')}`);
  }
}


function parseBoolean_(value) {
  if (value === true) return true;
  const text = clean_(value).toLowerCase();
  return ['true', '1', 'yes', 'on', '有効'].includes(text);
}


function parseDate_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }

  const text = clean_(value);
  if (!text) return null;
  const match = text.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/);
  if (!match) return null;

  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}


function parseTime_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return {hour: value.getHours(), minute: value.getMinutes()};
  }

  const text = clean_(value);
  if (!text) return null;
  const match = text.match(/^(\d{1,2}):(\d{2})/);
  if (!match) return null;

  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return {hour, minute};
}


function addDays_(date, days) {
  const result = new Date(date.getTime());
  result.setDate(result.getDate() + days);
  return result;
}


function clean_(value) {
  if (value === null || value === undefined) return '';
  return String(value).trim();
}


function serializeValue_(value, name) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    if (name === 'kickoff') {
      return Utilities.formatDate(value, TIMEZONE, 'HH:mm');
    }
    return Utilities.formatDate(value, TIMEZONE, 'yyyy-MM-dd');
  }
  if (typeof value === 'boolean') return value;
  return value === null || value === undefined ? '' : String(value);
}


function getSampleRows_() {
  const ticketApp = 'https://club-ticket-navi-fctokyo-test.streamlit.app/';
  const row = (values) => HEADERS.map((header) => (
    Object.prototype.hasOwnProperty.call(values, header) ? values[header] : ''
  ));

  return [
    row({
      match_id: 'U21-2026-04-OKAYAMA',
      team: 'U21',
      competition: 'U-21 Jリーグ 交流戦',
      round: '第4節',
      status: '確定',
      confirmed_date: '2026-12-06',
      kickoff: '14:00',
      duration_minutes: 120,
      home_away: 'AWAY',
      opponent: 'U-21 ファジアーノ岡山',
      ticket_url: ticketApp,
      enabled: true,
    }),
    row({
      match_id: 'U21-2026-06-NAGOYA',
      team: 'U21',
      competition: 'U-21 Jリーグ 交流戦',
      round: '第6節',
      status: '確定',
      confirmed_date: '2026-12-19',
      kickoff: '15:00',
      duration_minutes: 120,
      home_away: 'HOME',
      opponent: 'U-21 名古屋グランパス',
      venue: 'AGFフィールド',
      ticket_url: ticketApp,
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-06-IWATA',
      team: 'U21',
      competition: 'U-21 Jリーグ',
      round: '第6節',
      status: '候補日あり',
      candidate_start: '2027-02-13',
      candidate_end: '2027-02-15',
      candidate_dates: '2/13(土)・2/14(日)・2/15(月)',
      home_away: 'AWAY',
      opponent: 'U-21 ジュビロ磐田',
      ticket_url: ticketApp,
      note: '開催日時確定後、同じイベントを正式日時へ更新',
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-07-KAWASAKI',
      team: 'U21',
      competition: 'U-21 Jリーグ',
      round: '第7節',
      status: '候補日あり',
      candidate_start: '2027-02-20',
      candidate_end: '2027-02-22',
      candidate_dates: '2/20(土)・2/21(日)・2/22(月)',
      home_away: 'AWAY',
      opponent: 'U-21 川崎フロンターレ',
      ticket_url: ticketApp,
      note: '開催日時確定後、同じイベントを正式日時へ更新',
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-08-URAWA',
      team: 'U21',
      competition: 'U-21 Jリーグ',
      round: '第8節',
      status: '候補日あり',
      candidate_start: '2027-02-27',
      candidate_end: '2027-03-01',
      candidate_dates: '2/27(土)・2/28(日)・3/1(月)',
      home_away: 'HOME',
      opponent: 'U-21 浦和レッズ',
      ticket_url: ticketApp,
      note: '候補期間を終日予定1件で登録',
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-09-SHIMIZU',
      team: 'U21',
      competition: 'U-21 Jリーグ',
      round: '第9節',
      status: '候補日あり',
      candidate_start: '2027-03-06',
      candidate_end: '2027-03-08',
      candidate_dates: '3/6(土)・3/7(日)・3/8(月)',
      home_away: 'AWAY',
      opponent: 'U-21 清水エスパルス',
      ticket_url: ticketApp,
      note: '開催日時確定後、同じイベントを正式日時へ更新',
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-10-VERDY',
      team: 'U21',
      competition: 'U-21 Jリーグ',
      round: '第10節',
      status: '候補日あり',
      candidate_start: '2027-03-13',
      candidate_end: '2027-03-15',
      candidate_dates: '3/13(土)・3/14(日)・3/15(月)',
      home_away: 'HOME',
      opponent: 'U-21 東京ヴェルディ',
      ticket_url: ticketApp,
      note: '開催日時確定後、同じイベントを正式日時へ更新',
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-PO-01',
      team: 'U21',
      competition: 'U-21 Jリーグ プレーオフ',
      round: '第1節',
      status: '進出時',
      candidate_start: '2027-04-03',
      candidate_end: '2027-04-04',
      candidate_dates: '4/3(土)・4/4(日)',
      home_away: 'HOME',
      opponent: '対戦相手未定',
      ticket_url: ticketApp,
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-PO-02',
      team: 'U21',
      competition: 'U-21 Jリーグ プレーオフ',
      round: '第2節',
      status: '進出時',
      candidate_start: '2027-04-10',
      candidate_end: '2027-04-11',
      candidate_dates: '4/10(土)・4/11(日)',
      home_away: 'AWAY',
      opponent: '対戦相手未定',
      ticket_url: ticketApp,
      enabled: true,
    }),
    row({
      match_id: 'U21-2027-PO-FINAL',
      team: 'U21',
      competition: 'U-21 Jリーグ プレーオフ',
      round: '決勝・3位決定戦',
      status: '進出時',
      candidate_start: '2027-04-17',
      candidate_end: '2027-04-18',
      candidate_dates: '4/17(土)・4/18(日)',
      opponent: '対戦相手未定',
      ticket_url: ticketApp,
      enabled: true,
    }),
    row({
      match_id: 'TOP-SAMPLE-001',
      team: 'TOP',
      competition: '明治安田J1リーグ',
      round: '第○節',
      status: '確定',
      confirmed_date: '2027-01-01',
      kickoff: '14:00',
      duration_minutes: 120,
      home_away: 'HOME',
      opponent: '（この行を実際の試合に置換）',
      venue: '味の素スタジアム',
      ticket_url: ticketApp,
      note: '入力例のため無効。実データに置き換えてenabledをTRUEにしてください。',
      enabled: false,
    }),
  ];
}
