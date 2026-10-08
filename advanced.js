'use strict';
const SHOW_TRACKING_METRICS=false;
const metricNumber=x=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(1):'資料不足';
function advancedPanel(g){const a=g.advanced,d=el('div',undefined,'advanced-panel');const atoSection=reportSection(4,'ATO 暫停後進攻與防守','暫停後首個可辨識完整回合，以得分與失誤評估結果。');const atoCard=reportCard();atoSection.append(atoCard);d.append(atoSection);let target=atoCard;
if(!a){target.append(el('p','進階資料尚未取得，待下次官方更新。','no-data'));return d}
const ato=a.ato;target.append(el('p',`ATO：記錄 ${ato.total} 次暫停，${ato.total-ato.excluded} 個回合可辨識，排除 ${ato.excluded} 個不完整回合。`,'meta'));
const rate=(n,total)=>total?`${(100*n/total).toFixed(1)}%（${n}/${total}）`:'無可用樣本';
target.append(table('ATO 暫停後首個可辨識回合',['球隊','進攻得分成功率','防守阻止得分成功率','進攻得分／失誤'],ato.summary.map(x=>[g[x.side],rate(x.attack_success,x.attack_n),rate(x.defense_success,x.defense_n),`${x.points} 分／${x.turnovers} 次失誤`])));
target.append(el('p','本站口徑：得分即進攻成功，未得分即防守成功；進攻籃板延續回合。罰球先出現、回合缺漏或驗證失敗的紀錄不納入成功率。防守成功不等同於一次抄截，也不能單憑此判定戰術效果。','meta'));
const names=new Map(a.players.map(p=>[p.id,p.name]));if(ato.records.length){const details=el('details');details.append(el('summary','ATO 回合紀錄與參與球員'));details.append(table('ATO 回合明細',['暫停時點','進攻方','發球者／接球者','終結者','結果'],ato.records.map(x=>[`Q${x.period} ${Math.floor(x.timeout_sec/60)}:${String(x.timeout_sec%60).padStart(2,'0')}`,x.offense?g[x.offense]:'未辨識',`${x.inbounder?names.get(x.inbounder)||x.inbounder:'未提供'}／${x.receiver?names.get(x.receiver)||x.receiver:'未提供'}`,x.finisher?names.get(x.finisher)||x.finisher:'未辨識',x.eligible?`${x.points} 分、${x.turnovers} 失誤`:x.exclusion])));target.append(details)}
const b=a.benchmark;const usgSection=reportSection(5,'USG% 使用率與表現比較','使用率估計與本場 EFF 最佳球員比較。');target=reportCard();usgSection.append(target);d.append(usgSection);target.append(el('p',b?`比較基準：${b.name}（${g[b.side]}），本場 EFF ${metricNumber(b.eff)}、USG ${metricNumber(b.usg)}%。`:'尚無足夠正式統計建立比較基準。'));target.append(el('p',a.benchmark_method,'meta'));
const details=el('details');details.append(el('summary','展開全隊 USG、助攻與助攻失誤比'));details.append(table('個人使用率與組織基本指標',['球員／球隊','上場分鐘','USG%（估計）','與基準差（百分點）','EFF','助攻／失誤','AST/TO'],a.players.map(p=>[p.name+'／'+g[p.side],(p.seconds/60).toFixed(1)+(p.seconds<600?'（小樣本）':''),metricNumber(p.usg),typeof p.usg==='number'&&typeof b?.usg==='number'?(p.usg-b.usg).toFixed(1):'資料不足',metricNumber(p.eff),`${p.assists??'—'}／${p.turnovers}`,p.turnovers===0?'零失誤，不計比值':metricNumber(p.ast_to)])));target.append(details);
target.append(el('p','USG 為傳統 box-score 估計：100 × (FGA + 0.44 × FTA + TOV) × (球隊總上場秒數 ÷ 5) ÷ [個人上場秒數 × (球隊 FGA + 0.44 × FTA + TOV)]。使用率不是效率；短上場時間的估計可能大幅波動。','meta'));
if(SHOW_TRACKING_METRICS){
const passingSection=reportSection(6,'Playmaking & Passing 傳球與組織','超越助攻次數的傳球追蹤指標。');target=reportCard();passingSection.append(target);d.append(passingSection);target.append(table('進階傳球追蹤資料可用性',['指標','目前狀態'],[['Potential Assists 潛在助攻','缺少傳球與出手連結'],['Passes Made / Received 傳出／接球次數','缺少完整傳球追蹤'],['Secondary Assists 次級助攻','缺少連續傳球鏈']]));target.append(el('p',a.tracking_status,'meta'));
const vorpSection=reportSection(7,'VORP 替換球員價值','依聯盟適用的模型與替補基準評估。');target=reportCard();vorpSection.append(target);d.append(vorpSection);target.append(el('p',a.vorp_status,'meta'));
}return d}
