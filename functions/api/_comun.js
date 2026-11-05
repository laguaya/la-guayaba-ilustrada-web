// Utilidades compartidas por las funciones de recursos (no es una ruta).
// Configuración en Cloudflare Pages > Settings:
//   DRIVE_GRATIS, DRIVE_PRO  enlace de Google Drive de cada archivo (secretos).
//                 El cliente nunca ve estos enlaces: la página descarga el archivo por él.
//   ARCHIVOS      (opcional) bucket privado de R2; si existe, se usa en lugar de Drive
//   RECURSOS      enlace (binding) a un espacio KV para contar descargas
//   MP_TOKEN      Access Token de producción de Mercado Pago (secreto)
//   PANEL_CLAVE   contraseña del panel /panel (secreto)
//   FIRMA         texto largo al azar para firmar los enlaces de descarga (secreto)

export const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

export async function body(req) {
  try { return await req.json(); } catch { return {}; }
}

// ---------- almacenamiento ----------
const claveDrive = a => 'DRIVE_' + a.replace(/\.zip$/, '').replace(/[^a-z0-9]/gi, '_').toUpperCase();
export const idDrive = (env, a) => {
  const v = String(env[claveDrive(a)] || '').trim();
  const m = v.match(/\/d\/([\w-]{20,})/) || v.match(/[?&]id=([\w-]{20,})/) || v.match(/^([\w-]{20,})$/);
  return m ? m[1] : '';
};
// ¿Están disponibles todos los archivos de este nivel?
export const listo = (env, niv) => !!env.ARCHIVOS || niv.archivos.every(a => idDrive(env, a));

// ---------- enlaces firmados ----------
const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const llave = env => env.FIRMA || env.MP_TOKEN || env.PANEL_CLAVE || '';

async function hmac(env, txt) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(llave(env)), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(txt)));
}

// Crea los enlaces de descarga de un nivel. p: número de pago o 'gratis'. Caducan en `horas`.
export async function enlaces(env, origin, rec, niv, p, horas) {
  if (!llave(env)) return [];
  const e = Date.now() + horas * 3600e3;
  return Promise.all(niv.archivos.map(async a => {
    const datos = b64(new TextEncoder().encode(JSON.stringify({ r: rec.id, n: niv.id, a, p, e })));
    return { nombre: a, url: `${origin}/api/archivo?t=${datos}.${await hmac(env, datos)}` };
  }));
}

export async function leerFirma(env, t) {
  const [datos, firma] = String(t || '').split('.');
  if (!datos || !firma || !llave(env) || firma !== (await hmac(env, datos))) return null;
  try {
    const o = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(datos.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))));
    return o.e > Date.now() ? o : null;
  } catch { return null; }
}

// ---------- contador ----------
// Suma una descarga al contador. Si el KV aún no está conectado, no falla.
export async function contar(env, { rec, niv, monto = 0, ref = '' }) {
  const kv = env.RECURSOS;
  if (!kv) return;
  const inc = async (k, by = 1) => {
    const v = Number((await kv.get(k)) || 0);
    await kv.put(k, String(v + by));
  };
  await inc(`n:${rec.id}:${niv.id}`);
  await inc('n:total');
  if (monto > 0) await inc(niv.base ? 'm:ventas' : 'm:donativos', monto);
  const log = JSON.parse((await kv.get('log')) || '[]');
  log.unshift({ t: new Date().toISOString(), r: rec.id, n: niv.id, m: monto, ref });
  await kv.put('log', JSON.stringify(log.slice(0, 150)));
}
