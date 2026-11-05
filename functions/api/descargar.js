// Descarga gratuita (sin donativo): cuenta la descarga y entrega el enlace.
import { buscar } from '../../lib/recursos.js';
import { json, enlace, contar, body } from './_comun.js';

export async function onRequestPost({ request, env }) {
  const { r, n } = await body(request);
  const f = buscar(r, n);
  if (!f || f.niv.base) return json({ error: 'Este nivel no es gratuito.' }, 400);
  const url = enlace(env, f.rec, f.niv);
  if (!url) return json({ error: 'El archivo todavía no está disponible. Escríbenos por WhatsApp y te lo mandamos.' }, 503);
  await contar(env, { ...f, ref: 'gratis' });
  return json({ url });
}
