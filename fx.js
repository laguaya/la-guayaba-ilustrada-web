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
  st.textContent='@keyframes lgiShake{0%,100%{translate:0 0;rotate:0deg}20%{translate:-4px 0;rotate:-1.5deg}40%{translate:4px 0;rotate:1.5deg}60%{translate:-3px 0;rotate:-1deg}80%{translate:2px 0;rotate:.6deg}}.lgi-shake{animation:lgiShake .32s ease}.gallery .ph,.lb-media,.lb-media img,.lb-media video{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}';
  document.head.appendChild(st);
  window.shake=function(el){if(!el)return;el.classList.remove('lgi-shake');void el.offsetWidth;el.classList.add('lgi-shake');setTimeout(()=>el.classList.remove('lgi-shake'),340)};
  /* Mantener presionado: explosión de confeti */
  window.longPress=function(el,cb){let t=null,sx=0,sy=0,fired=false;
    const start=e=>{const p=e.touches?e.touches[0]:e;sx=p.clientX;sy=p.clientY;fired=false;clearTimeout(t);t=setTimeout(()=>{fired=true;cb(sx,sy)},650)};
    const move=e=>{const p=e.touches?e.touches[0]:e;if(Math.hypot(p.clientX-sx,p.clientY-sy)>10)clearTimeout(t)};
    const end=()=>clearTimeout(t);
    el.addEventListener('touchstart',start,{passive:true});el.addEventListener('touchmove',move,{passive:true});el.addEventListener('touchend',end);el.addEventListener('touchcancel',end);
    el.addEventListener('mousedown',start);el.addEventListener('mousemove',move);el.addEventListener('mouseup',end);el.addEventListener('mouseleave',end);
    el.addEventListener('contextmenu',e=>e.preventDefault());
    return ()=>fired;};
})();
