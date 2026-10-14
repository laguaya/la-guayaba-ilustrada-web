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
IGQ = 'drafts/.igqueue.json'
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


SR_MODEL = '/tmp/FSRCNN_x2.pb'
SR_URL = 'https://raw.githubusercontent.com/Saafke/FSRCNN_Tensorflow/master/models/FSRCNN_x2.pb'


def mejorar(im, objetivo=2000):
    """Agranda con IA (FSRCNN) las fotos chicas y las afina; las grandes solo se ajustan."""
    from PIL import Image, ImageFilter
    try:
        import cv2, numpy as np
        if not os.path.exists(SR_MODEL):
            open(SR_MODEL, 'wb').write(requests.get(SR_URL, timeout=60).content)
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(SR_MODEL); sr.setModel('fsrcnn', 2)
        a = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
        a = cv2.fastNlMeansDenoisingColored(a, None, 3, 3, 7, 21)  # quita ruido de compresión
        for _ in range(2):
            if max(a.shape[:2]) >= objetivo * 0.8:
                break
            a = sr.upsample(a)
        im = Image.fromarray(cv2.cvtColor(a, cv2.COLOR_BGR2RGB))
    except Exception as e:
        print('Mejora con IA no disponible:', e, file=sys.stderr)
        k = objetivo / max(im.size)
        if k > 1:
            im = im.resize((round(im.size[0] * min(k, 2.5)), round(im.size[1] * min(k, 2.5))), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=2))
    im.thumbnail((objetivo, objetivo), Image.LANCZOS)
    return im


def get_photo(msg, dest):
    """Descarga la foto de Telegram, la mejora y la guarda. Regresa el tamaño original."""
    from PIL import Image
    try:
        import pillow_heif; pillow_heif.register_heif_opener()  # fotos de iPhone mandadas como archivo
    except Exception:
        pass
    ph = msg.get('photo')
    fid = ph[-1]['file_id'] if ph else msg['document']['file_id']
    info = tg('getFile', file_id=fid)
    url = f'https://api.telegram.org/file/bot{TOKEN}/' + info['result']['file_path']
    raw = requests.get(url, timeout=120).content
    im = Image.open(io.BytesIO(raw))
    from PIL import ImageOps
    im = ImageOps.exif_transpose(im).convert('RGB')
    orig = im.size
    if max(orig) < 1800:
        im = mejorar(im)
    else:
        im.thumbnail((2400, 2400), Image.LANCZOS)
    im.save(dest, 'WEBP', quality=88, method=6)
    return orig


def tip(orig):
    if max(orig) < 1280:
        return f'\n\nℹ️ La foto llegó chica ({orig[0]}×{orig[1]} px) y la mejoré con IA. Para máxima calidad mándala como archivo: 📎 → Archivo → elige la foto.'
    return ''


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


def note_get(nid):
    """Regresa (dict, guardar) para un borrador o una nota publicada en formato JSON."""
    path = f'drafts/{nid}.json'
    if os.path.exists(path):
        n = load(path)
        return n, lambda x: save(path, x)
    lines = open('posts.js', encoding='utf-8').read().split('\n')
    for i, ln in enumerate(lines):
        if ln.strip().startswith('{"id": "' + nid + '"'):
            n = json.loads(ln.strip().rstrip(','))
            def put(x, i=i):
                lines[i] = '  ' + json.dumps(x, ensure_ascii=False) + ','
                open('posts.js', 'w', encoding='utf-8').write('\n'.join(lines))
            return n, put
    return None, None


def add_photo(nid, dest, caption=''):
    """Primera foto real = portada; las siguientes van a la galería de la nota."""
    n, put = note_get(nid)
    if not n:
        return None
    if '-foto' not in n.get('img', ''):
        set_cover(nid, dest)
        return 'portada'
    n.setdefault('g', []).append({'s': dest, 'c': caption} if caption else dest)
    put(n)
    return 'galeria'


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
    mg = msg.get('media_group_id')
    if mg:
        if nid:
            remember('mg' + str(mg), nid)
        else:
            nid = msgs().get('mg' + str(mg))
    if is_photo:
        if nid:
            dest = f'assets/work/nota-{nid}-foto{u["update_id"]}.webp'
            orig = get_photo(msg, dest)
            r = add_photo(nid, dest, text if mg is None else '')
            if r == 'portada':
                reply(mid, '🖼 Listo, esta foto queda como portada de esa nota.' + tip(orig))
                return
            if r == 'galeria':
                reply(mid, '🖼 Listo, foto agregada a la galería de la nota.' + tip(orig))
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


def build_carousel(n):
    """Crea las 3 láminas en assets/ig/<id>/ y regresa sus rutas."""
    sys.path.insert(0, 'scripts')
    import carrusel
    out = f'assets/ig/{n["id"]}'
    data = dict(n['ig'])
    data.setdefault('img', n['img'])
    if not os.path.exists(data['img']):
        data['img'] = n['img']
    if '-foto' not in data['img']:
        # sin foto real: fondo de marca limpio en vez de la portada con texto
        import portada
        os.makedirs(out, exist_ok=True)
        data['img'] = portada.fondo(n['id'], n['k'], f'/tmp/fondo-{n["id"]}.jpg')
    now = datetime.now(timezone(timedelta(hours=-6)))
    meses = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    data.setdefault('fecha', f'{now.day} {meses[now.month - 1]} {now.year}')
    carrusel.make(data, out)
    return [f'{out}/{i}.jpg' for i in (1, 2, 3)]


def send_carousel(n):
    try:
        files = build_carousel(n)
    except Exception as e:
        tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude armar el carrusel de Instagram: {e}')
        return False
    media, fh = [], {}
    for i, f in enumerate(files):
        fh[f'f{i}'] = open(f, 'rb')
        item = {'type': 'photo', 'media': f'attach://f{i}'}
        if i == 0:
            item['caption'] = ('📲 Carrusel para Instagram\n\n' + n['ig'].get('caption', ''))[:1000]
        media.append(item)
    r = tg('sendMediaGroup', files=fh, chat_id=CHAT, media=media)
    for f in fh.values():
        f.close()
    if r.get('ok'):
        for m in r['result']:
            remember(m['message_id'], n['id'])
    else:
        tg('sendMessage', chat_id=CHAT, text=f'⚠️ Telegram no aceptó el carrusel: {r.get("description")}')
    return bool(r.get('ok'))


def queue_instagram(n):
    q = load(IGQ) if os.path.exists(IGQ) else []
    q.append({'id': n['id'], 'caption': n['ig'].get('caption', ''), 'reply': n.get('tg')})
    save(IGQ, q)


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
        kb = [[{'text': '✅ Publicar en la web', 'callback_data': 'pub:' + n['id']}]]
        if n.get('ig') and send_carousel(n):
            kb.append([{'text': '📲 Web + Instagram', 'callback_data': 'pig:' + n['id']}])
        kb.append([{'text': '🗑 Descartar', 'callback_data': 'del:' + n['id']}])
        r = tg('sendMessage', chat_id=CHAT, text=body[:3900], parse_mode='HTML',
               disable_web_page_preview='true', reply_markup={'inline_keyboard': kb})
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
    upd = os.environ.get('UPDATE', '').strip()
    if upd and upd != 'null':
        ups = [json.loads(upd)]
        rounds = 0
    else:
        rounds = int(os.environ.get('ROUNDS', '1'))
    for _ in range(rounds):
        r = tg('getUpdates', offset=off, timeout=int(os.environ.get('LONGPOLL', '0')), allowed_updates=['callback_query', 'message'])
        ups = r.get('result', [])
        if ups or not r.get('ok'):
            break
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
        if accion in ('pub', 'pig'):
            publish(n)
            os.remove(path)
            if accion == 'pig' and n.get('ig'):
                queue_instagram(n)
                if os.environ.get('IG_TOKEN'):
                    mark(cq, '✅ Publicada en la web. En unos minutos sale el carrusel en Instagram.')
                else:
                    mark(cq, '✅ Publicada en la web. Instagram todavía no está conectado: descarga el carrusel de arriba y súbelo tú.')
            else:
                mark(cq, '✅ Publicada. Aparece en el blog en uno o dos minutos.')
            print('Publicada:', nid)
        elif accion == 'del':
            os.remove(path)
            if n.get('img', '').startswith('assets/work/nota-') and os.path.exists(n['img']):
                os.remove(n['img'])
            import shutil
            shutil.rmtree(f'assets/ig/{nid}', ignore_errors=True)
            mark(cq, '🗑 Descartada.')
            print('Descartada:', nid)
        changed = True
    if ups and rounds:
        os.makedirs('drafts', exist_ok=True)
        open(OFFSET, 'w').write(str(off))
        changed = True


def instagram():
    """Publica los carruseles en cola usando la API oficial de Instagram."""
    import time
    global changed
    if not os.path.exists(IGQ):
        return
    q = load(IGQ)
    tok, uid = os.environ.get('IG_TOKEN'), os.environ.get('IG_USER_ID')
    if not (tok and uid):
        return
    api = os.environ.get('IG_API', 'https://graph.instagram.com/v21.0')
    site = os.environ.get('SITE', 'https://la-guayaba-ilustrada-web.pages.dev')
    rest = []
    for item in q:
        urls = [f'{site}/assets/ig/{item["id"]}/{i}.jpg' for i in (1, 2, 3)]
        for _ in range(30):  # espera a que la web publique las imágenes
            if all(requests.head(u, timeout=20).status_code == 200 for u in urls):
                break
            time.sleep(10)
        try:
            kids = []
            for u in urls:
                c = requests.post(f'{api}/{uid}/media', data={'image_url': u, 'is_carousel_item': 'true', 'access_token': tok}, timeout=60).json()
                kids.append(c['id'])
            car = requests.post(f'{api}/{uid}/media', data={'media_type': 'CAROUSEL', 'children': ','.join(kids),
                                'caption': item['caption'], 'access_token': tok}, timeout=60).json()
            for _ in range(20):
                st = requests.get(f'{api}/{car["id"]}', params={'fields': 'status_code', 'access_token': tok}, timeout=30).json()
                if st.get('status_code') == 'FINISHED':
                    break
                time.sleep(6)
            pub = requests.post(f'{api}/{uid}/media_publish', data={'creation_id': car['id'], 'access_token': tok}, timeout=60).json()
            if 'id' not in pub:
                raise RuntimeError(pub)
            tg('sendMessage', chat_id=CHAT, text='📲 Listo, el carrusel ya está publicado en Instagram.', reply_to_message_id=item.get('reply'))
        except Exception as e:
            print('Instagram falló:', e, file=sys.stderr)
            item['intentos'] = item.get('intentos', 0) + 1
            if item['intentos'] < 3:
                rest.append(item)
            else:
                tg('sendMessage', chat_id=CHAT, text='⚠️ No pude publicar el carrusel en Instagram. Súbelo a mano con las imágenes de arriba.', reply_to_message_id=item.get('reply'))
    if rest:
        save(IGQ, rest)
    else:
        os.remove(IGQ)
    changed = True


def sh(*a):
    import subprocess
    return subprocess.run(a, capture_output=True, text=True)


def commit(msg):
    sh('git', 'add', '-A', 'drafts', 'inbox', 'posts.js', 'assets')
    if sh('git', 'diff', '--cached', '--quiet').returncode == 0:
        return
    sh('git', 'commit', '-m', msg)
    for _ in range(4):
        if sh('git', 'pull', '--rebase', '-q', 'origin', 'main').returncode == 0 and \
           sh('git', 'push', '-q', 'origin', 'main').returncode == 0:
            return
        import time; time.sleep(4)


def listen(hours=5.6):
    """Escucha Telegram sin parar (hasta ~6 h) y luego se vuelve a lanzar solo."""
    import time
    global changed
    sh('git', 'config', 'user.name', 'La Guayaba Ilustrada')
    sh('git', 'config', 'user.email', 'laguayabailustrada@gmail.com')
    os.environ['LONGPOLL'], os.environ['ROUNDS'] = '25', '1'
    code = sh('git', 'rev-parse', 'HEAD:scripts/notas.py').stdout.strip()
    t0 = time.time()
    while time.time() - t0 < hours * 3600:
        try:
            sh('git', 'pull', '--rebase', '-q', 'origin', 'main')
            if sh('git', 'rev-parse', 'HEAD:scripts/notas.py').stdout.strip() != code:
                print('Hay una versión nueva del bot; reinicio.')
                break
            changed = False
            send_pending()
            poll()
            if changed:
                commit('Notas: actualización desde Telegram')
            if os.path.exists(IGQ) and os.environ.get('IG_TOKEN'):
                changed = False
                instagram()
                if changed:
                    commit('Notas: carrusel publicado en Instagram')
        except Exception as e:
            print('Error en la vuelta:', e, file=sys.stderr)
            time.sleep(10)
    # relevo: lanza otra vez este mismo workflow
    repo, tok = os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GITHUB_TOKEN')
    if repo and tok:
        r = requests.post(f'https://api.github.com/repos/{repo}/actions/workflows/notas.yml/dispatches',
                          headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'},
                          json={'ref': 'main'}, timeout=30)
        print('Relevo:', r.status_code)


if __name__ == '__main__' and '--listen' in sys.argv:
    os.makedirs('drafts', exist_ok=True)
    listen()
elif __name__ == '__main__' and '--instagram' in sys.argv:
    instagram()
    open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a').write(f'changed={"true" if changed else "false"}\n')
elif __name__ == '__main__':
    os.makedirs('drafts', exist_ok=True)
    send_pending()
    poll()
    open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a').write(f'changed={"true" if changed else "false"}\n')
