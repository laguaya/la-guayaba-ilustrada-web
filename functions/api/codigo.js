// Canjea un código de regalo: entrega el nivel sin pago si el código es válido y tiene usos.
import { buscar } from '../../lib/recursos.js';
import { json, enlaces, contar, body, listo } from './_comun.js';

const huella = async t => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(t)))]
  .map(b => b.toString(16).padStart(2, '0')).join('');

export async function onRequestPost({ request, env }) {
  const { r, n, codigo } = await body(request);
  const f = buscar(r, n);
  const c = String(codigo || '').trim().toUpperCase();
  if (!f || !f.niv.codigos || c.length < 6 || c.length > 40) return json({ error: 'Código no válido.' }, 400);
  const h = await huella(c);
  const cod = f.niv.codigos.find(x => x.hash === h);
  if (!cod) return json({ error: 'Ese código no es válido para este recurso.' }, 400);

  const kv = env.RECURSOS;
  const k = `codigo:${cod.id}`;
  const usados = kv ? Number((await kv.get(k)) || 0) : 0;
  if (usados >= cod.usos) return json({ error: 'Este código ya se agotó.' }, 410);

  const archivos = await enlaces(env, new URL(request.url).origin, f.rec, f.niv, `codigo-${cod.id}-${usados + 1}`, 24);
  if (!archivos.length || !listo(env, f.niv)) return json({ error: 'La descarga todavía no está disponible.' }, 503);
  if (kv) await kv.put(k, String(usados + 1));
  await contar(env, { ...f, ref: `codigo ${cod.id}` });
  return json({ archivos, recurso: f.rec.nombre, nivel: f.niv.nombre });
}
