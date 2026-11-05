// Entrega un archivo (R2 o Google Drive) solo con un enlace firmado y vigente.
// Cada pago permite hasta 10 descargas por archivo, para que el enlace no circule.
import { buscar } from '../../lib/recursos.js';
import { leerFirma, idDrive } from './_comun.js';

const txt = (m, s) => new Response(m, { status: s, headers: { 'content-type': 'text/plain; charset=utf-8' } });

export async function onRequestGet({ request, env }) {
  const o = await leerFirma(env, new URL(request.url).searchParams.get('t'));
  if (!o) return txt('Este enlace de descarga ya caducó. Vuelve a la página de Recursos o escríbenos por WhatsApp al 720 909 7907.', 403);
  const f = buscar(o.r, o.n);
  if (!f || !f.niv.archivos.includes(o.a)) return txt('Archivo no encontrado.', 404);

  const kv = env.RECURSOS;
  if (kv && o.p !== 'gratis') {
    const k = `uso:${o.p}:${o.a}`;
    const n = Number((await kv.get(k)) || 0);
    if (n >= 10) return txt('Este pago ya alcanzó el límite de descargas. Escríbenos por WhatsApp al 720 909 7907.', 429);
    await kv.put(k, String(n + 1));
  }

  const nombre = `${f.rec.id}-${o.a}`;
  const cab = { 'content-type': 'application/zip', 'content-disposition': `attachment; filename="${nombre}"`, 'cache-control': 'private, no-store' };

  // 1) Bucket privado de R2, si está conectado
  if (env.ARCHIVOS) {
    const obj = await env.ARCHIVOS.get(`${f.rec.id}/${o.a}`);
    if (obj) return new Response(obj.body, { headers: { ...cab, 'content-length': String(obj.size) } });
  }
  // 2) Google Drive: la página baja el archivo y se lo pasa al cliente, sin mostrarle el enlace
  const id = idDrive(env, o.a);
  if (!id) return txt('El archivo todavía no está disponible. Escríbenos por WhatsApp al 720 909 7907.', 404);
  let r;
  try { r = await fetch(`https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`, { redirect: 'follow' }); } catch { r = null; }
  const tipo = r ? r.headers.get('content-type') || '' : '';
  if (!r || !r.ok || tipo.includes('text/html')) return txt('No pudimos preparar tu descarga. Escríbenos por WhatsApp al 720 909 7907.', 502);
  const largo = r.headers.get('content-length');
  return new Response(r.body, { headers: largo ? { ...cab, 'content-length': largo } : cab });
}
