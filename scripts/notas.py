"""Notas automáticas de La Guayaba Ilustrada.

1. Envía a Telegram cada borrador nuevo de drafts/ con botones Publicar / Descartar.
2. Lee los botones que se presionaron y publica o descarta la nota.

Corre dentro de GitHub Actions. Necesita el secreto TELEGRAM_TOKEN.
"""
import glob, io, json, os, re, sys
from datetime import datetime, timezone, timedelta
import requests

TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT = int(os.environ['TELEGRAM_CHAT_ID'])
API = f'https://api.telegram.org/bot{TOKEN}/'
OFFSET = 'drafts/.offset'
MSGS = 'drafts/.msgs.json'
COLORS = {'Noticias': '#FF9D00', 'Tendencias': '#FF3674', 'Inspiración': '#FFA4BE'}
MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
changed = False


def tg(method, files=None, **data):
    for k, v in list(data.items()):
        if isinstance(v, (dict, list)):
            data[k] = json.dumps(v, ensure_ascii=False)
    r = requests.post(API + method, data=data, files=files, timeout=60)
    j = r.json()
    if not j.get('ok'):
        print(f'Telegram {method} falló: {j.get("description")}', file=sys.stderr)
    return j


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def load(path):
    return json.load(open(path, encoding='utf-8'))


def save(path, data):
    json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def msgs():
    return load(MSGS) if os.path.exists(MSGS) else {}


def remember(mid, nid):
    m = msgs(); m[str(mid)] = nid
    save(MSGS, dict(list(m.items())[-400:]))


def reply(mid, text):
    tg('sendMessage', chat_id=CHAT, text=text, reply_to_message_id=mid)


def get_photo(msg, dest):
    from PIL import Image
    ph = msg.get('photo')
    fid = ph[-1]['file_id'] if ph else msg['document']['file_id']
    info = tg('getFile', file_id=fid)
    url = f'https://api.telegram.org/file/bot{TOKEN}/' + info['result']['file_path']
    raw = requests.get(url, timeout=60).content
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    im.thumbnail((1600, 1600))
    im.save(dest, 'WEBP', quality=86)


def set_cover(nid, src_img):
    """Pone la foto como portada de un borrador o de una nota ya publicada."""
    path = f'drafts/{nid}.json'
    if os.path.exists(path):
        n = load(path); old = n.get('img', '')
        n['img'] = src_img; n['cr'] = 'Foto: La Guayaba Ilustrada'
        save(path, n)
    else:
        js = open('posts.js', encoding='utf-8').read()
        lines = js.split('\n')
        for i, ln in enumerate(lines):
            if f'"id": "{nid}"' in ln or f"id:'{nid}'" in ln:
                m = re.search(r'("img": "|img:\')([^"\']+)', ln)
                old = m.group(2) if m else ''
                ln = ln.replace(old, src_img, 1) if old else ln
                ln = re.sub(r'"cr": "[^"]*"', '"cr": "Foto: La Guayaba Ilustrada"', ln)
                lines[i] = re.sub(r"cr:'[^']*'", "cr:'Foto: La Guayaba Ilustrada'", ln)
                break
        else:
            return False
        open('posts.js', 'w', encoding='utf-8').write('\n'.join(lines))
    if old.startswith('assets/work/nota-') and old != src_img and os.path.exists(old):
        os.remove(old)
    return True


def handle_message(u, msg):
    """Fotos y pedidos que manda Sergio por Telegram."""
    os.makedirs('inbox', exist_ok=True)
    mid = msg['message_id']
    rto = (msg.get('reply_to_message') or {}).get('message_id')
    nid = msgs().get(str(rto)) if rto else None
    text = msg.get('text') or msg.get('caption') or ''
    is_photo = 'photo' in msg or (msg.get('document', {}).get('mime_type', '').startswith('image/'))
    if text.strip().lower() in ('/start', '/help', '/ayuda'):
        reply(mid, 'Hola. Aquí te llegan las notas para aprobar.\n\n'
              '• Mándame un link o un texto con lo que quieres que se publique y lo redacto en mi próxima vuelta.\n'
              '• Para cambiar la portada de una nota, responde a su mensaje con la foto.\n'
              '• Una foto suelta se guarda para usarla en la siguiente nota.')
        return
    if is_photo:
        if nid:
            dest = f'assets/work/nota-{nid}-foto{u["update_id"]}.webp'
            get_photo(msg, dest)
            if set_cover(nid, dest):
                reply(mid, '🖼 Listo, esta foto queda como portada de esa nota.')
                if text:
                    save(f'inbox/{u["update_id"]}.json', {'tipo': 'texto', 'nota': nid, 'texto': text, 'fecha': msg['date']})
                return
        dest = f'inbox/foto-{u["update_id"]}.webp'
        get_photo(msg, dest)
        save(f'inbox/{u["update_id"]}.json', {'tipo': 'foto', 'archivo': dest, 'texto': text, 'nota': nid, 'fecha': msg['date']})
        reply(mid, '📥 Foto guardada. La uso en la nota que me indiques o en la siguiente que redacte.')
        return
    if text:
        urgente = bool(re.search(r'urgent|ya mismo|ahorita|de inmediato', text, re.I))
        save(f'inbox/{u["update_id"]}.json', {'tipo': 'texto', 'texto': text, 'nota': nid, 'urgente': urgente, 'fecha': msg['date']})
        reply(mid, '📥 Recibido. Lo redacto en mi próxima vuelta, que es en menos de una hora, y te lo mando aquí para que lo apruebes.')


def send_pending():
    global changed
    for path in sorted(glob.glob('drafts/*.json')):
        n = load(path)
        if n.get('tg'):
            continue
        cap = f'<b>Nota nueva para revisar</b> · {esc(n["k"])}\n\n<b>{esc(n["t"])}</b>\n<i>{esc(n["x"])}</i>'
        img = n.get('img', '')
        if img and os.path.exists(img):
            with open(img, 'rb') as f:
                r0 = tg('sendPhoto', files={'photo': f}, chat_id=CHAT, caption=cap[:1000], parse_mode='HTML')
        else:
            r0 = tg('sendMessage', chat_id=CHAT, text=cap, parse_mode='HTML')
        if r0.get('ok'):
            remember(r0['result']['message_id'], n['id'])
        body = '\n\n'.join(esc(p) for p in n['b'])
        if n.get('src'):
            body += f'\n\nFuente: {esc(n["src"])}'
        r = tg('sendMessage', chat_id=CHAT, text=body[:3900], parse_mode='HTML',
               disable_web_page_preview='true',
               reply_markup={'inline_keyboard': [[
                   {'text': '✅ Publicar', 'callback_data': 'pub:' + n['id']},
                   {'text': '🗑 Descartar', 'callback_data': 'del:' + n['id']}]]})
        if r.get('ok'):
            n['tg'] = r['result']['message_id']
            remember(n['tg'], n['id'])
            save(path, n)
            changed = True
            print('Enviada a Telegram:', n['id'])


def publish(n):
    now = datetime.now(timezone(timedelta(hours=-6)))
    post = {'id': n['id'], 'k': n['k'], 'c': n.get('c') or COLORS.get(n['k'], '#FF3674'),
            'd': f'{now.day} {MESES[now.month - 1]} {now.year}', 'img': n['img'],
            'alt': n.get('alt', ''), 'cr': n.get('cr', ''), 't': n['t'], 'x': n['x'], 'b': n['b']}
    if n.get('src'):
        post['src'] = n['src']
        if n.get('sn'):
            post['sn'] = n['sn']
    js = open('posts.js', encoding='utf-8').read()
    if f"'{n['id']}'" in js or f'"{n["id"]}"' in js:
        return
    line = '  ' + json.dumps(post, ensure_ascii=False) + ',\n'
    js = js.replace('window.POSTS=[\n', 'window.POSTS=[\n' + line, 1)
    open('posts.js', 'w', encoding='utf-8').write(js)


def mark(cq, texto):
    m = cq.get('message') or {}
    tg('answerCallbackQuery', callback_query_id=cq['id'], text=texto)
    if m:
        tg('editMessageReplyMarkup', chat_id=CHAT, message_id=m['message_id'], reply_markup={'inline_keyboard': []})
        tg('sendMessage', chat_id=CHAT, text=texto, reply_to_message_id=m['message_id'])


def poll():
    global changed
    off = int(open(OFFSET).read().strip() or 0) if os.path.exists(OFFSET) else 0
    r = tg('getUpdates', offset=off, timeout=0, allowed_updates=['callback_query', 'message'])
    ups = r.get('result', [])
    for u in ups:
        off = u['update_id'] + 1
        msg = u.get('message')
        if msg and msg.get('chat', {}).get('id') == CHAT:
            try:
                handle_message(u, msg)
            except Exception as e:
                print('Error con mensaje:', e, file=sys.stderr)
                reply(msg['message_id'], 'No pude procesar este mensaje, ¿me lo mandas otra vez?')
            changed = True
            continue
        cq = u.get('callback_query')
        if not cq or cq['from']['id'] != CHAT:
            continue
        accion, _, nid = (cq.get('data') or '').partition(':')
        if not re.fullmatch(r'[a-z0-9-]+', nid or ''):
            continue
        path = f'drafts/{nid}.json'
        if not os.path.exists(path):
            tg('answerCallbackQuery', callback_query_id=cq['id'], text='Esa nota ya se había procesado.')
            continue
        n = load(path)
        if accion == 'pub':
            publish(n)
            os.remove(path)
            mark(cq, '✅ Publicada. Aparece en el blog en uno o dos minutos.')
            print('Publicada:', nid)
        elif accion == 'del':
            os.remove(path)
            if n.get('img', '').startswith('assets/work/nota-') and os.path.exists(n['img']):
                os.remove(n['img'])
            mark(cq, '🗑 Descartada.')
            print('Descartada:', nid)
        changed = True
    if ups:
        os.makedirs('drafts', exist_ok=True)
        open(OFFSET, 'w').write(str(off))
        changed = True


if __name__ == '__main__':
    os.makedirs('drafts', exist_ok=True)
    send_pending()
    poll()
    open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a').write(f'changed={"true" if changed else "false"}\n')
