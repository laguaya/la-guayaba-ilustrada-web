// Utilidades compartidas por las funciones de recursos (no es una ruta).
// Variables en Cloudflare Pages > Settings:
//   RECURSOS      enlace (binding) a un espacio KV para contar descargas
//   MP_TOKEN      Access Token de producción de Mercado Pago (secreto)
//   PANEL_CLAVE   contraseña del panel /panel (secreto)
//   LINK_<CLAVE>_<NIVEL>  enlace de descarga de cada nivel (secreto)

export const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

export const enlace = (env, rec, niv) => env[`LINK_${rec.clave}_${niv.id.toUpperCase()}`] || '';

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

export async function body(req) {
  try { return await req.json(); } catch { return {}; }
}
