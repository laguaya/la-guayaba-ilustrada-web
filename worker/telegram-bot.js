// Puente entre Telegram y GitHub para el bot LGI Notas (Cloudflare Worker, gratis).
// Variables secretas del Worker: TELEGRAM_TOKEN, GH_TOKEN, TG_SECRET
const OWNER = '8941716448';
const REPO = 'laguaya/la-guayaba-ilustrada-web';

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const tg = (m, body) => fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/${m}`, {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });

    if (url.pathname === '/setup') {
      const r = await tg('setWebhook', { url: `${url.origin}/tg`, secret_token: env.TG_SECRET,
        allowed_updates: ['callback_query', 'message'] });
      const j = await r.json();
      return new Response(j.ok ? 'Listo: el bot ya está conectado.' : 'Error: ' + j.description,
        { headers: { 'content-type': 'text/plain; charset=utf-8' } });
    }

    if (url.pathname === '/tg' && req.method === 'POST') {
      if (req.headers.get('X-Telegram-Bot-Api-Secret-Token') !== env.TG_SECRET) return new Response('no', { status: 403 });
      const u = await req.json();
      const from = String(u.callback_query?.from?.id ?? u.message?.chat?.id ?? '');
      if (from !== OWNER) return new Response('ok');
      if (u.callback_query) {
        await tg('answerCallbackQuery', { callback_query_id: u.callback_query.id, text: 'Recibido, procesando…' });
      }
      await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
        method: 'POST',
        headers: { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'lgi-notas-bot' },
        body: JSON.stringify({ event_type: 'telegram', client_payload: { update: u } }),
      });
      return new Response('ok');
    }
    return new Response('LGI Notas');
  },
};
