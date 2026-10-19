'use strict';
(async function () {
  const form = document.getElementById('history-filters');
  if (!form) return;
  const body = document.getElementById('history-body');
  const count = document.getElementById('history-count');
  const prev = document.getElementById('history-prev');
  const next = document.getElementById('history-next');
  const pageLabel = document.getElementById('history-page');
  const names = {tpbl:'TPBL',plg:'P. LEAGUE+',b:'B.LEAGUE',cba:'CBA'};
  const params = new URLSearchParams(location.search);
  for (const key of ['league','season','date','team','status']) {
    if (params.has(key)) form.elements.namedItem(key).value = params.get(key);
  }
  try {
    const response = await fetch('../data/history.json');
    if (!response.ok) throw new Error('HTTP '+response.status);
    const data = await response.json();
    let page = 0;
    function render() {
      const value = key => form.elements.namedItem(key).value;
      const filtered = data.games.filter(g =>
        (!value('league') || g.league === value('league')) &&
        (!value('season') || g.season === value('season')) &&
        (!value('date') || g.date === value('date')) &&
        (!value('team') || (g.home+' '+g.away).toLocaleLowerCase().includes(value('team').trim().toLocaleLowerCase())) &&
        (!value('status') || (value('status') === 'detail' ? g.detail : value('status') === 'pending' ? g.complete && !g.detail : !g.complete)) &&
        (value('status') || value('date') || g.complete));
      const pages = Math.max(1,Math.ceil(filtered.length/50));
      page = Math.min(page,pages-1);
      body.replaceChildren();
      for (const g of filtered.slice(page*50,(page+1)*50)) {
        const row = document.createElement('tr');
        for (const [i,text] of [g.date,names[g.league]||g.league,g.home+' vs '+g.away,(g.score||[]).filter(x=>x!==null).join('：')||'—',g.status].entries()) {
          const cell = document.createElement(i === 2 ? 'th':'td');
          if (i === 2) {
            cell.scope = 'row';
            const link = document.createElement('a');
            link.textContent = text;
            // Paths are constrained so a data correction cannot inject a URL.
            if (/^games\/[a-z0-9_-]+\/[a-z0-9_.%-]+\.html$/i.test(g.path)) link.href = '../'+g.path;
            cell.append(link);
          } else cell.textContent = text;
          row.append(cell);
        }
        body.append(row);
      }
      count.textContent = `符合 ${filtered.length} 場；已有詳細統計 ${filtered.filter(g=>g.detail).length} 場。每頁50場，缺資料狀態保留。`;
      pageLabel.textContent = `第 ${page+1}／${pages} 頁`;
      prev.hidden = false; next.hidden = false;
      prev.disabled = page === 0; next.disabled = page+1 >= pages;
      const query = new URLSearchParams();
      for (const key of ['league','season','date','team','status']) if (value(key)) query.set(key,value(key));
      history.replaceState(null,'',location.pathname+(query.size?'?'+query:''));
    }
    form.addEventListener('submit',e=>e.preventDefault());
    form.addEventListener('input',()=>{page=0;render();});
    form.addEventListener('reset',()=>setTimeout(()=>{page=0;render();},0));
    prev.addEventListener('click',()=>{page--;render();});
    next.addEventListener('click',()=>{page++;render();});
    render();
  } catch (error) {
    const note = document.getElementById('history-error');
    note.hidden = false;
    note.textContent = '篩選資料暫時無法載入；下方保留已發布的完整靜態賽事列表。';
  }
})();
