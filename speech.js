'use strict';
(()=>{
  const start=document.getElementById('read-start'),pause=document.getElementById('read-pause'),stop=document.getElementById('read-stop'),status=document.getElementById('speech-status');
  const synth=window.speechSynthesis;
  if(!synth||typeof window.SpeechSynthesisUtterance!=='function'){
    start.disabled=true;status.textContent='此瀏覽器不支援朗讀';return;
  }
  let state='idle',generation=0,queue=[],current=null,lastSection=null;
  function controls(message){start.disabled=state!=='idle';pause.disabled=stop.disabled=state==='idle';pause.textContent=state==='paused'?'繼續':'暫停';pause.setAttribute('aria-pressed',String(state==='paused'));status.textContent=message}
  function finish(message){const restoreFocus=document.activeElement===pause||document.activeElement===stop;generation++;state='idle';queue=[];current=null;synth.cancel();controls(message);if(restoreFocus)start.focus({preventScroll:true})}
  document.getElementById('main').addEventListener('focusin',e=>{lastSection=e.target.closest('main>section')});
  function next(token){
    if(token!==generation||state==='idle')return;
    if(state==='paused')return;
    if(!queue.length){finish('朗讀完成');return}
    current=new SpeechSynthesisUtterance(queue.shift());current.lang='zh-TW';
    const voices=synth.getVoices();
    current.voice=voices.find(v=>/^zh[-_]TW$/i.test(v.lang)&&v.localService)||voices.find(v=>/^zh[-_]TW$/i.test(v.lang))||voices.find(v=>/^zh/i.test(v.lang))||null;
    current.onend=()=>{if(token!==generation)return;current=null;next(token)};
    current.onerror=e=>{if(token===generation)finish(e.error==='not-allowed'?'朗讀未獲瀏覽器允許，請再按朗讀。':'朗讀無法播放，請確認裝置語音設定。')};
    try{synth.speak(current)}catch{finish('朗讀無法播放，請確認裝置語音設定。')}
  }
  start.addEventListener('click',()=>{
    const selection=window.getSelection(),selected=selection?.toString().trim();
    let text,label;
    if(selected&&document.getElementById('main').contains(selection.anchorNode)&&document.getElementById('main').contains(selection.focusNode)){
      text=selected;label='選取文字';
    }else{
      const hash=document.getElementById(location.hash.slice(1));
      const target=hash?.matches('main section')?hash:lastSection||document.getElementById('main');
      // innerText includes visible content only; explicitly omit collapsed detail bodies.
      const clone=target.cloneNode(true);
      clone.querySelectorAll('[hidden],.sr-only,script,noscript').forEach(n=>n.remove());
      clone.querySelectorAll('details:not([open])').forEach(n=>n.replaceChildren(n.querySelector('summary')));
      clone.style.position='fixed';clone.style.left='-100000px';clone.style.width=target.clientWidth+'px';clone.setAttribute('aria-hidden','true');document.body.append(clone);
      text=clone.innerText;clone.remove();
      label=target.querySelector('h2')?.textContent||'主要內容';
    }
    if(!text?.trim()){status.textContent='目前沒有可朗讀文字';return}
    // Bounded utterances prevent long reports from becoming one uninterruptible sentence.
    queue=text.replace(/\s+/g,' ').match(/[\s\S]{1,120}(?:[。！？；]|$)|[\s\S]{1,120}/g)||[];
    const moveFocus=document.activeElement===start;
    generation++;synth.cancel();synth.resume();state='speaking';controls('朗讀：'+label);if(moveFocus)pause.focus({preventScroll:true});next(generation);
  });
  pause.addEventListener('click',()=>{
    if(state==='speaking'){state='paused';synth.pause();controls('已暫停朗讀')}
    else if(state==='paused'){state='speaking';synth.resume();controls('繼續朗讀');if(!current)next(generation)}
  });
  stop.addEventListener('click',()=>finish('已停止朗讀'));
  window.addEventListener('hashchange',()=>{if(state!=='idle')finish('切換區塊，已停止朗讀')});
  window.addEventListener('pagehide',()=>finish('已停止朗讀'));
})();
