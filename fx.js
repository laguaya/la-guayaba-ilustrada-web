/* Sensaciones al tocar el portafolio: vibración del teléfono, temblor y confeti rosa */
(function(){
  /* Vibración. Android usa navigator.vibrate. En iPhone (iOS 18 o más reciente) Safari no permite
     vibrar desde una página, salvo al activar un interruptor; usamos uno invisible para lograr el pulso. */
  let sw=null;
  function ensureSwitch(){if(sw)return sw;const l=document.createElement('label');l.setAttribute('aria-hidden','true');l.style.cssText='position:fixed;left:-9999px;top:0;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none';const i=document.createElement('input');i.type='checkbox';i.setAttribute('switch','');i.tabIndex=-1;l.appendChild(i);document.body.appendChild(l);sw=l;return l}
  window.haptic=function(kind){
    try{if(navigator.vibrate){navigator.vibrate(kind==='boom'?[18,40,28,40,60]:12);return}}catch(e){}
    try{const l=ensureSwitch();l.click();if(kind==='boom'){setTimeout(()=>l.click(),90);setTimeout(()=>l.click(),190)}}catch(e){}
  };
  /* Confeti rosa */
  const cols=['#FF3674','#FF6489','#FFA4BE','#FFEDF2','#FF5B00','#FF9D00'];
  window.confetti=function(x,y){
    if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    const c=document.createElement('canvas'),d=devicePixelRatio||1;c.width=innerWidth*d;c.height=innerHeight*d;
    c.style.cssText='position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:200';document.body.appendChild(c);
    const g=c.getContext('2d');g.scale(d,d);
    const P=[];for(let i=0;i<110;i++){const a=Math.random()*Math.PI*2,v=4+Math.random()*9;P.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v-5,w:6+Math.random()*7,h:4+Math.random()*5,r:Math.random()*6,vr:(Math.random()-.5)*.4,c:cols[i%cols.length],s:Math.random()<.35})}
    const ring={r:0,o:.9};let t0=performance.now();
    (function f(t){const dt=Math.max(0,Math.min(2,(t-t0)/16.7));t0=t;g.clearRect(0,0,innerWidth,innerHeight);
      if(ring.o>0&&dt>0){ring.r+=14*dt;ring.o-=.05*dt;g.beginPath();g.arc(x,y,ring.r,0,7);g.strokeStyle=`rgba(255,54,116,${Math.max(0,ring.o)})`;g.lineWidth=6;g.stroke()}
      let alive=0;for(const p of P){p.vy+=.28*dt;p.vx*=.99;p.x+=p.vx*dt;p.y+=p.vy*dt;p.r+=p.vr*dt;if(p.y<innerHeight+30){alive++;g.save();g.translate(p.x,p.y);g.rotate(p.r);g.fillStyle=p.c;if(p.s){g.beginPath();g.arc(0,0,Math.abs(p.w/2),0,7);g.fill()}else g.fillRect(-p.w/2,-p.h/2,p.w,p.h);g.restore()}}
      if(alive)requestAnimationFrame(f);else c.remove()})(t0);
  };
  /* Temblor */
  const st=document.createElement('style');
  st.textContent='@keyframes lgiShake{0%,100%{translate:0 0;rotate:0deg}20%{translate:-4px 0;rotate:-1.5deg}40%{translate:4px 0;rotate:1.5deg}60%{translate:-3px 0;rotate:-1deg}80%{translate:2px 0;rotate:.6deg}}.lgi-shake{animation:lgiShake .32s ease}.lb-media img,.lb-media video{clip-path:inset(0 round 18px)}.gallery .ph{clip-path:inset(0 round 20px)}.gallery .ph,.lb-media,.lb-media img,.lb-media video{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}';
  document.head.appendChild(st);
  window.shake=function(el){if(!el)return;el.classList.remove('lgi-shake');void el.offsetWidth;el.classList.add('lgi-shake');setTimeout(()=>el.classList.remove('lgi-shake'),340)};
  /* Carga de energía: tiembla cada vez más fuerte, crece un poco y al final explota */
  const CHARGE=1600;
  window.charge=function(getEl,done){
    let raf=0,t0=performance.now(),stop=false,lastTick=0;const el0=getEl();
    try{if(navigator.vibrate){const pat=[];let gap=150;for(let t=0;t<CHARGE;){pat.push(14,gap);t+=14+gap;gap=Math.max(30,gap*0.8)}navigator.vibrate(pat)}}catch(e){}
    (function f(t){if(stop)return;const el=getEl();const k=Math.min(1,(t-t0)/CHARGE),amp=0.6+k*k*6;
      if(el){el.style.translate=`${(Math.random()-.5)*amp*2}px ${(Math.random()-.5)*amp}px`;el.style.rotate=`${(Math.random()-.5)*amp*0.5}deg`;el.style.scale=String(1+k*0.06);el.style.filter=`brightness(${1+k*0.25})`}
      if(!navigator.vibrate&&t-lastTick>Math.max(70,260*(1-k))){lastTick=t;haptic()}
      if(k<1)raf=requestAnimationFrame(f);else{reset(el,true);done()}})(t0);
    function reset(el,pop){if(!el)return;el.style.translate='';el.style.rotate='';el.style.filter='';
      el.style.transition='scale .45s cubic-bezier(.34,1.8,.64,1)';el.style.scale=pop?'1.12':'1';setTimeout(()=>{el.style.scale='1';setTimeout(()=>{el.style.transition='';el.style.scale=''},460)},pop?120:0)}
    return function cancel(){if(stop)return;stop=true;cancelAnimationFrame(raf);try{navigator.vibrate&&navigator.vibrate(0)}catch(e){}reset(getEl(),false)};
  };
  /* Mantener presionado: empieza a cargar y, si no sueltas, explota en confeti */
  window.longPress=function(el,getTarget,cb){let t=null,sx=0,sy=0,fired=false,cancel=null;
    const stopAll=()=>{clearTimeout(t);if(cancel){cancel();cancel=null}};
    const start=e=>{const p=e.touches?e.touches[0]:e;sx=p.clientX;sy=p.clientY;fired=false;stopAll();
      t=setTimeout(()=>{cancel=charge(getTarget,()=>{cancel=null;fired=true;cb(sx,sy)})},260)};
    const move=e=>{const p=e.touches?e.touches[0]:e;if(Math.hypot(p.clientX-sx,p.clientY-sy)>10)stopAll()};
    el.addEventListener('touchstart',start,{passive:true});el.addEventListener('touchmove',move,{passive:true});el.addEventListener('touchend',stopAll);el.addEventListener('touchcancel',stopAll);
    el.addEventListener('mousedown',start);el.addEventListener('mousemove',move);el.addEventListener('mouseup',stopAll);el.addEventListener('mouseleave',stopAll);
    el.addEventListener('contextmenu',e=>e.preventDefault());
    return ()=>fired;};
})();
