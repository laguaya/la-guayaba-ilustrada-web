// Crea el cobro en Mercado Pago (Checkout Pro) y devuelve el enlace de pago.
// Sirve para los niveles de pago y para los donativos de la versión gratuita.
import { buscar, total as totalDe } from '../../lib/recursos.js';
import { json, body } from './_comun.js';

export async function onRequestPost({ request, env }) {
  if (!env.MP_TOKEN) return json({ error: 'Los pagos todavía no están activos. Escríbenos por WhatsApp.' }, 503);
  const { r, n, monto } = await body(request);
  const f = buscar(r, n);
  if (!f) return json({ error: 'Recurso no encontrado.' }, 404);

  let total, titulo;
  if (f.niv.base) {
    total = totalDe(f.niv);
    titulo = `${f.rec.nombre} · ${f.niv.nombre}`;
  } else {
    total = Math.round(Number(monto));
    if (!(total >= 10 && total <= 5000)) return json({ error: 'El donativo debe ser de $10 a $5,000.' }, 400);
    titulo = `Donativo · ${f.rec.nombre}`;
  }

  const origin = new URL(request.url).origin;
  const ref = `${f.rec.id}|${f.niv.id}|${crypto.randomUUID().slice(0, 8)}`;
  const vuelta = `${origin}/recursos`;
  const res = await fetch('https://api.mercadopago.com/checkout/preferences', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${env.MP_TOKEN}`,
      'content-type': 'application/json',
      'x-idempotency-key': ref,
    },
    body: JSON.stringify({
      items: [{ id: `${f.rec.id}-${f.niv.id}`, title: titulo, quantity: 1, unit_price: total, currency_id: 'MXN' }],
      external_reference: ref,
      back_urls: { success: vuelta, failure: vuelta, pending: vuelta },
      auto_return: 'approved',
      statement_descriptor: 'GUAYABA ILUSTRADA',
      // Solo pagos que se acreditan al momento, para entregar el archivo en cuanto regresan.
      payment_methods: { excluded_payment_types: [{ id: 'ticket' }, { id: 'atm' }] },
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.init_point) return json({ error: 'No pudimos abrir Mercado Pago. Intenta de nuevo en un momento.' }, 502);
  return json({ url: data.init_point });
}
