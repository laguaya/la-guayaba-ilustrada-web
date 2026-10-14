/* Burbuja de chat que lleva a WhatsApp. Cambia el número aquí si algún día cambia. */
(function(){
  const NUM='527209097907';
  const OPCIONES=[
    'Quiero cotizar un proyecto',
    'Me interesa un plan mensual',
    'Quiero una página web',
    'Tengo otra duda'
  ];
  const css=`
  .lgi-chat{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:90;pointer-events:none;display:flex;flex-direction:column;align-items:flex-end;gap:12px;font-family:"Linear Grotesk","Helvetica Neue",Arial,sans-serif}
  .lgi-bubble{pointer-events:auto;display:inline-flex;align-items:center;gap:10px;height:56px;padding:2px 22px 0 18px;border-radius:999px;background:#000;color:#fff;font-weight:700;font-size:15px;line-height:1;border:0;cursor:pointer;box-shadow:0 14px 30px rgba(255,54,116,.35);transition:transform .25s}
  .lgi-bubble:hover{transform:translateY(-2px)}
  .lgi-bubble svg{width:24px;height:24px;flex:none;margin-top:-2px}
  .lgi-bubble .dot{width:9px;height:9px;border-radius:50%;background:#FF3674;animation:lgiPulse 1.8s ease-in-out infinite}
  @keyframes lgiPulse{0%,100%{box-shadow:0 0 0 0 rgba(255,54,116,.6)}50%{box-shadow:0 0 0 7px rgba(255,54,116,0)}}
  .lgi-panel{width:min(340px,calc(100vw - 32px));background:#fff;border-radius:26px;box-shadow:0 24px 60px rgba(0,0,0,.18);overflow:hidden;opacity:0;transform:translateY(14px) scale(.98);transform-origin:bottom right;pointer-events:none;transition:opacity .3s,transform .4s cubic-bezier(.22,.8,.2,1)}
  .lgi-chat.open .lgi-panel{opacity:1;transform:none;pointer-events:auto}
  .lgi-top{background:#FF3674;color:#000;padding:18px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px}
  .lgi-top b{display:block;font-size:17px;font-weight:900;letter-spacing:-0.02em;line-height:1.1}
  .lgi-top small{font-size:13px}
  .lgi-x{width:36px;height:36px;border-radius:12px;background:#fff;color:#000;border:0;font-size:18px;font-weight:700;line-height:1;cursor:pointer}
  .lgi-body{padding:18px 18px 20px;display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center}
  .lgi-msg{background:#FFEDF2;border-radius:18px;padding:12px 16px;font-size:15px;line-height:1.4;color:#000}
  .lgi-opt{width:100%;border:0;border-radius:14px;background:#000;color:#fff;font:inherit;font-weight:700;font-size:15px;line-height:1.2;padding:15px 16px 13px;cursor:pointer;text-decoration:none;display:block;transition:transform .2s}
  .lgi-opt:hover{transform:translateY(-2px)}
  .lgi-opt.alt{background:#FFEDF2;color:#000}
  .lgi-note{font-size:12.5px;color:#565656}
  .lgi-chat :focus-visible{outline:3px solid #FF5B00;outline-offset:3px}
  @media (max-width:640px){.lgi-bubble{width:56px;padding:0;justify-content:center;font-size:0;gap:0}.lgi-bubble svg{margin:0}}
  @media (prefers-reduced-motion:reduce){.lgi-chat *{animation:none!important;transition:none!important}}`;
  const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);

  const wa=t=>`https://wa.me/${NUM}?text=${encodeURIComponent('Hola, vengo de la página de La Guayaba Ilustrada. '+t)}`;
  const box=document.createElement('div');box.className='lgi-chat';
  box.innerHTML=`
    <div class="lgi-panel" id="lgi-panel" role="dialog" aria-label="Chat por WhatsApp">
      <div class="lgi-top"><span><b>La Guayaba Ilustrada</b><small>Respondemos por WhatsApp</small></span><button type="button" class="lgi-x" aria-label="Cerrar chat">×</button></div>
      <div class="lgi-body">
        <p class="lgi-msg">Hola, soy Sergio. ¿En qué te podemos ayudar?</p>
        ${OPCIONES.map((o,i)=>`<a class="lgi-opt${i===OPCIONES.length-1?' alt':''}" href="${wa(o+'.')}" target="_blank" rel="noopener">${o}</a>`).join('')}
        <span class="lgi-note">Se abrirá WhatsApp con tu mensaje listo.</span>
      </div>
    </div>
    <button type="button" class="lgi-bubble" aria-expanded="false" aria-controls="lgi-panel">
      <svg viewBox="0 0 24 24" fill="#FF3674" aria-hidden="true"><path d="M12 3C6.5 3 2 6.8 2 11.5c0 2.4 1.2 4.6 3.1 6.1L4.4 21l3.9-1.9c1.2.4 2.4.6 3.7.6 5.5 0 10-3.8 10-8.5S17.5 3 12 3z"/></svg>
      Escríbenos
    </button>`;
  document.body.appendChild(box);
  const btn=box.querySelector('.lgi-bubble');
  const set=o=>{box.classList.toggle('open',o);btn.setAttribute('aria-expanded',o)};
  btn.addEventListener('click',()=>set(!box.classList.contains('open')));
  box.querySelector('.lgi-x').addEventListener('click',()=>{set(false);btn.focus()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')set(false)});
})();
