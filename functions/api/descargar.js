// Descarga gratuita (sin donativo): cuenta la descarga y entrega un enlace firmado de 1 hora.
import { buscar } from '../../lib/recursos.js';
import { json, enlaces, contar, body } from './_comun.js';

export async function onRequestPost({ request, env }) {
  const { r, n } = await body(request);
  const f = buscar(r, n);
  if (!f || f.niv.base) return json({ error: 'Este nivel no es gratuito.' }, 400);
  const archivos = await enlaces(env, new URL(request.url).origin, f.rec, f.niv, 'gratis', 1);
  if (!archivos.length || !env.ARCHIVOS) return json({ error: 'La descarga todavía no está disponible.' }, 503);
  await contar(env, { ...f, ref: 'gratis' });
  return json({ archivos });
}
