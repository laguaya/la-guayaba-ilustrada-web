// Publica un reel en Instagram (@guayabailustrada) y en la Página de Facebook La Guayaba Ilustrada.
// Uso (solo el dueño): /api/publicar?clave=<IG_VERIFY>&id=<nombre>&video=<url pública del mp4>
//   1a llamada: sube el video a los dos lados.
//   Siguientes llamadas: revisan si Instagram terminó de procesarlo y lo publican. Nunca publica dos veces.
// El texto de cada publicación está en COPYS. Usa el token de IG_DM_TOKEN (usuario del sistema Guayaba Bot).

const API = 'https://graph.facebook.com/v21.0';
const IG_ID = '17841448502239351';
const PAGINA = '103453035328282';

const COPYS = {
  'historia-edicion': `La edición de video cambió para siempre. 🎬

De los primeros cortes en película a la inteligencia artificial: la historia de la edición, contada en menos de minuto y medio.

Este video lo hice con mi skill para Claude "Video estilo collage LGI". Le das un guion y una voz en off, y te entrega el mini documental listo, con este mismo estilo.

👉 Comenta EDICIÓN y te mando la skill gratis por mensaje.

#EdicionDeVideo #ClaudeAI #InteligenciaArtificial #MotionGraphics #EditorDeVideo #IA #ContenidoDigital #CreadoresDeContenido #HistoriaDelCine #LaGuayabaIlustrada`,
};

const json = (d, s = 200) => new Response(JSON.stringify(d, null, 2), { status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

async function tokenPagina(env) {
  const r = await fetch(`${API}/${PAGINA}?fields=access_token&access_token=${encodeURIComponent(env.IG_DM_TOKEN || '')}`);
  const j = await r.json().catch(() => ({}));
  return j.access_token || '';
}

async function g(ruta, t, metodo = 'GET', cuerpo) {
  try {
    const r = await fetch(`${API}/${ruta}`, {
      method: metodo,
      headers: { authorization: `Bearer ${t}`, 'content-type': 'application/json' },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
    return await r.json();
  } catch (e) { return { error: { message: String(e) } }; }
}

const err = j => (j && j.error && j.error.message) || null;

export async function onRequestGet({ request, env }) {
  const q = new URL(request.url).searchParams;
  if (!env.IG_VERIFY || q.get('clave') !== env.IG_VERIFY) return new Response('no', { status: 403 });
  const id = q.get('id') || '';
  const copy = COPYS[id];
  if (!copy) return json({ error: 'id desconocido' }, 400);
  const kv = env.RECURSOS;
  if (!kv) return json({ error: 'sin KV' }, 500);
  const k = `pub:${id}`;
  const est = JSON.parse((await kv.get(k)) || '{}');
  const t = await tokenPagina(env);
  if (!t) return json({ error: 'no hay token de página' }, 500);
  const video = q.get('video') || est.video;

  // ---------- Instagram ----------
  if (!est.ig_post) {
    if (!est.ig_cont) {
      if (!video) return json({ error: 'falta video' }, 400);
      const c = await g(`${IG_ID}/media`, t, 'POST', { media_type: 'REELS', video_url: video, caption: copy, share_to_feed: true, thumb_offset: Number(q.get('seg') || 3) * 1000 });
      if (c.id) est.ig_cont = c.id; else est.ig_error = err(c);
    } else {
      const s = await g(`${est.ig_cont}?fields=status_code,status`, t);
      est.ig_estado = s.status_code || err(s);
      if (s.status_code === 'FINISHED') {
        const p = await g(`${IG_ID}/media_publish`, t, 'POST', { creation_id: est.ig_cont });
        if (p.id) {
          est.ig_post = p.id;
          const l = await g(`${p.id}?fields=permalink`, t);
          est.ig_link = l.permalink || null;
        } else est.ig_error = err(p);
      } else if (s.status_code === 'ERROR') { est.ig_error = s.status || 'error al procesar'; delete est.ig_cont; }
    }
  }

  // ---------- Facebook (Reel de la Página) ----------
  if (!est.fb_post && video) {
    if (!est.fb_vid) {
      const a = await g(`${PAGINA}/video_reels`, t, 'POST', { upload_phase: 'start' });
      if (a.video_id && a.upload_url) {
        try {
          const u = await fetch(a.upload_url, { method: 'POST', headers: { authorization: `OAuth ${t}`, file_url: video } });
          const uj = await u.json().catch(() => ({}));
          if (uj.success) est.fb_vid = a.video_id; else est.fb_error = err(uj) || 'no se pudo subir';
        } catch (e) { est.fb_error = String(e); }
      } else est.fb_error = err(a);
    }
    if (est.fb_vid && !est.fb_fin) {
      const f = await g(`${PAGINA}/video_reels`, t, 'POST', { upload_phase: 'finish', video_id: est.fb_vid, video_state: 'PUBLISHED', description: copy });
      if (f.success) est.fb_fin = true; else est.fb_error = err(f);
    }
    if (est.fb_fin) {
      const s = await g(`${est.fb_vid}?fields=status,permalink_url`, t);
      est.fb_estado = (s.status && (s.status.publishing_phase?.status || s.status.video_status)) || err(s);
      if (s.permalink_url) est.fb_link = `https://www.facebook.com${s.permalink_url}`;
      if (s.status && s.status.video_status === 'ready' && s.status.publishing_phase?.status === 'complete') est.fb_post = est.fb_vid;
    }
  }

  // ---------- Portada del Reel de Facebook: &portada=<url de una imagen jpg> ----------
  const portada = q.get('portada');
  if (portada && est.fb_vid && est.fb_portada !== portada) {
    try {
      const img = await fetch(portada);
      const fd = new FormData();
      fd.append('source', new Blob([await img.arrayBuffer()], { type: 'image/jpeg' }), 'portada.jpg');
      fd.append('is_preferred', 'true');
      const r = await fetch(`${API}/${est.fb_vid}/thumbnails`, { method: 'POST', headers: { authorization: `Bearer ${t}` }, body: fd });
      const j = await r.json().catch(() => ({}));
      if (j.success || j.id) { est.fb_portada = portada; delete est.fb_portada_error; } else est.fb_portada_error = err(j) || JSON.stringify(j).slice(0, 200);
    } catch (e) { est.fb_portada_error = String(e); }
  }

  if (est.ig_post) delete est.ig_error;
  if (est.fb_post) delete est.fb_error;
  est.video = video;
  est.t = new Date().toISOString();
  await kv.put(k, JSON.stringify(est));
  const { video: _v, ...ver } = est;
  return json(ver);
}
