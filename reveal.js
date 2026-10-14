/* Aparición suave de los elementos al bajar por la página */
(function(){
  if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const st=document.createElement('style');
  st.textContent='.rv{opacity:0;translate:0 28px;transition:opacity .9s cubic-bezier(.22,.8,.2,1) var(--rvd,0ms),translate .9s cubic-bezier(.22,.8,.2,1) var(--rvd,0ms)}.rv.in{opacity:1;translate:0 0}';
  document.head.appendChild(st);
  const sel=window.REVEAL||'';
  const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{rootMargin:'0px 0px -6% 0px',threshold:0});
  function scan(){
    const els=[...document.querySelectorAll(sel)].filter(el=>!el.classList.contains('rv'));
    const groups=new Map();
    els.forEach(el=>{const p=el.parentElement;const n=groups.get(p)||0;groups.set(p,n+1);el.style.setProperty('--rvd',Math.min(n,6)*90+'ms');el.classList.add('rv');io.observe(el)});
  }
  window.revealScan=scan;scan();
  /* al llegar al final, mostrar lo que quede */
  addEventListener('scroll',()=>{if(innerHeight+scrollY>=document.documentElement.scrollHeight-6)document.querySelectorAll('.rv:not(.in)').forEach(e=>{if(e.offsetParent){e.classList.add('in');io.unobserve(e)}})},{passive:true});
  /* elementos que se dibujan después (notas del blog, filtros) */
  new MutationObserver(()=>scan()).observe(document.body,{childList:true,subtree:true});
})();
