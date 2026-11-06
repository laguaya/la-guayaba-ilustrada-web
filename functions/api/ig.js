// Mensaje automático de Instagram: "comenta EDICIÓN" -> pide seguir -> entrega la skill.
// Webhook de Meta (Instagram API con inicio de sesión de Instagram): https://guayabailustrada.com.mx/api/ig
//
// Variables en Cloudflare Pages (Configuración > Variables y secretos):
//   IG_DM_TOKEN     token del usuario del sistema "Guayaba Bot" del porfolio La Guayaba Ilustrada (secreto, no caduca).
//   IG_ID           id de la cuenta @guayabailustrada. Por defecto: 17841448502239351
//   IG_PAGE_ID      id de la Página de Facebook unida a la cuenta. Por defecto: 103453035328282
//   IG_APP_SECRET   clave secreta de la app "La Guayaba Ilustrada" en Meta (secreto). Valida que el aviso venga de Meta.
//   IG_VERIFY       palabra que tú inventas para verificar el webhook (secreto).
//   IG_USUARIO      (opcional) usuario de la cuenta, sin @. Por defecto: guayabailustrada
//   IG_MEDIA_ID     (opcional) id de una publicación; si existe, solo responde en esa publicación.
// Usa el KV RECURSOS para no responder dos veces el mismo comentario y para contar.

const API = 'https://graph.facebook.com/v21.0';
const PALABRAS = ['edicion'];
const ENLACE = 'https://guayabailustrada.com.mx/recursos?utm_source=instagram&utm_medium=dm&utm_campaign=edicion';

const TXT = {
  seguir: '¡Hola! 🎬 Qué gusto que te interese la skill para editar videos con Claude.\n\nPara mandártela gratis, primero sígueme y luego toca "Ya te sigo" 👇',
  noSigue: 'Todavía no te veo entre mis seguidores 👀\n\nSígueme y vuelve a tocar "Ya te sigo" para liberar tu descarga.',
  listo: '¡Listo, gracias por seguirme! 🙌\n\nAquí está tu skill Video estilo collage LGI. Incluye instalador para Windows y Mac y una guía en PDF.',
  publico: ['¡Te mandé un mensaje! 📩', '¡Revisa tus mensajes! 🎬', '¡Listo, ya te escribí! 📩'],
};

const cuentaId = env => env.IG_ID || '17841448502239351';
const paginaId = env => env.IG_PAGE_ID || '103453035328282';
const normal = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const coincide = t => PALABRAS.some(p => normal(t).split(/[^a-z0-9ñ]+/).includes(p));

// ---------- token (se renueva solo) ----------
async function token(env) {
  const base = env.IG_DM_TOKEN || '';
  const kv = env.RECURSOS;
  if (!kv || !base || base.startsWith('EAA')) return base;   // los tokens de usuario del sistema no caducan
  const marca = base.slice(-12);
  const g = JSON.parse((await kv.get('ig:token')) || 'null');
  const vigente = g && g.base === marca;
  const t = vigente ? g.t : base;
  if (!vigente || Date.now() - g.f > 30 * 864e5) {
    let nuevo = t;
    try {
      const r = await fetch(`${env.IG_AUTH || 'https://graph.instagram.com'}/refresh_access_token?grant_type=ig_refresh_token&access_token=${encodeURIComponent(t)}`);
      const j = await r.json();
      if (j.access_token) nuevo = j.access_token;
    } catch {}
    await kv.put('ig:token', JSON.stringify({ t: nuevo, f: Date.now(), base: marca }));
    return nuevo;
  }
  return t;
}

// Los mensajes de Instagram se mandan con el token de la Página de Facebook unida a la cuenta.
async function tokenPagina(env) {
  const base = await token(env);
  const kv = env.RECURSOS;
  if (kv) {
    const g = JSON.parse((await kv.get('ig:pt')) || 'null');
    if (g && g.b === base.slice(-12) && Date.now() - g.f < 7 * 864e5) return g.t;
  }
  let j = {};
  try { j = await (await fetch(`${env.IG_API || API}/${paginaId(env)}?fields=access_token&access_token=${encodeURIComponent(base)}`)).json(); } catch {}
  if (!j.access_token) { await nota(env, 'token pagina', j); return base; }
  if (kv) await kv.put('ig:pt', JSON.stringify({ t: j.access_token, f: Date.now(), b: base.slice(-12) }));
  return j.access_token;
}

// Guarda los últimos errores en el KV para poder revisarlos.
async function nota(env, donde, j) {
  console.log('IG error', donde, JSON.stringify(j).slice(0, 300));
  const kv = env.RECURSOS; if (!kv) return;
  const l = JSON.parse((await kv.get('ig:errores')) || '[]');
  l.unshift({ t: new Date().toISOString(), donde, e: (j && j.error && j.error.message) || JSON.stringify(j).slice(0, 200) });
  await kv.put('ig:errores', JSON.stringify(l.slice(0, 20)));
}

async function ig(env, ruta, metodo = 'GET', cuerpo) {
  const t = await tokenPagina(env);
  const r = await fetch(`${env.IG_API || API}/${ruta}`, {
    method: metodo,
    headers: { authorization: `Bearer ${t}`, 'content-type': 'application/json' },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) await nota(env, `${metodo} ${ruta.split('?')[0]}`, j);
  return { ok: r.ok, ...j };
}

const botones = (texto, lista) => ({
  attachment: { type: 'template', payload: { template_type: 'button', text: texto, buttons: lista } },
});
const perfil = env => `https://www.instagram.com/${env.IG_USUARIO || 'guayabailustrada'}/`;
const pedirSeguir = env => botones(TXT.seguir, [
  { type: 'web_url', url: perfil(env), title: 'Seguir' },
  { type: 'postback', title: 'Ya te sigo', payload: 'YA_TE_SIGO' },
]);

async function contar(env, k) {
  const kv = env.RECURSOS; if (!kv) return;
  await kv.put(k, String(Number((await kv.get(k)) || 0) + 1));
}

// ---------- comentario con la palabra ----------
async function alComentar(env, cuenta, v) {
  if (!v || !v.id || !coincide(v.text)) return;
  if (v.from && String(v.from.id) === String(cuenta)) return;               // tus propios comentarios
  if (env.IG_MEDIA_ID && v.media && String(v.media.id) !== env.IG_MEDIA_ID) return;
  const kv = env.RECURSOS;
  if (kv) {
    if (await kv.get(`ig:c:${v.id}`)) return;                              // ya respondido
    await kv.put(`ig:c:${v.id}`, '1', { expirationTtl: 60 * 864e2 });
  }
  const r = await ig(env, `${paginaId(env)}/messages`, 'POST', { recipient: { comment_id: v.id }, message: pedirSeguir(env) });
  if (!r.ok) await ig(env, `${paginaId(env)}/messages`, 'POST', {                         // respaldo en texto
    recipient: { comment_id: v.id },
    message: { text: `${TXT.seguir}\n\n${perfil(env)}\n\nCuando me sigas, contesta "Ya te sigo".` },
  });
  const frase = TXT.publico[Math.floor(Math.random() * TXT.publico.length)];
  await ig(env, `${v.id}/replies`, 'POST', { message: frase });
  await contar(env, 'ig:comentarios');
}

// ---------- botón "Ya te sigo" ----------
async function revisarSeguidor(env, igsid) {
  const p = await ig(env, `${igsid}?fields=is_user_follow_business,username`);
  if (p.is_user_follow_business) {
    await ig(env, `${paginaId(env)}/messages`, 'POST', {
      recipient: { id: igsid },
      message: botones(TXT.listo, [{ type: 'web_url', url: ENLACE, title: 'Descargar skill' }]),
    });
    await contar(env, 'ig:entregas');
  } else {
    await ig(env, `${paginaId(env)}/messages`, 'POST', {
      recipient: { id: igsid },
      message: botones(TXT.noSigue, [
        { type: 'web_url', url: perfil(env), title: 'Seguir' },
        { type: 'postback', title: 'Ya te sigo', payload: 'YA_TE_SIGO' },
      ]),
    });
  }
}

async function alMensaje(env, cuenta, m) {
  if (!m || !m.sender || String(m.sender.id) === String(cuenta) || m.message?.is_echo) return;
  if (m.postback?.payload === 'YA_TE_SIGO') return revisarSeguidor(env, m.sender.id);
  const t = normal(m.message?.text);
  if (t && (/ya te sigo|ya te segui|listo|ya$/.test(t) || coincide(t))) return revisarSeguidor(env, m.sender.id);
}

// ---------- firma de Meta ----------
async function firmaValida(env, crudo, cabecera) {
  if (!env.IG_APP_SECRET) return false;
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.IG_APP_SECRET), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const s = await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(crudo));
  const hex = [...new Uint8Array(s)].map(b => b.toString(16).padStart(2, '0')).join('');
  return cabecera === `sha256=${hex}`;
}

// Meta verifica el webhook con un GET
export async function onRequestGet({ request, env }) {
  const q = new URL(request.url).searchParams;
  // Revisión: /api/ig?revisar=<IG_VERIFY> suscribe la Página al bot y muestra el estado (nunca muestra tokens).
  if (env.IG_VERIFY && q.get('revisar') === env.IG_VERIFY) {
    const kv = env.RECURSOS;
    if (kv) await kv.delete('ig:pt');
    const pt = await tokenPagina(env);
    const llamar = async (ruta, metodo = 'GET') => {
      try { return await (await fetch(`${env.IG_API || API}/${ruta}${ruta.includes('?') ? '&' : '?'}access_token=${encodeURIComponent(pt)}`, { method: metodo })).json(); }
      catch (e) { return { error: { message: String(e) } }; }
    };
    const sus = await llamar(`${paginaId(env)}/subscribed_apps?subscribed_fields=feed`, 'POST');
    const out = {
      token_pagina: pt !== env.IG_DM_TOKEN,
      pagina: await llamar(`${paginaId(env)}?fields=name,instagram_business_account`),
      suscribir_pagina: sus,
      apps_pagina: await llamar(`${paginaId(env)}/subscribed_apps`),
      apps_ig: await llamar(`${cuentaId(env)}/subscribed_apps`),
      mensajes: await llamar(`${paginaId(env)}/conversations?platform=instagram&limit=1&fields=id`),
      avisos: kv ? Number((await kv.get('ig:avisos')) || 0) : null,
      comentarios: kv ? Number((await kv.get('ig:comentarios')) || 0) : null,
      entregas: kv ? Number((await kv.get('ig:entregas')) || 0) : null,
      errores: kv ? JSON.parse((await kv.get('ig:errores')) || '[]') : null,
    };
    const limpiar = o => JSON.parse(JSON.stringify(o, (k, v) =>
      k === 'access_token' || k === 'paging' ? undefined : typeof v === 'string' ? v.replace(/access_token=[^&\s"]+/g, 'access_token=***') : v));
    return new Response(JSON.stringify(limpiar(out), null, 2), { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
  }
  if (q.get('hub.mode') === 'subscribe' && env.IG_VERIFY && q.get('hub.verify_token') === env.IG_VERIFY)
    return new Response(q.get('hub.challenge') || '', { headers: { 'content-type': 'text/plain' } });
  return new Response('LGI Instagram', { status: q.get('hub.mode') ? 403 : 200 });
}

// Meta avisa de comentarios y mensajes con un POST
export async function onRequestPost({ request, env, waitUntil }) {
  const crudo = await request.text();
  if (!(await firmaValida(env, crudo, request.headers.get('x-hub-signature-256') || ''))) {
    waitUntil(nota(env, 'firma', { error: { message: 'firma no válida' } }));
    return new Response('firma', { status: 401 });
  }
  let d; try { d = JSON.parse(crudo); } catch { return new Response('ok'); }
  if (env.RECURSOS) waitUntil(contar(env, 'ig:avisos'));
  const tareas = [];
  for (const e of d.entry || []) {
    for (const c of e.changes || []) if (c.field === 'comments') tareas.push(alComentar(env, e.id, c.value));
    for (const m of e.messaging || []) tareas.push(alMensaje(env, e.id, m));
  }
  waitUntil(Promise.allSettled(tareas));
  return new Response('ok');
}
