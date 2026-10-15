"""Notas automáticas de La Guayaba Ilustrada.

1. Envía a Telegram cada borrador nuevo de drafts/ con botones Publicar / Descartar.
2. Lee los botones que se presionaron y publica o descarta la nota.

Corre dentro de GitHub Actions. Necesita el secreto TELEGRAM_TOKEN.
"""
import glob, io, json, os, re, sys, time
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
    im.thumbnail((2400, 2400), Image.LANCZOS)  # se guarda tal cual, sin inventar detalle
    im.save(dest, 'WEBP', quality=92, method=6)
    return orig


def tip(orig):
    if max(orig) < 1280:
        return f'\n\nℹ️ Ojo: la foto llegó chica ({orig[0]}×{orig[1]} px) y en computadora se verá pequeña. Para buena calidad mándala como archivo (📎 → Archivo) y de al menos 1600 px de ancho.'
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


def mejor(a, b):
    """True si la foto a tiene más resolución que la foto b."""
    from PIL import Image
    try:
        return Image.open(a).size[0] > Image.open(b).size[0] * 1.15
    except Exception:
        return False


PREVIEW = set()   # borradores a los que hay que reenviarles el carrusel
NOFOTO = {}       # id -> True si el último carrusel salió sin foto real


def ig_store(nid, n, put):
    """Dónde se guardan las fotos del carrusel: en el borrador o, si ya está publicada, en drafts/ig/<id>.json."""
    if os.path.exists(f'drafts/{nid}.json'):
        return n, put
    p = f'drafts/ig/{nid}.json'
    d = load(p) if os.path.exists(p) else {}
    def sput(x):
        os.makedirs('drafts/ig', exist_ok=True)
        save(p, x)
    return d, sput


def misma(a, b):
    import hashlib
    try:
        return hashlib.md5(open(a, 'rb').read()).digest() == hashlib.md5(open(b, 'rb').read()).digest()
    except Exception:
        return False


def add_photo(nid, dest, caption=''):
    """Fotos que manda Sergio respondiendo a una nota.
    - Nota con video: las fotos son solo para Instagram (1a = lámina 1, 2a = lámina 2); la web no cambia.
    - Nota sin video: la 1a foto real es portada de la web y lámina 1; las demás van a la lámina 2.
    - Texto "2" = lámina 2; "portada" = portada de la web; "galería" = galería de la web.
    - Una foto repetida se ignora."""
    n, put = note_get(nid)
    if not n:
        return None
    c = caption.lower().strip()
    st, sput = ig_store(nid, n, put)
    g = [x['s'] if isinstance(x, dict) else x for x in n.get('g', [])]
    for k in [n.get('img', '').split('?')[0], st.get('ig1'), st.get('ig2')] + g:
        if k and k != dest and os.path.exists(k) and misma(k, dest):
            os.remove(dest)
            return 'dup'
    if 'galer' in c:
        n.setdefault('g', []).append({'s': dest, 'c': caption})
        put(n)
        return 'galeria'
    if c in ('2', 'segunda', 'lámina 2', 'lamina 2') or 'carrusel' in c or 'segunda foto' in c:
        st['ig2'] = dest; sput(st)
        return 'ig2'
    if 'portada' in c and not (n.get('yt') or n.get('vm')):
        set_cover(nid, dest)
        return 'portada'
    if n.get('yt') or n.get('vm'):
        r = 'ig1' if not st.get('ig1') else 'ig2'
        st[r] = dest; sput(st)
        return r
    cur = n.get('img', '').split('?')[0]
    if '-foto' not in cur or mejor(dest, cur):
        set_cover(nid, dest)
        return 'portada'
    st['ig2'] = dest; sput(st)
    return 'ig2'


def siguiente_vuelta():
    """Hora (Ciudad de México) de la siguiente vuelta del redactor: minuto 52, de 6:52 a 21:52."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=-6)))
    t = now.replace(minute=52, second=0, microsecond=0)
    if t <= now:
        t += timedelta(hours=1)
    if t.hour < 6:
        t = t.replace(hour=6)
    elif t.hour > 21:
        t = (t + timedelta(days=1)).replace(hour=6)
    h = t.hour % 12 or 12
    return f"{h}:52 {'am' if t.hour < 12 else 'pm'}" + ('' if t.date() == now.date() else ' de mañana')


def ig_command(nid, mid):
    """Sube a Instagram el carrusel de una nota ya publicada."""
    if os.path.exists(f'drafts/{nid}.json'):
        reply(mid, 'Esa nota todavía no está publicada. Usa el botón 📲 Web + Instagram de la nota.')
        return
    n, _ = note_get(nid)
    igp = f'drafts/ig/{nid}.json'
    if not n or not os.path.exists(igp):
        reply(mid, '⚠️ Esa nota no tiene textos de carrusel guardados, no puedo armarlo.')
        return
    n['ig'] = load(igp)
    if n['ig'].get('ig2'):
        n['ig2'] = n['ig']['ig2']
    n['tg'] = mid
    try:
        build_carousel(n)
    except Exception as e:
        reply(mid, f'⚠️ No pude armar el carrusel: {e}')
        return
    if not os.environ.get('IG_TOKEN'):
        reply(mid, 'Instagram no está conectado todavía.')
        return
    if NOFOTO.get(nid):
        reply(mid, '⚠️ Esta nota no tiene fotos para el carrusel. Respóndele con 1 o 2 fotos y vuelve a escribir "instagram".')
        return
    queue_instagram(n)
    reply(mid, '📲 Va. Armé el carrusel y lo subo a Instagram en unos minutos. Te aviso aquí cuando esté publicado.')
    return


LAST = 'drafts/.last.json'
IGNOW = {}   # id -> message_id: subir a Instagram después de procesar las fotos


def set_last(nid):
    save(LAST, {'id': nid, 't': time.time()})


def last_note():
    if not os.path.exists(LAST):
        return None
    d = load(LAST)
    n, _ = note_get(d['id']) if time.time() - d.get('t', 0) < 24 * 3600 else (None, None)
    return d['id'] if n else None


def handle_message(u, msg):
    """Fotos y pedidos que manda Sergio por Telegram."""
    os.makedirs('inbox', exist_ok=True)
    mid = msg['message_id']
    rto = (msg.get('reply_to_message') or {}).get('message_id')
    nid = msgs().get(str(rto)) if rto else None
    text = msg.get('text') or msg.get('caption') or ''
    is_photo = 'photo' in msg or (msg.get('document', {}).get('mime_type', '').startswith('image/'))
    yt = re.search(r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})', text)
    vm = re.search(r'vimeo\.com/(?:video/)?(\d{5,})', text)
    if vm and nid and not is_photo:
        n, put = note_get(nid)
        if n:
            n['vm'] = vm.group(1); n.pop('yt', None)
            vt = vimeo_thumb(n['vm'])
            if vt:
                n['vt'] = vt
            put(n)
            reply(mid, '🎬 Listo, ese video de Vimeo queda en la nota de la web. En Instagram van las fotos que me mandes.')
            return
    if yt and nid and not is_photo:
        n, put = note_get(nid)
        if n:
            n['yt'] = yt.group(1); n.pop('vm', None)
            put(n)
            reply(mid, '🎬 Listo, ese video de YouTube queda como portada de la nota.')
            return
    ig_word = len(text) < 40 and re.search(r'\b(instagram|ig)\b', text, re.I)
    if not nid and (is_photo or ig_word):
        nid = last_note()   # en iPhone a veces no se puede responder: se usa la última nota
    if nid:
        set_last(nid)
    if nid and not is_photo and ig_word:
        ig_command(nid, mid)
        return
    if text.strip().lower() in ('/start', '/help', '/ayuda'):
        reply(mid, 'Hola. Aquí te llegan las notas para aprobar.\n\n'
              '• Mándame un link o un texto con lo que quieres que se publique y lo redacto en mi próxima vuelta.\n'
              '• Fotos para el carrusel: responde a la nota con 1 o 2 fotos. Si la nota es video, las fotos son solo para Instagram; si no, la primera también es la portada de la web.\n'
              '• Para poner un video de YouTube como portada, responde a la nota con el link del video.\n'
              '• Para subir a Instagram una nota que ya está en la web, responde a la nota con la palabra "instagram".\n'
              '• Para forzar la segunda lámina escribe "2" en el texto de la foto; para mandarla a la galería de la web escribe "galería".\n'
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
            if re.search(r'\b(instagram|ig)\b', text, re.I):
                IGNOW[nid] = mid
                text = ''
            r = add_photo(nid, dest, text if mg is None else '')
            if r:
                borrador = os.path.exists(f'drafts/{nid}.json')
                extra = '' if borrador else '\n\nCuando tengas las fotos que quieres, responde "instagram" a la nota para subir el carrusel.'
                txt = {
                    'portada': '🖼 Esta foto queda de portada en la web y en la primera lámina del carrusel.' + tip(orig),
                    'ig1': '📲 Esta foto va en la primera lámina del carrusel de Instagram. En la web se queda el video.',
                    'ig2': '📲 Esta foto va en la segunda lámina del carrusel de Instagram. No se agrega a la página.',
                    'galeria': '🖼 Listo, foto agregada a la galería de la nota en la web.',
                    'dup': '👌 Esa foto ya la tenía, no la repetí.',
                }[r]
                if not rto:
                    nn, _ = note_get(nid)
                    txt = f'(Nota: {nn["t"][:70]})\n' + txt
                if nid in IGNOW and not borrador:
                    extra = ''
                reply(mid, txt + ('' if r in ('galeria', 'dup') else extra))
                if borrador and r in ('portada', 'ig1', 'ig2'):
                    PREVIEW.add(nid)
                return
        dest = f'inbox/foto-{u["update_id"]}.webp'
        get_photo(msg, dest)
        save(f'inbox/{u["update_id"]}.json', {'tipo': 'foto', 'archivo': dest, 'texto': text, 'nota': nid, 'fecha': msg['date']})
        reply(mid, '📥 Foto guardada. La uso en la nota que me indiques o en la siguiente que redacte.')
        return
    if text:
        urgente = bool(re.search(r'urgent|ya mismo|ahorita|de inmediato', text, re.I))
        save(f'inbox/{u["update_id"]}.json', {'tipo': 'texto', 'texto': text, 'nota': nid, 'urgente': urgente, 'fecha': msg['date']})
        aviso = ''
        if re.search(r'(facebook\.com|fb\.watch|instagram\.com|tiktok\.com|x\.com/|twitter\.com)', text):
            aviso = '\n\nℹ️ Ese link es de una red social y no se puede abrir sin sesión. Voy a buscar la noticia en medios; si tienes el link de una página de noticias o el texto, mándamelo.'
        reply(mid, f'📥 Recibido. Lo redacto en la vuelta de las {siguiente_vuelta()} y te lo mando aquí para que lo apruebes (unos 10 minutos después).' + aviso)


def build_carousel(n):
    """Crea las 3 láminas en assets/ig/<id>/ y regresa sus rutas."""
    sys.path.insert(0, 'scripts')
    import carrusel
    out = f'assets/ig/{n["id"]}'
    data = dict(n['ig'])
    ig1 = n.get('ig1') or n['ig'].get('ig1')
    ig2 = n.get('ig2') or n['ig'].get('ig2')
    data['img'] = ig1 if ig1 and os.path.exists(ig1) else n['img'].split('?')[0]
    if ig2 and os.path.exists(ig2):
        data['img2'] = ig2
    NOFOTO[n['id']] = '-foto' not in data['img']
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
            aviso = ('⚠️ Este carrusel no tiene foto. Respóndele a la nota con 1 o 2 fotos antes de publicar.\n\n'
                     if NOFOTO.get(n['id']) else '')
            item['caption'] = (aviso + '📲 Carrusel para Instagram\n\n' + n['ig'].get('caption', ''))[:1000]
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
            set_last(n['id'])
            save(path, n)
            changed = True
            print('Enviada a Telegram:', n['id'])


def publish(n):
    now = datetime.now(timezone(timedelta(hours=-6)))
    post = {'id': n['id'], 'k': n['k'], 'c': n.get('c') or COLORS.get(n['k'], '#FF3674'),
            'd': f'{now.day} {MESES[now.month - 1]} {now.year}', 'img': n['img'],
            'alt': n.get('alt', ''), 'cr': n.get('cr', ''), 't': n['t'], 'x': n['x'], 'b': n['b']}
    for k in ('g', 'yt', 'vm', 'vt'):
        if n.get(k):
            post[k] = n[k]
    if n.get('src'):
        post['src'] = n['src']
        if n.get('sn'):
            post['sn'] = n['sn']
    if n.get('ig'):
        os.makedirs('drafts/ig', exist_ok=True)
        ig = dict(n['ig'])
        for k in ('ig2',):
            if n.get(k):
                ig[k] = n[k]
        save(f'drafts/ig/{n["id"]}.json', ig)
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


VERIFY = 'drafts/.verify.json'


def verify_live():
    """Revisa en la página real que las notas recién publicadas ya se vean y avisa por Telegram con el link."""
    global changed
    if not os.path.exists(VERIFY):
        return
    site = os.environ.get('SITE', 'https://guayabailustrada.com.mx')
    try:
        live = requests.get(f'{site}/posts.js', params={'t': int(time.time())}, headers={'Cache-Control': 'no-cache'}, timeout=20).text
    except Exception:
        return
    rest = []
    for v in load(VERIFY):
        if f'"{v["id"]}"' in live:
            tg('sendMessage', chat_id=CHAT, reply_to_message_id=v.get('reply'),
               text=f'🌐 Ya está en línea en la página:\n{site}/notas/{v["id"]}\n\nSi en tu celular no la ves, cierra la pestaña y ábrela de nuevo.')
        elif time.time() - v['t'] > 900:
            tg('sendMessage', chat_id=CHAT, reply_to_message_id=v.get('reply'),
               text='⚠️ Pasaron 15 minutos y la nota todavía no aparece en la página. Avísale a Claude para revisarlo.')
        else:
            rest.append(v)
    if rest:
        save(VERIFY, rest)
    else:
        os.remove(VERIFY)
    changed = True


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
            set_last(nid)
            os.remove(path)
            if accion == 'pig' and n.get('ig'):
                try:
                    build_carousel(n)  # rehace las láminas con las fotos más recientes
                except Exception as e:
                    print('Carrusel:', e, file=sys.stderr)
                if NOFOTO.get(n['id']):
                    mark(cq, '✅ Publicada en la web. El carrusel no tenía foto, así que NO lo subí a Instagram. '
                             'Respóndele a la nota con 1 o 2 fotos y después escribe "instagram".')
                elif os.environ.get('IG_TOKEN'):
                    queue_instagram(n)
                    mark(cq, '✅ Publicada en la web. En unos minutos sale el carrusel en Instagram.')
                else:
                    mark(cq, '✅ Publicada en la web. Instagram todavía no está conectado: descarga el carrusel de arriba y súbelo tú.')
            else:
                mark(cq, '✅ Publicada. Te aviso aquí con el link en cuanto ya se vea en la página (1 a 3 minutos).')
            pend = load(VERIFY) if os.path.exists(VERIFY) else []
            pend.append({'id': nid, 'reply': (cq.get('message') or {}).get('message_id'), 't': time.time()})
            save(VERIFY, pend)
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
    site = os.environ.get('SITE', 'https://guayabailustrada.com.mx')
    rest = []
    for item in q:
        urls = [f'{site}/assets/ig/{item["id"]}/{i}.jpg' for i in (1, 2, 3)]
        import hashlib
        local = [hashlib.md5(open(f'assets/ig/{item["id"]}/{i}.jpg', 'rb').read()).hexdigest()
                 if os.path.exists(f'assets/ig/{item["id"]}/{i}.jpg') else None for i in (1, 2, 3)]
        for _ in range(40):  # espera a que la web publique las láminas nuevas (no las de antes)
            try:
                live = [hashlib.md5(requests.get(u + f'?t={time.time():.0f}', timeout=30).content).hexdigest() for u in urls]
                if all(l is None or l == v for l, v in zip(local, live)):
                    break
            except Exception:
                pass
            time.sleep(10)
        urls = [u + f'?v={(l or "")[:8]}' for u, l in zip(urls, local)]
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
                tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude publicar el carrusel en Instagram ({str(e)[:300]}). Súbelo a mano con las imágenes de arriba.', reply_to_message_id=item.get('reply'))
    if rest:
        save(IGQ, rest)
    else:
        os.remove(IGQ)
    changed = True


def sh(*a):
    import subprocess
    return subprocess.run(a, capture_output=True, text=True)


def commit(msg):
    if sh('git', 'diff', '--quiet', '--', 'posts.js').returncode != 0:
        sh('python', 'scripts/seo.py')  # páginas de notas, sitemap, RSS y llms.txt
    sh('git', 'add', '-A', 'drafts', 'inbox', 'posts.js', 'assets', 'notas', 'index.html', 'blog.html', 'precios.html',
       'sitemap.xml', 'feed.xml', 'llms.txt', 'robots.txt')
    if sh('git', 'diff', '--cached', '--quiet').returncode == 0:
        return
    sh('git', 'commit', '-m', msg)
    for _ in range(4):
        if sh('git', 'pull', '--rebase', '-q', 'origin', 'main').returncode == 0 and \
           sh('git', 'push', '-q', 'origin', 'main').returncode == 0:
            return
        import time; time.sleep(4)


IGSTAT = 'drafts/.ig_status.json'


def vimeo_thumb(vid):
    """Miniatura grande de un video de Vimeo (para la tarjeta de afuera)."""
    try:
        r = requests.get('https://vimeo.com/api/oembed.json', params={'url': f'https://vimeo.com/{vid}', 'width': 1280}, timeout=20).json()
        return re.sub(r'_\d+x\d+', '_1280x720', r.get('thumbnail_url', '')) or None
    except Exception as e:
        print('Vimeo:', e, file=sys.stderr)
        return None


def vimeo_backfill():
    """Notas publicadas con video de Vimeo que todavía no tienen miniatura."""
    js = open('posts.js', encoding='utf-8').read()
    for nid in re.findall(r'\{"id": "([^"]+)"[^\n]*"vm": "\d+"', js):
        n, put = note_get(nid)
        if n and n.get('vm') and not n.get('vt'):
            vt = vimeo_thumb(n['vm'])
            if vt:
                n['vt'] = vt; put(n)
                return True
    return False


def ig_check():
    """Confirma por Telegram que Instagram está conectado y avisa antes de que venza el token (60 días)."""
    import hashlib
    tok = os.environ.get('IG_TOKEN')
    if not tok:
        return False
    api = os.environ.get('IG_API', 'https://graph.instagram.com/v21.0')
    h = hashlib.sha256(tok.encode()).hexdigest()[:10]
    st = load(IGSTAT) if os.path.exists(IGSTAT) else {}
    try:
        r = requests.get(f'{api}/me', params={'fields': 'username', 'access_token': tok}, timeout=30).json()
    except Exception as e:
        print('IG check:', e, file=sys.stderr)
        return False
    if 'username' not in r:
        if st.get('bad') != h:
            tg('sendMessage', chat_id=CHAT, text='⚠️ Instagram no aceptó el token guardado en GitHub '
               f'({(r.get("error") or {}).get("message", "sin detalle")}). Genera uno nuevo en Meta y actualiza IG_TOKEN.')
            st['bad'] = h
            save(IGSTAT, st)
            return True
        return False
    if st.get('tok') != h:
        st = {'tok': h, 'user': r['username'], 'since': time.time()}
        tg('sendMessage', chat_id=CHAT, text=f'📸 Instagram conectado: @{r["username"]}.\n\n'
           'Desde ahora, cuando elijas publicar también en Instagram, el carrusel sale solo. '
           'El permiso dura 60 días; te aviso aquí unos días antes para renovarlo.')
    elif time.time() - st.get('since', time.time()) > 50 * 86400 and not st.get('warned'):
        st['warned'] = True
        tg('sendMessage', chat_id=CHAT, text='⏰ El permiso de Instagram vence en unos 10 días. '
           'Entra a developers.facebook.com → LGI Newsbrand → Generar identificador (con sesión solo en @lgi.newsbrand) '
           'y actualiza IG_TOKEN en GitHub.')
    else:
        return False
    save(IGSTAT, st)
    return True


def listen(hours=5.6):
    """Escucha Telegram sin parar (hasta ~6 h) y luego se vuelve a lanzar solo."""
    import time
    global changed
    sh('git', 'config', 'user.name', 'La Guayaba Ilustrada')
    sh('git', 'config', 'user.email', 'laguayabailustrada@gmail.com')
    try:
        while vimeo_backfill():
            pass
        commit('Notas: miniaturas de Vimeo')
        if ig_check():
            commit('Notas: estado de Instagram')
    except Exception as e:
        print('IG check:', e, file=sys.stderr)
    os.environ['LONGPOLL'], os.environ['ROUNDS'] = '25', '1'
    code = sh('git', 'rev-parse', 'HEAD:scripts').stdout.strip()
    t0 = time.time()
    while time.time() - t0 < hours * 3600:
        try:
            sh('git', 'pull', '--rebase', '-q', 'origin', 'main')
            if sh('git', 'rev-parse', 'HEAD:scripts').stdout.strip() != code:
                print('Hay una versión nueva del bot; reinicio.')
                break
            changed = False
            send_pending()
            poll()
            for pid, pmid in list(IGNOW.items()):
                IGNOW.pop(pid, None)
                if os.path.exists(f'drafts/{pid}.json'):
                    PREVIEW.add(pid)
                else:
                    ig_command(pid, pmid)
                changed = True
            for pid in list(PREVIEW):
                PREVIEW.discard(pid)
                if os.path.exists(f'drafts/{pid}.json'):
                    pn = load(f'drafts/{pid}.json')
                    if pn.get('ig'):
                        send_carousel(pn)
                        changed = True
            if changed:
                commit('Notas: actualización desde Telegram')
            if os.path.exists(VERIFY):
                changed = False
                verify_live()
                if changed:
                    commit('Notas: verificación en línea')
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
