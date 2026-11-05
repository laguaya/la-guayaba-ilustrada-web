// Datos del panel privado: descargas por recurso y nivel, dinero recibido y actividad reciente.
import { RECURSOS } from '../../lib/recursos.js';
import { json } from './_comun.js';

export async function onRequestGet({ request, env }) {
  const clave = request.headers.get('x-clave') || '';
  if (!env.PANEL_CLAVE) return json({ error: 'Falta configurar la variable PANEL_CLAVE en Cloudflare.' }, 503);
  if (clave !== env.PANEL_CLAVE) return json({ error: 'Clave incorrecta.' }, 401);
  const kv = env.RECURSOS;
  if (!kv) return json({ error: 'Falta conectar el contador (KV con el nombre RECURSOS) en Cloudflare.' }, 503);

  const num = async k => Number((await kv.get(k)) || 0);
  const recursos = [];
  for (const rec of RECURSOS) {
    const niveles = [];
    for (const niv of rec.niveles) niveles.push({ id: niv.id, nombre: niv.nombre, n: await num(`n:${rec.id}:${niv.id}`) });
    recursos.push({ id: rec.id, nombre: rec.nombre, total: niveles.reduce((a, b) => a + b.n, 0), niveles });
  }
  return json({
    total: await num('n:total'),
    ventas: await num('m:ventas'),
    donativos: await num('m:donativos'),
    recursos,
    log: JSON.parse((await kv.get('log')) || '[]').slice(0, 30),
  });
}
