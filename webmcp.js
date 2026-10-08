/* Read-only queries over the existing public official-data snapshots. */
(() => {
  'use strict';
  const context = document.modelContext ?? navigator.modelContext;
  if (typeof context?.registerTool !== 'function') return;
  const root = new URL('.', document.currentScript.src);
  const leagueIds = ['tpbl', 'plg', 'b'];
  const leagueSchema = {type: 'string', enum: leagueIds, description: 'tpbl = TPBL；plg = P. LEAGUE+；b = 日本 B.LEAGUE'};
  const dateSchema = {type: 'string', pattern: '^\\d{4}-\\d{2}-\\d{2}$', description: '臺北日期 YYYY-MM-DD'};
  const limitation = '本站整理官方公開資料，並非即時比分。請核對來源時間與官方紀錄；分析及重建統計包含資料限制。';
  const fail = (code, message) => ({ok: false, error: {code, message}});
  function date(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value + 'T00:00:00Z')) || new Date(value + 'T00:00:00Z').toISOString().slice(0,10) !== value) throw Error('INVALID_DATE');
    return value;
  }
  function league(value, optional = false) { if (!(optional && value === undefined) && !leagueIds.includes(value)) throw Error('INVALID_LEAGUE'); return value; }
  async function read(path) {
    const response = await fetch(new URL(path, root), {cache: 'no-cache'});
    if (response.status === 404) return null;
    if (!response.ok) throw Error('DATA_UNAVAILABLE');
    const data = await response.json();
    if (!Array.isArray(data.leagues)) throw Error('DATA_UNAVAILABLE');
    return data;
  }
  const game = g => ({id: String(g.id), league: g.league, date: g.date, time: g.time ?? null, home: g.home, away: g.away, score: g.score, complete: g.complete, source: g.source, statsSource: g.statsSource ?? null, pbpSource: g.pbpSource ?? null});
  const analysis = g => ({...game(g), stats: g.stats ?? null, analysis: g.analysis ?? [], keyPlayers: g.keyPlayers ?? [], lineups: g.lineups ?? [], playerChanges: g.playerChanges ?? [], advanced: g.advanced ?? null, quality: g.quality ?? null, clockCorrections: g.clockCorrections ?? null, identityCorrections: g.identityCorrections ?? null});
  function tool(name, description, properties, required, execute) {
    return {name, description, inputSchema: {type: 'object', properties, required, additionalProperties: false}, annotations: {readOnlyHint: true}, execute: async input => {
      try { return await execute(input ?? {}); }
      catch (error) { return fail(error.message.startsWith('INVALID_') ? 'INVALID_INPUT' : 'DATA_UNAVAILABLE', error.message.startsWith('INVALID_') ? '請提供有效的聯盟代碼、日期或比賽 ID。' : '公開資料暫時無法讀取，請稍後重試。'); }
    }};
  }
  const tools = [
    tool('get_league_schedule', '查詢指定聯盟最新公開快照中的未來賽程或最近賽果，可依臺北日期篩選。回傳比賽 ID、比分、官方來源及擷取時間；不是即時或完整歷史賽程。', {league: leagueSchema, date: dateSchema, scope: {type: 'string', enum: ['upcoming', 'recent', 'all'], default: 'upcoming'}}, ['league'], async input => {
      const id = league(input.league), when = input.date === undefined ? undefined : date(input.date), scope = input.scope ?? 'upcoming';
      if (!['upcoming', 'recent', 'all'].includes(scope)) throw Error('INVALID_SCOPE');
      const data = await read('data/site.json'); if (!data) return fail('NOT_FOUND', '目前沒有公開資料快照。');
      const l = data.leagues.find(l => l.id === id); if (!l) return fail('NOT_FOUND', '快照內沒有此聯盟。');
      const selected = scope === 'all' ? [...(l.upcoming ?? []), ...(l.recent ?? [])] : (l[scope] ?? []);
      const matches = selected.filter(g => when === undefined || g.date === when);
      return {ok: true, league: id, leagueName: l.name, scope, date: when ?? null, generatedAt: data.generatedAt, lastSuccess: l.lastSuccess ?? null, sourceIssue: l.error ?? null, source: l.source, timezone: 'Asia/Taipei', total: matches.length, games: matches.map(game), limitation};
    }),
    tool('get_daily_report', '讀取指定臺北日期的已發布日報快照，包含賽程、賽後分析、官方新聞及來源，可限定聯盟。未存檔的日期回傳 NOT_FOUND，不會推測或生成比賽資料。', {date: dateSchema, league: leagueSchema}, ['date'], async input => {
      const when = date(input.date), id = league(input.league, true);
      const data = await read('data/reports/' + when + '.json'); if (!data) return fail('NOT_FOUND', '此日期沒有已發布的日報。');
      const selected = data.leagues.filter(l => id === undefined || l.id === id);
      return {ok: true, date: when, generatedAt: data.generatedAt, url: new URL('reports/' + when + '.html', root).href, timezone: 'Asia/Taipei', sourceIssues: data.errors ?? [], leagues: selected.map(l => ({id: l.id, name: l.name, source: l.source, lastSuccess: l.lastSuccess ?? null, sourceIssue: l.error ?? null, upcoming: (l.upcoming ?? []).map(game), recent: (l.recent ?? []).map(analysis)})), news: data.news ?? [], limitation};
    }),
    tool('get_game_analysis', '依聯盟及比賽 ID 取得已驗證的賽後分析、原始比分、數據品質限制與官方賽事／逐球來源。預設查最新最近賽果；report_date 可查指定日期保存的日報快照。', {league: leagueSchema, game_id: {type: 'string', minLength: 1, maxLength: 100}, report_date: dateSchema}, ['league', 'game_id'], async input => {
      const id = league(input.league);
      if (typeof input.game_id !== 'string' || !input.game_id.trim() || input.game_id.length > 100) throw Error('INVALID_GAME_ID');
      const when = input.report_date === undefined ? undefined : date(input.report_date);
      const data = await read(when ? 'data/reports/' + when + '.json' : 'data/site.json'); if (!data) return fail('NOT_FOUND', '找不到指定資料快照。');
      const l = data.leagues.find(l => l.id === id), g = (l?.recent ?? []).find(g => String(g.id) === input.game_id.trim());
      return g ? {ok: true, generatedAt: data.generatedAt, lastSuccess: l.lastSuccess ?? null, sourceIssue: l.error ?? null, reportDate: when ?? null, game: analysis(g), limitation} : fail('NOT_FOUND', '此快照沒有該比賽的賽後分析。請先查最近賽果取得 ID。');
    })
  ];
  (async () => {
    for (const item of tools) await context.registerTool(item);
    document.querySelectorAll('[data-webmcp-status]').forEach(el => {el.textContent = '已提供 3 個唯讀 AI 查詢工具：聯盟賽程、日期日報與比賽分析。';});
  })().catch(() => console.warn('Basketball site tools registration unavailable.'));
})();
