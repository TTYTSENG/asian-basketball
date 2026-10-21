/* Local browser audit: set BASKETBALL_AXE_PATH to an installed axe-core file. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
async function main(){
 const root=path.resolve(__dirname,'..'),base=process.env.BASKETBALL_TEST_URL||'http://127.0.0.1:8770/';
 assert.ok(process.env.BASKETBALL_AXE_PATH,'Set BASKETBALL_AXE_PATH');
 const data=JSON.parse(fs.readFileSync(path.join(root,'public/data/history.json'),'utf8'));
 const nbl=data.games.find(g=>g.league==='nbl'&&g.complete);
 const routes=['','history/','analytics/','research/','basketball-analytics-handbook.html',`games/nbl/${nbl.id}.html`];
 const browser=await chromium.launch({headless:true,channel:'chrome'}),results=[];
 try{
  const p=await browser.newPage();
  for(const route of routes){
   const response=await p.goto(base+route);assert.equal(response.status(),200,route);
   for(const theme of ['standard','high','dark']){
    await p.selectOption('#contrast',theme);
    await p.addScriptTag({path:process.env.BASKETBALL_AXE_PATH});
    const result=await p.evaluate(async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),incomplete:r.incomplete.length,version:r.testEngine.version};});
    results.push({route,theme,...result});
   }
   await p.selectOption('#contrast','standard');await p.selectOption('#font-size','200');
   await p.setViewportSize({width:320,height:800});
   assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Reflow '+route);
   await p.selectOption('#font-size','100');await p.setViewportSize({width:1440,height:900});
  }
  await p.goto(base);await p.keyboard.press('Tab');await p.keyboard.press('Enter');
  assert.equal(await p.evaluate(()=>document.activeElement.id),'main','Skip link focus');
  fs.writeFileSync(path.join(root,'.cache/accessibility-final.json'),JSON.stringify(results,null,2));
  const violations=results.flatMap(r=>r.violations.map(v=>({route:r.route,theme:r.theme,...v})));
  assert.deepEqual(violations,[]);
  console.log(JSON.stringify({pages:routes.length,themes:3,axeVersion:results[0].version,violations:0,reflow:'320px / 200%',manualReviewRequired:true}));
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
