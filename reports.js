'use strict';
function reportSection(number,title,method){
  const section=el('div',undefined,'report-section');
  section.append(el('h5',`${number} · ${title}`));
  if(method)section.append(el('p',method,'meta report-method'));
  return section;
}
function reportCard(title,team){
  const card=el('div',undefined,'report-card'),heading=el('div',undefined,'card-heading');
  if(title)heading.append(el('strong',title));
  if(team)heading.append(el('span',team,'team-tag'));
  if(title||team)card.append(heading);
  return card;
}
function primaryPanels(g){
  const container=el('div',undefined,'primary-panels');
  const fallback=i=>g.analysis?.[i]?.[1]||'官方資料不足，暫不判定。';
  const first=reportSection(1,'第四節最後五分鐘的關鍵球員','以該時段得分排序，再依助攻、抄截、阻攻與失誤描述貢獻。');
  if(g.keyPlayers?.length)g.keyPlayers.forEach((p,i)=>{
    const c=reportCard(`#${i+1} ${p.name}`,g[p.side]);
    c.append(el('p',`${p.points} 分`,'metric-highlight'),el('p',`${p.assists} 助攻 · ${p.steals} 抄截 · ${p.blocks} 阻攻 · ${p.turnovers_valid?p.turnovers+' 失誤':'失誤紀錄需核對'}`,'meta'));
    first.append(c);
  });else{const c=reportCard();c.append(el('p',fallback(0)));first.append(c)}
  const second=reportSection(2,'整場最佳／最差五人組合與近三場','至少共同上場四分鐘，依淨得分排序；個人近三場含本場，依實際出賽紀錄呈現。');
  if(g.lineups?.length)for(const x of g.lineups){
    const c=reportCard(x.kind||x.label,x.team);
    c.append(el('p',x.names.join('、'),'lineup-names'));
    if(typeof x.net==='number')c.append(el('p',`淨得分 ${x.net>=0?'+':''}${x.net} · 共同 ${(x.seconds/60).toFixed(1)} 分鐘`,'metric-highlight'));
    const det=el('details');det.open=true;det.append(el('summary','組合球員個人近三場（可收合）'));
    const historyCell=h=>h?`${h.date}：${h.points} 分、${h.turnovers} 失誤、投籃 ${h.fgm}/${h.fga}`:'歷史不足';
    det.append(table('最近三場實際出賽（由近至遠，含本場）',['球員','最近第 1 場','最近第 2 場','最近第 3 場'],x.players.map(p=>[p.name,...[0,1,2].map(i=>historyCell(p.history[i]))])));
    c.append(det);second.append(c);
  }else{const c=reportCard();c.append(el('p',fallback(1)));second.append(c)}
  const third=reportSection(3,'球員特殊變化提示','本場至少十分鐘，與之前三場平均得分相差至少八分；顯示變化最大者。');
  if(g.playerChanges?.length)for(const p of g.playerChanges){
    const c=reportCard(p.name,p.team);
    c.append(el('p',`得分 ${p.delta>0?'增加':'減少'} ${Math.abs(p.delta).toFixed(1)} 分`,'metric-highlight'));
    c.append(el('p',`本場 ${p.points} 分 · 之前三場平均 ${p.average.toFixed(1)} 分`));
    c.append(el('p',`上場 ${p.minutes.toFixed(1)} 分鐘（之前平均 ${p.previousMinutes.toFixed(1)} 分鐘）· 投籃 ${p.fgm}/${p.fga}。變化也可能受上場時間或對手影響。`,'meta'));third.append(c);
  }else{const c=reportCard();c.append(el('p',fallback(2)));third.append(c)}
  container.append(first,second,third);return container;
}
