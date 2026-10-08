const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
async function load(context=true, navigatorFallback=false){
  const registered=[],requests=[];
  const registerTool=async t=>registered.push(t);
  const sandbox={URL,console,document:{currentScript:{src:'https://ttytseng.github.io/asian-basketball/webmcp.js'},querySelectorAll:()=>[],...(context&&!navigatorFallback?{modelContext:{registerTool}}:{})},navigator:context&&navigatorFallback?{modelContext:{registerTool}}:{},fetch:async url=>{
    requests.push(url.href);const relative=url.pathname.replace('/asian-basketball/','');
    const file=path.join(root,relative);return {status:fs.existsSync(file)?200:404,ok:fs.existsSync(file),json:async()=>JSON.parse(fs.readFileSync(file,'utf8'))};
  }};
  vm.runInNewContext(fs.readFileSync(path.join(root,'webmcp.js'),'utf8'),sandbox);await new Promise(resolve=>setImmediate(resolve));
  const call=async(name,input)=>JSON.parse(JSON.stringify(await registered.find(t=>t.name===name).execute(input)));
  return {registered,requests,call};
}
test('registers three read-only tools with schemas and degrades when unavailable',async()=>{
  const {registered}=await load();assert.equal(registered.length,3);
  for(const t of registered){assert.equal(t.annotations.readOnlyHint,true);assert.equal(t.inputSchema.additionalProperties,false)}
  assert.equal((await load(false)).registered.length,0);assert.equal((await load(true,true)).registered.length,3);
});
test('schedule filters actual data by league and date, with source timestamps',async()=>{
  const {call}=await load(),data=JSON.parse(fs.readFileSync(path.join(root,'data/site.json'),'utf8')),l=data.leagues[0];
  const out=await call('get_league_schedule',{league:l.id,scope:'all'});
  assert.equal(out.ok,true);assert.equal(out.total,l.upcoming.length+l.recent.length);assert.equal(out.generatedAt,data.generatedAt);assert.equal(out.source,l.source);
  const when=l.upcoming[0]?.date??l.recent[0].date;const filtered=await call('get_league_schedule',{league:l.id,date:when,scope:'all'});
  assert.ok(filtered.games.every(g=>g.date===when));assert.ok(filtered.games.every(g=>g.league===l.id));
});
test('returns existing date report and game analysis with original official sources',async()=>{
  const {call}=await load(),report=fs.readdirSync(path.join(root,'data/reports')).find(n=>n.endsWith('.json')).slice(0,-5);
  const daily=await call('get_daily_report',{date:report,league:'tpbl'});assert.equal(daily.ok,true);assert.equal(daily.leagues.length,1);assert.equal(daily.leagues[0].id,'tpbl');
  const expected=daily.leagues[0].recent[0];const result=await call('get_game_analysis',{league:'tpbl',game_id:expected.id,report_date:report});
  assert.equal(result.ok,true);assert.equal(result.game.source,expected.source);assert.deepEqual(result.game.analysis,expected.analysis);assert.equal(result.game.pbpSource,expected.pbpSource);
});
test('invalid dates and traversal paths are rejected before any fetch; missing records stay missing',async()=>{
  const {call,requests}=await load();
  for(const date of ['../../private','2026-02-30','2026-13-01','x'])assert.equal((await call('get_daily_report',{date})).error.code,'INVALID_INPUT');
  assert.equal((await call('get_league_schedule',{league:'unknown'})).error.code,'INVALID_INPUT');assert.equal(requests.length,0);
  assert.equal((await call('get_daily_report',{date:'1900-01-01'})).error.code,'NOT_FOUND');
  assert.equal((await call('get_game_analysis',{league:'tpbl',game_id:'nonexistent'})).error.code,'NOT_FOUND');
  assert.ok(requests.every(u=>u.startsWith('https://ttytseng.github.io/asian-basketball/data/')));
});
