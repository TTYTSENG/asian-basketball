'use strict';
(()=>{const font=document.getElementById('font-size'),contrast=document.getElementById('contrast'),status=document.getElementById('reading-status');
const themes={standard:'標準配色',high:'高對比黑字白底',dark:'深色白字黑底'};const allowed=['100','125','150','175','200'];
function apply(save=true){if(!allowed.includes(font.value))font.value='100';if(!themes[contrast.value])contrast.value='standard';document.documentElement.style.fontSize=font.value+'%';document.documentElement.dataset.theme=contrast.value;status.textContent='字體 '+font.value+'%，'+themes[contrast.value]+'。';if(save){try{localStorage.setItem('basketball-reading',JSON.stringify({font:font.value,contrast:contrast.value}))}catch{status.textContent+=' 瀏覽器未允許保存設定。'}}}
try{const saved=JSON.parse(localStorage.getItem('basketball-reading')||'null');if(saved){font.value=allowed.includes(saved.font)?saved.font:'100';contrast.value=themes[saved.contrast]?saved.contrast:'standard'}}catch{}
font.addEventListener('change',()=>apply());contrast.addEventListener('change',()=>apply());document.getElementById('reset-reading').addEventListener('click',()=>{font.value='100';contrast.value='standard';apply()});apply(false);
// An in-page navigation must move focus as well as the viewport.
document.addEventListener('click',event=>{
 const anchor=event.target.closest('a[href^="#"]');
 if(!anchor||event.defaultPrevented||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
 const destination=document.getElementById(anchor.hash.slice(1));
 if(!destination)return;
 if(!destination.hasAttribute('tabindex'))destination.tabIndex=-1;
 destination.focus({preventScroll:true});
});
})();
