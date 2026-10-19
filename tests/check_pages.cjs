/* Browser regression checks for the published static artifact. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {chromium}=require('playwright');

async function main(){
 const root=path.resolve(__dirname,'../public');
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  let relative=decodeURIComponent(url.pathname).replace(/^\/asian-basketball\//,'').replace(/^\//,'');
  let file=path.resolve(root,relative);
  if(!file.startsWith(root+path.sep)&&file!==root){res.writeHead(403).end();return;}
  if(fs.existsSync(file)&&fs.statSync(file).isDirectory())file=path.join(file,'index.html');
  if(!fs.existsSync(file)){res.writeHead(404).end('Not found');return;}
  const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png'};
  res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port,base=`http://127.0.0.1:${port}/asian-basketball/`;
 let browser;
 try{
  browser=await chromium.launch({headless:true,channel:process.env.BASKETBALL_TEST_BROWSER||undefined});
  const context=await browser.newContext();
  const p=await context.newPage();const errors=[];p.on('pageerror',e=>errors.push(String(e)));
  const data=JSON.parse(fs.readFileSync(path.join(root,'data/history.json'),'utf8'));
  const dateCounts=new Map();
  for(const g of data.games.filter(g=>g.league==='b'&&g.complete))dateCounts.set(g.date,(dateCounts.get(g.date)||0)+1);
  const bigDay=[...dateCounts].sort((a,b)=>b[1]-a[1])[0];
  assert.ok(bigDay&&bigDay[1]>5,'Need a real B.LEAGUE matchday with more than five stored games');
  await p.goto(base+'history/?league=b&date='+bigDay[0]);
  await p.waitForFunction(()=>document.querySelector('#history-page').textContent.includes('頁'));
  const rows=await p.locator('#history-body tr').count();
  assert.equal(rows,bigDay[1],'No same-day game may disappear from the filtered list');
  const first=await p.locator('#history-body a').first().getAttribute('href');
  await p.locator('#history-body a').first().click();await p.waitForLoadState();
  assert.ok((await p.locator('h1').textContent()).includes(' vs '));
  assert.equal(await p.locator('h2').filter({hasText:'進階觀戰數據'}).count(),1);
  assert.equal(await p.locator('#font-size').count(),1);
  await p.selectOption('#font-size','150');
  assert.equal(await p.evaluate(()=>document.documentElement.style.fontSize),'150%');
  await p.goto(base+'research/');assert.equal(await p.locator('.article-list > li').count(),14);
  await p.locator('.article-list a').first().click();
  assert.ok((await p.locator('main').innerText()).includes('原文來源'));
  await p.goto(base+'analytics/');assert.equal(await p.locator('.article-list > li').count(),6);
  await p.goto(base);await p.waitForFunction(()=>document.querySelector('#updated').textContent.includes('更新嘗試'));
  assert.equal(await p.locator('#analysis-content table').count(),0,'Homepage must only list reports');
  assert.equal(await p.locator('#analysis-content .article-list').count(),4);
  await p.setViewportSize({width:390,height:844});
  await p.goto(base+'history/?league=b&date='+bigDay[0]);
  await p.waitForFunction(()=>document.querySelector('#history-page').textContent.includes('頁'));
  assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'Mobile page must not overflow horizontally');
  await p.screenshot({path:path.resolve(__dirname,'../.cache/history-mobile.png'),fullPage:true});
  await p.setViewportSize({width:1440,height:1000});
  await p.goto(base+first.replace('../',''));await p.screenshot({path:path.resolve(__dirname,'../.cache/game-desktop.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  const nojs=await browser.newContext({javaScriptEnabled:false});
  const q=await nojs.newPage();await q.goto(base+'history/');
  const staticCount=await q.locator('#history-body tr').count();
  assert.equal(staticCount,data.games.filter(g=>g.complete).length);
  await nojs.close();
  console.log(JSON.stringify({passed:true,historyGames:data.games.length,largeMatchday:bigDay[0],gamesOnDay:rows,staticCompleted:staticCount,researchArticles:14,methods:6,browserErrors:errors.length}));
 }finally{if(browser)await browser.close();server.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
