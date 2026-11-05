// Entrega un archivo del bucket privado solo con un enlace firmado y vigente.
// Cada pago permite hasta 10 descargas por archivo, para que el enlace no circule.
import { buscar } from '../../lib/recursos.js';
import { leerFirma } from './_comun.js';

const txt = (m, s) => new Response(m, { status: s, headers: { 'content-type': 'text/plain; charset=utf-8' } });

export async function onRequestGet({ request, env }) {
  const o = await leerFirma(env, new URL(request.url).searchParams.get('t'));
  if (!o) return txt('Este enlace de descarga ya caducó. Vuelve a la página de Recursos o escríbenos por WhatsApp al 720 909 7907.', 403);
  const f = buscar(o.r, o.n);
  if (!f || !f.niv.archivos.includes(o.a)) return txt('Archivo no encontrado.', 404);
  if (!env.ARCHIVOS) return txt('Las descargas todavía no están activas. Escríbenos por WhatsApp al 720 909 7907.', 503);

  const kv = env.RECURSOS;
  if (kv && o.p !== 'gratis') {
    const k = `uso:${o.p}:${o.a}`;
    const n = Number((await kv.get(k)) || 0);
    if (n >= 10) return txt('Este pago ya alcanzó el límite de descargas. Escríbenos por WhatsApp al 720 909 7907.', 429);
    await kv.put(k, String(n + 1));
  }

  const obj = await env.ARCHIVOS.get(`${f.rec.id}/${o.a}`);
  if (!obj) return txt('El archivo todavía no está disponible. Escríbenos por WhatsApp al 720 909 7907.', 404);
  const nombre = `${f.rec.id}-${o.a}`;
  return new Response(obj.body, {
    headers: {
      'content-type': obj.httpMetadata?.contentType || 'application/zip',
      'content-disposition': `attachment; filename="${nombre}"`,
      'content-length': String(obj.size),
      'cache-control': 'private, no-store',
    },
  });
}
