// Al regresar de Mercado Pago: verifica el pago y entrega enlaces firmados (válidos 7 días).
// La descarga se cuenta una sola vez por pago, aunque la persona recargue la página.
import { buscar, total } from '../../lib/recursos.js';
import { json, enlaces, contar, body } from './_comun.js';

export async function onRequestPost({ request, env }) {
  const { pago } = await body(request);
  if (!env.MP_TOKEN || !/^\d{5,20}$/.test(String(pago || ''))) return json({ error: 'Pago no válido.' }, 400);

  const res = await fetch(`https://api.mercadopago.com/v1/payments/${pago}`, {
    headers: { authorization: `Bearer ${env.MP_TOKEN}` },
  });
  const p = await res.json().catch(() => ({}));
  if (!res.ok) return json({ error: 'No encontramos ese pago.' }, 404);
  if (p.status !== 'approved') return json({ estado: p.status || 'pendiente' }, 202);

  const [r, n] = String(p.external_reference || '').split('|');
  const f = buscar(r, n);
  if (!f) return json({ error: 'Este pago no corresponde a un recurso.' }, 400);
  const monto = Number(p.transaction_amount || 0);
  if (f.niv.base && monto < total(f.niv)) return json({ error: 'El monto pagado no coincide con el precio.' }, 400);

  const archivos = await enlaces(env, new URL(request.url).origin, f.rec, f.niv, String(pago), 24 * 7);
  if (!archivos.length || !env.ARCHIVOS) return json({ error: `Tu pago ${pago} quedó registrado. Escríbenos por WhatsApp con ese número y te mandamos el archivo.` }, 503);

  const kv = env.RECURSOS;
  if (kv && !(await kv.get(`pago:${pago}`))) {
    await kv.put(`pago:${pago}`, '1');
    await contar(env, { ...f, monto, ref: String(pago) });
  }
  return json({ archivos, recurso: f.rec.nombre, nivel: f.niv.nombre });
}
