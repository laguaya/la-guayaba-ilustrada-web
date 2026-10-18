"""Notas automáticas de La Guayaba Ilustrada.

1. Envía a Telegram cada borrador nuevo de drafts/ con botones Publicar / Descartar.
2. Lee los botones que se presionaron y publica o descarta la nota.

Corre dentro de GitHub Actions. Necesita el secreto TELEGRAM_TOKEN.
"""
import glob, io, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
import requests
from urllib.parse import urlparse

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


def set_cover(nid, src_img, cr='Foto: La Guayaba Ilustrada'):
    """Pone la foto como portada de un borrador o de una nota ya publicada."""
    path = f'drafts/{nid}.json'
    if os.path.exists(path):
        n = load(path); old = n.get('img', '')
        n['img'] = src_img; n['cr'] = cr
        save(path, n)
    else:
        js = open('posts.js', encoding='utf-8').read()
        lines = js.split('\n')
        for i, ln in enumerate(lines):
            if f'"id": "{nid}"' in ln or f"id:'{nid}'" in ln:
                m = re.search(r'("img": "|img:\')([^"\']+)', ln)
                old = m.group(2) if m else ''
                ln = ln.replace(old, src_img, 1) if old else ln
                ln = re.sub(r'"cr": "[^"]*"', '"cr": "' + cr + '"', ln)
                lines[i] = re.sub(r"cr:'[^']*'", "cr:'" + cr + "'", ln)
                break
        else:
            return False
        open('posts.js', 'w', encoding='utf-8').write('\n'.join(lines))
    if old.startswith('assets/work/nota-') and '-foto-src' not in old and old != src_img and os.path.exists(old):
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


REHACER = 'drafts/.rehacer_reel.json'   # notas publicadas a las que hay que rehacerles el Reel (lo pide Claude)


REENVIAR = 'drafts/.reenviar_reel.json'   # Reels ya armados que hay que volver a mandar a Telegram (sin rehacerlos)


def enviar_reel(nid, titulo=None):
    out = f'assets/ig/{nid}/reel.mp4'
    if not os.path.exists(out):
        tg('sendMessage', chat_id=CHAT, text=f'⚠️ No encontré el Reel de {nid}.')
        return
    n, _ = note_get(nid)
    with open(out, 'rb') as f:
        r = tg('sendVideo', files={'video': f}, chat_id=CHAT, supports_streaming='true', width=1080, height=1920,
               caption=f'🎬 Reel: {(titulo or (n or {}).get("t") or nid)[:120]}\nSi te gusta, súbelo con el botón.',
               reply_markup={'inline_keyboard': [[{'text': '📲 Subir este Reel a Instagram', 'callback_data': f'subreel:{nid}'}]]})
    if r.get('ok'):
        remember(r['result']['message_id'], nid)


def rehacer_reel(nid):
    """Vuelve a armar el Reel de una nota ya publicada y lo manda a Telegram con botón para subirlo."""
    n, _ = note_get(nid)
    igp = f'drafts/ig/{nid}.json'
    if not n or not (os.path.exists(igp) or n.get('ig')):
        tg('sendMessage', chat_id=CHAT, text=f'⚠️ No encontré la nota {nid} para rehacer su Reel.')
        return
    if os.path.exists(igp):
        n['ig'] = load(igp)
    for k in ('ig1', 'ig2'):
        if n['ig'].get(k):
            n[k] = n['ig'][k]
    try:
        out = build_reel(n)
    except Exception as e:
        tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude rehacer el Reel de {nid}: {str(e)[:200]}')
        return
    with open(out, 'rb') as f:
        r = tg('sendVideo', files={'video': f}, chat_id=CHAT, supports_streaming='true', width=1080, height=1920,
               caption=f'🎬 Reel nuevo: {n.get("t", nid)[:120]}\nSi te gusta, súbelo con el botón (el anterior lo borras tú en Instagram).',
               reply_markup={'inline_keyboard': [[{'text': '📲 Subir este Reel a Instagram', 'callback_data': f'subreel:{nid}'}]]})
    if r.get('ok'):
        remember(r['result']['message_id'], nid)


def ig_command(nid, mid, kind='carousel'):
    """Sube a Instagram el carrusel (o el Reel) de una nota ya publicada."""
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
    if kind == 'reel':
        try:
            build_reel(n)
        except Exception as e:
            reply(mid, f'⚠️ No pude armar el Reel: {e}')
            return
    queue_instagram(n, kind)
    reply(mid, ('🎬 Va. Armé el Reel' if kind == 'reel' else '📲 Va. Armé el carrusel')
          + ' y lo subo a Instagram en unos minutos. Te aviso aquí cuando esté publicado.')
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
    if (vm or yt) and nid and not is_photo:
        kind, vid = ('vm', vm.group(1)) if vm else ('yt', yt.group(1))
        if not video_embebible(kind, vid):
            reply(mid, '⚠️ Ese video no se puede ver fuera de su página original (su dueño lo bloqueó), '
                       'así que no lo pongo en la nota. Si tienes el mismo video en YouTube, mándame ese link.')
            return
    if vm and nid and not is_photo:
        n, put = note_get(nid)
        if n:
            n['vm'] = vm.group(1); n.pop('yt', None)
            vt = vimeo_thumb(n['vm'])
            if vt:
                n['vt'] = vt
            put(n)
            reply(mid, '🎬 Listo, ese video de Vimeo queda en la nota de la web. Te mando imágenes del video para Instagram.')
            video_cands(nid)
            return
    if yt and nid and not is_photo:
        n, put = note_get(nid)
        if n:
            n['yt'] = yt.group(1); n.pop('vm', None)
            put(n)
            reply(mid, '🎬 Listo, ese video de YouTube queda como portada de la nota. Te mando imágenes del video para Instagram.')
            video_cands(nid)
            return
    ig_word = len(text) < 40 and re.search(r'\b(instagram|ig|reel)\b', text, re.I)
    if not nid and (is_photo or ig_word):
        nid = last_note()   # en iPhone a veces no se puede responder: se usa la última nota
    if nid:
        set_last(nid)
    if not is_photo and re.fullmatch(r'\s*sin\s+video\s*[.!]*\s*', text, re.I):
        nid = nid or last_note()
        n, put = note_get(nid) if nid else (None, None)
        if not n:
            reply(mid, 'No encuentro la nota. Respóndele "sin video" a la nota.'); return
        for k in ('yt', 'vm', 'vt', 'th', 'mp4', 'auto_video'):
            n.pop(k, None)
        n['sin_video'] = True
        if n.get('ig1') and os.path.exists(f'drafts/{nid}.json') and '-foto-src' in n['ig1'] and n['ig1'].endswith('v.webp'):
            n.pop('ig1', None)
        put(n)
        reply(mid, '👌 Quité el video. La nota usa la foto de portada.')
        return
    if not is_photo and re.fullmatch(r'\s*(busca\s+)?fotos?\s*[.!?]*\s*', text, re.I):
        nid = nid or last_note()
        path = f'drafts/{nid}.json' if nid else ''
        if not nid or not os.path.exists(path):
            reply(mid, 'Esa nota ya está publicada o no la encuentro. Respóndele "fotos" a una nota pendiente.')
            return
        reply(mid, '🔎 Buscando fotos reales en la fuente…')
        n = load(path); poner_candidatas(n); save(path, n)
        send_selector(n); PREVIEW.add(nid)
        return
    if not is_photo and re.search(r'\b(otras?|otros?|nuevas?|diferentes?|mejor(es)?)\s+(fotos?|im[aá]gen(es)?)\b|'
                                  r'\bcambia(r|le)?\s+(la\s+)?(foto|imagen)\b|\bbusca\s+(otra|otras|más|mas)\b', text, re.I):
        nid = nid or last_note()
        path = f'drafts/{nid}.json' if nid else ''
        if not nid or not os.path.exists(path):
            reply(mid, 'Esa nota ya está publicada o no la encuentro. Respóndele "otra foto" a una nota pendiente.')
            return
        reply(mid, '🔎 Va. Busco fotos en otros medios que publicaron la misma noticia…')
        otra_foto(nid, mid)
        return
    if nid and not is_photo and ig_word:
        ig_command(nid, mid, 'reel' if re.search(r'\breel\b', text, re.I) else 'carousel')
        return
    if text.strip().lower() in ('/start', '/help', '/ayuda'):
        reply(mid, 'Hola. Aquí te llegan las notas para aprobar.\n\n'
              '• Mándame un link o un texto con lo que quieres que se publique y lo redacto en mi próxima vuelta.\n'
              '• Fotos para el carrusel: responde a la nota con 1 o 2 fotos. Si la nota es video, las fotos son solo para Instagram; si no, la primera también es la portada de la web.\n'
              '• Para poner un video de YouTube como portada, responde a la nota con el link del video.\n'
              '• Para subir a Instagram una nota que ya está en la web, responde a la nota con "instagram" (carrusel) o "reel".\n'
              '• Las fotos de la nota original te llegan numeradas: usa los botones para escoger portada y lámina 2. Para buscarlas otra vez, responde "fotos".\n'
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
    if not data.get('info'):
        data['info'] = info_auto(n)
    if n.get('ajuste'):
        data['ajuste'] = n['ajuste']
    carrusel.make(data, out)
    n['_data'] = data
    return [f'{out}/{i}.jpg' for i in (1, 2, 3, 4) if os.path.exists(f'{out}/{i}.jpg')]


ANIM = 'drafts/ig/.animado.json'   # {'ultimo': 'AAAA-MM-DD', 'id': nota, 'previo': ...}


def build_anim(n):
    """Carrusel animado (naranja) en assets/ig/<id>/anim/1.mp4 ... ; el fijo rosa queda de respaldo."""
    sys.path.insert(0, 'scripts')
    import carrusel_video
    build_carousel(n)
    out = f'assets/ig/{n["id"]}/anim'
    import shutil
    shutil.rmtree(out, ignore_errors=True)
    vids = carrusel_video.make(n['_data'], out)
    for f in glob.glob(f'{out}/*.jpg'):
        os.remove(f)
    return vids


def toca_animado(n):
    """Una vez por semana (mínimo) va un carrusel animado. Se elige la nota que más vale la pena:
    la que el redactor marcó como 'destacada', de lunes a jueves (mejores días de alcance),
    y si pasan 7 días sin animado, la siguiente nota con foto real."""
    if 'animado' in n:
        return bool(n['animado'])
    if not n.get('ig') or '-foto' not in (n.get('ig1') or n.get('img') or ''):
        return False
    st = load(ANIM) if os.path.exists(ANIM) else {}
    hoy = datetime.now(timezone(timedelta(hours=-6)))
    try:
        dias = (hoy.date() - datetime.strptime(st['ultimo'], '%Y-%m-%d').date()).days
    except Exception:
        dias = 99
    if dias >= 7:
        return True
    return dias >= 3 and bool(n.get('destacada')) and hoy.weekday() <= 3


def reservar_animado(nid, si=True):
    """Apunta (o devuelve) el turno semanal del carrusel animado."""
    os.makedirs('drafts/ig', exist_ok=True)
    st = load(ANIM) if os.path.exists(ANIM) else {}
    if si:
        if st.get('id') != nid:
            st = {'ultimo': datetime.now(timezone(timedelta(hours=-6))).strftime('%Y-%m-%d'), 'id': nid,
                  'previo': st.get('ultimo')}
    elif st.get('id') == nid:
        st = {'ultimo': st.get('previo'), 'id': None} if st.get('previo') else {}
    save(ANIM, st)


def info_auto(n):
    """Si el redactor no mandó 'info', usa el contexto de la nota (párrafos 2 y 3) recortado en frases completas."""
    out, total = [], 0
    for p in n.get('b', [])[1:3]:
        frases, txt = re.split(r'(?<=[.!?])\s+', p.strip()), ''
        for f in frases:
            if total + len(txt) + len(f) > 520:
                break
            txt += (' ' if txt else '') + f
        if txt:
            out.append(txt); total += len(txt)
    return out


def build_reel(n):
    """Reel vertical con voz, subtítulos, fotos y clips del video de la campaña -> assets/ig/<id>/reel.mp4"""
    sys.path.insert(0, 'scripts')
    import reel
    build_carousel(n)  # deja listas las fotos y los textos
    data = dict(n['_data'])
    data['src'] = n.get('src', '')
    data['guion'] = n.get('guion') or n['ig'].get('guion', '')
    data['mp4'] = n.get('mp4', '')
    data['yt'], data['vm'] = n.get('yt', ''), n.get('vm', '')
    data['videos'] = n.get('videos') or n['ig'].get('videos') or []   # videos de apoyo (otras campañas, la marca, el producto)
    out = f'assets/ig/{n["id"]}/reel.mp4'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import io, contextlib, traceback
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            reel.make(data, out)
    except Exception:
        with open('drafts/.errores.log', 'a') as f:
            f.write(f'{datetime.now().isoformat()} reel {n["id"]}\n{buf.getvalue()[-3000:]}\n{traceback.format_exc()}\n')
        raise
    finally:
        sys.stderr.write(buf.getvalue())
        with open('drafts/.reel.log', 'w') as f:      # último Reel: qué voz, qué videos y qué tramos usó
            f.write(f'{datetime.now().isoformat()} {n["id"]}\n{buf.getvalue()[-4000:]}\n')
    return out


REEL = 'drafts/ig/.reel.json'   # {'ts': segundos, 'id': nota, 'previo': ts}
CADA_REEL = 90 * 60                # cada nota (una cada 2 horas) lleva su Reel; 30 min de holgura


def toca_reel(n):
    """Reel cada 2 horas: la siguiente nota que traiga video de la campaña (sin video no hay Reel)."""
    if 'reel' in n:
        return bool(n['reel'])
    ig = n.get('ig') or {}
    if not ig or not (n.get('mp4') or n.get('yt') or n.get('vm') or ig.get('videos')
                      or any(e.get('video') for e in ig.get('escenas') or [])):
        return False
    st = load(REEL) if os.path.exists(REEL) else {}
    return time.time() - float(st.get('ts') or 0) >= CADA_REEL


def reservar_reel(nid, si=True):
    os.makedirs('drafts/ig', exist_ok=True)
    st = load(REEL) if os.path.exists(REEL) else {}
    if si:
        st = {'ts': time.time(), 'id': nid, 'previo': st.get('ts')}
    elif st.get('id') == nid:
        st = {'ts': st.get('previo') or 0, 'id': None}
    save(REEL, st)


def hora_de_salir():
    """Los Reels salen en punto: de 8 a 22 h, cada 2 horas (hora de Ciudad de México)."""
    h = datetime.now(timezone(timedelta(hours=-6))).hour
    return 8 <= h <= 22 and h % 2 == 0


def send_reel(n):
    try:
        out = f'assets/ig/{n["id"]}/reel.mp4'
        if not (n.get('reel_listo') and os.path.exists(out)):
            out = build_reel(n)
    except Exception as e:
        print('Reel:', e, file=sys.stderr)
        tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude armar el Reel: {str(e)[:200]}')
        return False
    with open(out, 'rb') as f:
        import voz
        aviso = ''
        if os.environ.get('ELEVENLABS_API_KEY') and voz.ELEVEN_ERROR[0]:
            aviso = f'\n⚠️ ElevenLabs no respondió ({voz.ELEVEN_ERROR[0][:120]}), usé la voz de respaldo.'
        r = tg('sendVideo', files={'video': f}, chat_id=CHAT, supports_streaming='true', width=1080, height=1920,
               caption='🎬 Reel para Instagram (sale junto con el carrusel al publicar)' + aviso)
    if r.get('ok'):
        remember(r['result']['message_id'], n['id'])
    return bool(r.get('ok'))


def send_carousel(n):
    animado = bool(n.get('animado'))
    try:
        files = build_anim(n) if animado else build_carousel(n)
    except Exception as e:
        if animado:
            import traceback, shutil
            print('Animado:', e, file=sys.stderr)
            with open('drafts/.errores.log', 'a') as f:
                f.write(f'{datetime.now().isoformat()} animado {n["id"]} ffmpeg={shutil.which("ffmpeg")}\n{traceback.format_exc()}\n')
            n['animado'] = False; animado = False
            try:
                files = build_carousel(n)
            except Exception as e2:
                tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude armar el carrusel de Instagram: {e2}')
                return False
        else:
            tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude armar el carrusel de Instagram: {e}')
            return False
    media, fh = [], {}
    for i, f in enumerate(files):
        fh[f'f{i}'] = open(f, 'rb')
        item = {'type': 'video' if animado else 'photo', 'media': f'attach://f{i}'}
        if animado:
            item.update({'width': 1080, 'height': 1350, 'supports_streaming': True})
        if i == 0:
            aviso = ('⚠️ Este carrusel no tiene foto. Respóndele a la nota con 1 o 2 fotos antes de publicar.\n\n'
                     if NOFOTO.get(n['id']) else '')
            titulo = ('🎬 Carrusel ANIMADO para Instagram (el de esta semana)' if animado
                      else '📲 Carrusel para Instagram')
            item['caption'] = (aviso + titulo + '\n\n' + n['ig'].get('caption', ''))[:1000]
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


def queue_instagram(n, kind='carousel'):
    q = load(IGQ) if os.path.exists(IGQ) else []
    item = {'id': n['id'], 'caption': n['ig'].get('caption', ''), 'reply': n.get('tg'), 'kind': kind}
    if kind == 'carousel' and n.get('animado') and os.path.exists(f'assets/ig/{n["id"]}/anim/1.mp4'):
        item['animado'] = True
    q.append(item)
    save(IGQ, q)


def es_video(n):
    return bool(n.get('yt') or n.get('vm'))


def mp4_de_fuente(src):
    """Video MP4 directo de la campaña (Ads of the World lo trae así). Se usa en la web y en el Reel."""
    sys.path.insert(0, 'scripts')
    import fuentes
    try:
        for u in fuentes.mp4s_de_pagina(src):
            r = requests.head(u, headers=fuentes.UA, timeout=20, allow_redirects=True)
            if r.status_code == 200 and 'video' in r.headers.get('content-type', 'video'):
                return u
    except Exception as e:
        print('MP4 de la fuente:', e, file=sys.stderr)
    return None


def otra_foto(nid, mid):
    """Sergio pide otra imagen: se buscan otras notas del mismo tema en la web y se juntan sus fotos."""
    sys.path.insert(0, 'scripts')
    import fuentes
    path = f'drafts/{nid}.json'
    n = load(path)
    antes = set(n.get('cands', []))
    nuevas_fuentes = [u for u in fuentes.otras_fuentes(n) if u not in (n.get('fuentes') or [])]
    n['fuentes'] = (list(n.get('fuentes') or []) + nuevas_fuentes)[:8]
    # la foto actual va a "evitar" para que salgan otras primero
    poner_candidatas(n)
    nuevas = [c for c in n.get('cands', []) if c not in antes]
    save(path, n)
    if nuevas:
        n['cands'] = nuevas + [c for c in n['cands'] if c not in nuevas]
        aplicar_fotos(n); save(path, n)
        reply(mid, f'✅ Encontré {len(nuevas)} foto(s) nueva(s) en otros medios. Puse la mejor de portada; '
                   'abajo te mando todas para que escojas.')
        send_selector(n); PREVIEW.add(nid)
    else:
        save(f'inbox/otra-foto-{nid}.json', {'tipo': 'texto', 'nota': nid, 'urgente': True, 'fecha': int(time.time()),
             'texto': 'Sergio pide OTRA IMAGEN para esta nota. Busca 2 o 3 notas de otros medios sobre la misma noticia '
                      'que traigan fotos reales del producto o la campaña y agrégalas al campo "fuentes" del borrador '
                      '(lista de URLs). Luego quita "cands" y "tg" del borrador para que el bot vuelva a buscar fotos.'})
        reply(mid, '😕 No encontré fotos nuevas que sirvan (en alta calidad y sin letras). Ya le pedí al redactor que busque '
                   'otras notas de esta noticia; en su siguiente vuelta (máx. 1 hora) te llega con fotos nuevas. '
                   'Si tienes una foto, respóndele aquí a la nota y la uso de inmediato.')


def hacer_tomas(n):
    """Hoja de tomas del video de la campaña (drafts/tomas/<id>.jpg + .json): el redactor la mira para decir
    qué toma va con cada frase de la voz del Reel."""
    if os.path.exists(f'drafts/tomas/{n["id"]}.json'):
        return
    sys.path.insert(0, 'scripts')
    try:
        import tomas
        tomas.de_url(n['mp4'], n['id'])
    except Exception as e:
        print('Tomas del video:', e, file=sys.stderr)


def poner_candidatas(n, solo_video=False):
    """Busca fotos reales (fuente y/o video) y deja puestas la 1 y la 2 por defecto."""
    sys.path.insert(0, 'scripts')
    import fuentes
    if not solo_video and not es_video(n) and not n.get('sin_video'):
        try:
            v = fuentes.video_de_pagina(n.get('src', ''))
        except Exception as e:
            v = None; print('Video de la fuente:', e, file=sys.stderr)
        if v and not video_embebible(*v):
            v = None   # el video solo se puede ver en su sitio original: mejor no ponerlo
        if v:
            n['yt' if v[0] == 'yt' else 'vm'] = v[1]; n['auto_video'] = True
            if v[0] == 'vm':
                n['vt'] = vimeo_thumb(v[1]) or ''
        elif not n.get('mp4'):
            m = mp4_de_fuente(n.get('src', ''))
            if m:
                n['mp4'] = m; n['auto_video'] = True
    if n.get('mp4') and not solo_video:
        hacer_tomas(n)
    reg_path = 'drafts/.huellas.json'
    reg = load(reg_path) if os.path.exists(reg_path) else {}
    reg = {k: v for k, v in reg.items() if v != n['id']}
    try:
        nuevas = fuentes.candidatas(n, solo_video=solo_video, registro=reg)
    except Exception as e:
        print('Fotos de la fuente:', e, file=sys.stderr)
        nuevas = []
    save(reg_path, dict(list(reg.items())[-600:]))
    c = nuevas + [x for x in n.get('cands', []) if x not in nuevas] if solo_video else nuevas
    propia = n.get('img', '').split('?')[0]
    if not solo_video and '-foto' in propia and '-foto-src' not in propia and os.path.exists(propia):
        c = [propia] + c   # una foto que ya mandó Sergio va primero
    c = [x for x in c if os.path.exists(x)][:6]
    n['cands'] = c
    aplicar_fotos(n)
    return c


def aplicar_fotos(n):
    """Pone la foto 1 de portada (web y carrusel) y la 2 en la lámina 2; si solo hay una, se repite."""
    sys.path.insert(0, 'scripts')
    import fuentes
    c = n.get('cands', [])
    if c:
        cr = 'Foto: ' + (fuentes.credito(n.get('src', '')) or 'cortesía')
        n['ig1'] = c[0]
        if c[0] != n.get('img', '').split('?')[0]:
            n['img'] = c[0]; n['cr'] = cr
        n['ig2'] = c[1] if len(c) > 1 else c[0]   # si no hay otra buena, se repite (mejor que una mala)


def limpiar_repetidas():
    """Una foto que aparece en varias notas es publicidad o adorno del sitio: se quita de todas."""
    sys.path.insert(0, 'scripts')
    import fuentes
    from PIL import Image
    hs = []
    for f in glob.glob('drafts/*.json'):
        n = load(f)
        for c in n.get('cands', []):
            try:
                hs.append((f, c, fuentes._huella(Image.open(c).convert('RGB'))))
            except Exception:
                pass
    malas = set()
    for i, (f1, c1, h1) in enumerate(hs):
        for f2, c2, h2 in hs[i + 1:]:
            if f1 != f2 and fuentes._parecidas(h1, h2):
                malas.update({c1, c2})
    cambiadas = []
    for f in glob.glob('drafts/*.json'):
        n = load(f)
        if any(c in malas for c in n.get('cands', [])):
            viejas = n['cands']
            n['cands'] = [c for c in viejas if c not in malas]
            for k in ('ig1', 'ig2'):
                if n.get(k) in malas: n.pop(k)
            if n.get('img') in malas:
                base = f'assets/work/nota-{n["id"]}.webp'
                n['img'] = n['cands'][0] if n['cands'] else (base if os.path.exists(base) else n['img'])
            aplicar_fotos(n); save(f, n); cambiadas.append(n['id'])
    return cambiadas


def video_cands(nid):
    """Al agregar un video a un borrador: suma sus imágenes a las opciones y las pone en el carrusel."""
    path = f'drafts/{nid}.json'
    if not os.path.exists(path):
        return
    n = load(path)
    poner_candidatas(n, solo_video=True)
    save(path, n)
    send_selector(n)
    PREVIEW.add(nid)


def send_selector(n):
    """Manda las fotos encontradas numeradas y los botones para escoger portada y lámina 2."""
    c = [x for x in n.get('cands', []) if os.path.exists(x)]
    if not c:
        tg('sendMessage', chat_id=CHAT, text='🔎 No encontré fotos buenas en la fuente de esta nota. Mándame 1 o 2 tuyas.')
        return
    media, fh = [], {}
    for i, f in enumerate(c):
        fh[f'c{i}'] = open(f, 'rb')
        it = {'type': 'photo', 'media': f'attach://c{i}'}
        if i == 0:
            it['caption'] = (('🎬 Encontré el video en la nota original y ya quedó como portada en la web '
                              '(si no lo quieres, responde "sin video").\n\n' if n.get('auto_video') else '')
                             + f'🖼 Fotos reales de la nota (1 a {len(c)}).\n'
                             + ('Puse la 1 en la portada del carrusel' if es_video(n) else 'Puse la 1 de portada')
                             + (' y la 2 en la segunda lámina.' if len(c) > 1 else '.'))
        media.append(it)
    if len(media) == 1:
        with open(c[0], 'rb') as f:
            r = tg('sendPhoto', files={'photo': f}, chat_id=CHAT, caption=media[0].get('caption', ''))
        r = {'ok': r.get('ok'), 'result': [r['result']] if r.get('ok') else []}
    else:
        r = tg('sendMediaGroup', files=fh, chat_id=CHAT, media=media)
    for f in fh.values():
        f.close()
    for m in r.get('result', []):
        remember(m['message_id'], n['id'])
    nums = range(1, len(c) + 1)
    kb = [[{'text': f'Portada {k}', 'callback_data': f'cp:{n["id"]}:{k}'} for k in nums],
          [{'text': f'Lámina 2 · {k}', 'callback_data': f'c2:{n["id"]}:{k}'} for k in nums]]
    r2 = tg('sendMessage', chat_id=CHAT, text='¿Quieres otras? Elige aquí:', reply_markup={'inline_keyboard': kb})
    if r2.get('ok'):
        remember(r2['result']['message_id'], n['id'])


def elegir(cq, data):
    """Botones Portada k / Lámina 2 · k."""
    tipo, nid, k = data.split(':')
    path = f'drafts/{nid}.json'
    if not re.fullmatch(r'[a-z0-9-]+', nid) or not os.path.exists(path):
        tg('answerCallbackQuery', callback_query_id=cq['id'], text='Esa nota ya se publicó.')
        return
    n = load(path); c = n.get('cands', []); k = int(k)
    if not (1 <= k <= len(c)):
        return
    f = c[k - 1]
    if tipo == 'cp':
        sys.path.insert(0, 'scripts'); import fuentes
        n['ig1'] = f; n['img'] = f; n['cr'] = 'Foto: ' + (fuentes.credito(n.get('src', '')) or 'cortesía')
        txt = f'✅ Foto {k} de portada'
    else:
        n['ig2'] = f; txt = f'✅ Foto {k} en la lámina 2'
    save(path, n)
    tg('answerCallbackQuery', callback_query_id=cq['id'], text=txt + '. Te mando el carrusel.')
    PREVIEW.add(nid)


AJ_PASO = 0.04   # 4% del cuadro por toque


def teclado_ajuste(nid):
    b = lambda t, m: {'text': t, 'callback_data': f'ajm:{nid}:{m}'}
    return {'inline_keyboard': [[b('⬅️', 'l'), b('⬆️', 'u'), b('⬇️', 'd'), b('➡️', 'r')],
                                [b('🔍 Acercar', 'zi'), b('🔎 Alejar', 'zo'), b('↺ Original', 'x')],
                                [{'text': '🔄 Buscar otra foto', 'callback_data': f'alt:{nid}'}],
                                [b('✅ Listo', 'ok')]]}


def ajuste_portada(cq, data):
    """Botones para mover y acercar la foto de la portada del carrusel hasta que quede perfecta."""
    _, nid, mov = data.split(':')
    path = f'drafts/{nid}.json'
    if not re.fullmatch(r'[a-z0-9-]+', nid) or not os.path.exists(path):
        tg('answerCallbackQuery', callback_query_id=cq['id'], text='Esa nota ya se publicó.')
        return
    n = load(path)
    m = cq.get('message') or {}
    if mov == 'ok':
        tg('answerCallbackQuery', callback_query_id=cq['id'], text='✅ Encuadre guardado. Así sale en Instagram.')
        tg('editMessageReplyMarkup', chat_id=CHAT, message_id=m.get('message_id'), reply_markup={'inline_keyboard': []})
        if n.get('animado'):
            PREVIEW.add(nid)
        return
    a = dict(n.get('ajuste') or {'dx': 0, 'dy': 0, 'z': 1.0})
    antes = dict(a)
    # la flecha mueve la FOTO hacia ese lado (⬅️ = lo que se ve se recorre a la izquierda)
    if mov == 'l': a['dx'] = round(max(-0.5, a['dx'] - AJ_PASO), 3)
    if mov == 'r': a['dx'] = round(min(0.5, a['dx'] + AJ_PASO), 3)
    if mov == 'u': a['dy'] = round(max(-0.5, a['dy'] - AJ_PASO), 3)
    if mov == 'd': a['dy'] = round(min(0.5, a['dy'] + AJ_PASO), 3)
    if mov == 'zi': a['z'] = round(min(2.0, a['z'] * 1.08), 3)
    if mov == 'zo': a['z'] = round(max(0.8, a['z'] / 1.08), 3)
    if mov == 'x': a = {'dx': 0, 'dy': 0, 'z': 1.0}
    n['ajuste'] = a
    save(path, n)
    files = build_carousel(n)
    pasos = lambda v: int(round(v / AJ_PASO))
    estado = (f"↔️ {pasos(a['dx']):+d}   ↕️ {pasos(a['dy']):+d}   🔍 {int(round(a['z'] * 100))}%"
              if a != {'dx': 0, 'dy': 0, 'z': 1.0} else 'Encuadre automático')
    cap = f'🎯 Mueve la foto hasta que lo importante quede al centro.\n{estado}'
    with open(files[0], 'rb') as f:
        r = tg('editMessageMedia', files={'p': f}, chat_id=CHAT, message_id=m.get('message_id'),
               media={'type': 'photo', 'media': 'attach://p', 'caption': cap}, reply_markup=teclado_ajuste(nid))
    if r.get('ok'):
        tg('answerCallbackQuery', callback_query_id=cq['id'], text=estado)
    elif a == antes:
        tg('answerCallbackQuery', callback_query_id=cq['id'], text='Ya está al límite en esa dirección.')
    else:   # si no se pudo cambiar la imagen del mensaje, se manda una nueva
        tg('answerCallbackQuery', callback_query_id=cq['id'], text=estado)
        with open(files[0], 'rb') as f:
            r = tg('sendPhoto', files={'photo': f}, chat_id=CHAT, caption=cap, reply_markup=teclado_ajuste(nid))
        if r.get('ok'):
            remember(r['result']['message_id'], nid)


def send_pending():
    global changed
    for path in sorted(glob.glob('drafts/*.json')):
        n = load(path)
        if n.get('tg'):
            continue
        if 'cands' not in n:
            poner_candidatas(n); n['cands_v'] = 2
            save(path, n)
            for otra in limpiar_repetidas():
                if otra != n['id']:
                    PREVIEW.add(otra)
            n = load(path)
        if n.get('ig') and not n.get('urgente') and not hora_de_salir():
            # se arma el Reel antes y se manda a Telegram en punto (8, 10, 12, 14, 16, 18, 20 y 22 h)
            if not n.get('reel_listo'):
                if 'reel' not in n and toca_reel(n):
                    n['reel'] = True
                    reservar_reel(n['id'])
                if n.get('reel'):
                    try:
                        build_reel(n)
                    except Exception as e:
                        print('Reel (previo):', e, file=sys.stderr)
                        n['reel'] = False
                        reservar_reel(n['id'], False)
                n['reel_listo'] = True
                n.pop('_data', None)
                save(path, n)
                changed = True
            continue
        cap = (f'<b>Nota nueva para revisar</b> · {esc(n["k"])}\n🖼 <i>Esta es la portada que tendrá en la web.</i>\n\n'
               f'<b>{esc(n["t"])}</b>\n<i>{esc(n["x"])}</i>')
        if n.get('auto_video'):
            cap += '\n\n🎬 Lleva el video de la nota original en la web. Si no lo quieres, responde "sin video".'
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
        if n.get('ig'):
            if 'animado' not in n and toca_animado(n):
                n['animado'] = True
                reservar_animado(n['id'])
            if send_carousel(n):
                kb.append([{'text': '📲 Web + Instagram', 'callback_data': 'pig:' + n['id']}])
                kb.append([{'text': '🖼 Mejor fijo (rosa)' if n.get('animado') else '🎬 Hacerlo animado',
                            'callback_data': 'anim:' + n['id']}])
                if 'reel' not in n and toca_reel(n):
                    n['reel'] = True
                    reservar_reel(n['id'])
                if n.get('reel') and not send_reel(n):
                    n['reel'] = False
                if n.get('mp4'):
                    kb.append([{'text': '🎞 Quitar el Reel' if n.get('reel') else '🎞 Agregar Reel',
                                'callback_data': 'reel:' + n['id']}])
            kb.append([{'text': '🎯 Ajustar encuadre de la portada', 'callback_data': 'aj:' + n['id']}])
            kb.append([{'text': '🔄 Otras fotos', 'callback_data': 'alt:' + n['id']}])
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
    for k in ('g', 'yt', 'vm', 'vt', 'th', 'mp4'):
        if n.get(k):
            post[k] = n[k]
    if n.get('src'):
        post['src'] = n['src']
        if n.get('sn'):
            post['sn'] = n['sn']
    if n.get('ig'):
        os.makedirs('drafts/ig', exist_ok=True)
        ig = dict(n['ig'])
        for k in ('ig1', 'ig2'):
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
        if (cq.get('data') or '').startswith('subreel:'):
            sid = cq['data'].split(':', 1)[1]
            n, _ = note_get(sid)
            if n and os.path.exists(f'assets/ig/{sid}/reel.mp4') and os.path.exists(f'drafts/ig/{sid}.json'):
                n['ig'] = load(f'drafts/ig/{sid}.json')
                n['tg'] = (cq.get('message') or {}).get('message_id')
                queue_instagram(n, 'reel')
                mark(cq, '📲 Va. En unos minutos sale el Reel en Instagram; te aviso aquí.')
            else:
                tg('answerCallbackQuery', callback_query_id=cq['id'], text='No encontré ese Reel.')
            changed = True
            continue
        if re.fullmatch(r'ajm:[a-z0-9-]+:(l|r|u|d|zi|zo|x|ok)', cq.get('data') or ''):
            ajuste_portada(cq, cq['data']); changed = True
            continue
        if re.fullmatch(r'(cp|c2):[a-z0-9-]+:\d', cq.get('data') or ''):
            elegir(cq, cq['data']); changed = True
            continue
        accion, _, nid = (cq.get('data') or '').partition(':')
        if not re.fullmatch(r'[a-z0-9-]+', nid or ''):
            continue
        path = f'drafts/{nid}.json'
        if not os.path.exists(path):
            tg('answerCallbackQuery', callback_query_id=cq['id'], text='Esa nota ya se había procesado.')
            continue
        n = load(path)
        if accion == 'anim':
            n['animado'] = not n.get('animado')
            reservar_animado(nid, n['animado'])
            n.pop('tg', None)
            save(path, n)
            mark(cq, '🎬 Va animado. Te mando la nota otra vez con el carrusel en movimiento.' if n['animado']
                 else '🖼 Va fijo en rosa. Te mando la nota otra vez.')
            changed = True
            continue
        if accion == 'reel':
            if not n.get('reel') and not n.get('mp4'):
                tg('answerCallbackQuery', callback_query_id=cq['id'], show_alert='true',
                   text='Esta nota no trae video de la campaña, y el Reel solo se arma con video.')
                continue
            n['reel'] = not n.get('reel')
            reservar_reel(nid, n['reel'])
            if n['reel']:
                n.pop('tg', None)
                save(path, n)
                mark(cq, '🎞 Va con Reel. Te mando la nota otra vez con el video (tarda 1 o 2 minutos).')
            else:
                save(path, n)
                tg('answerCallbackQuery', callback_query_id=cq['id'], text='🎞 Listo, esta nota sale sin Reel.')
            changed = True
            continue
        if accion == 'aj':
            tg('answerCallbackQuery', callback_query_id=cq['id'])
            files = build_carousel(n)
            with open(files[0], 'rb') as f:
                r = tg('sendPhoto', files={'photo': f}, chat_id=CHAT, reply_markup=teclado_ajuste(nid),
                       caption='🎯 Mueve la foto hasta que lo importante quede al centro. Cada toque la recorre un poco.')
            if r.get('ok'):
                remember(r['result']['message_id'], nid)
            changed = True
            continue
        if accion == 'alt':
            if len(n.get('cands', [])) > 1:
                tg('answerCallbackQuery', callback_query_id=cq['id'], text='Te mando las fotos que encontré.')
                send_selector(n)
            else:
                tg('answerCallbackQuery', callback_query_id=cq['id'], text='Busco fotos en otros medios…')
                otra_foto(nid, (cq.get('message') or {}).get('message_id'))
            changed = True
            continue
        if accion in ('pub', 'pig', 'prl', 'pall'):
            publish(n)
            set_last(nid)
            os.remove(path)
            kinds = {'pig': ['carousel'], 'prl': ['reel'], 'pall': ['carousel', 'reel']}.get(accion, [])
            if accion == 'pig' and n.get('reel'):
                kinds = ['carousel', 'reel']
            if kinds and n.get('ig'):
                try:
                    build_carousel(n)  # rehace las láminas con las fotos más recientes
                    if n.get('animado') and 'carousel' in kinds:
                        try:
                            build_anim(n)
                        except Exception as e:
                            print('Animado:', e, file=sys.stderr); n['animado'] = False
                    if 'reel' in kinds and not os.path.exists(f'assets/ig/{n["id"]}/reel.mp4'):
                        try:
                            build_reel(n)
                        except Exception as e:
                            print('Reel:', e, file=sys.stderr); kinds.remove('reel')
                except Exception as e:
                    print('Carrusel/Reel:', e, file=sys.stderr)
                nombre = ' y '.join({'carousel': 'el carrusel', 'reel': 'el Reel'}[k] for k in kinds)
                if NOFOTO.get(n['id']):
                    mark(cq, f'✅ Publicada en la web. No había fotos, así que NO subí {nombre} a Instagram. '
                             'Mándame 1 o 2 fotos y después escribe "instagram".')
                elif os.environ.get('IG_TOKEN'):
                    for k in kinds:
                        queue_instagram(n, k)
                    mark(cq, f'✅ Publicada en la web. En unos minutos sale {nombre} en Instagram.')
                else:
                    mark(cq, '✅ Publicada en la web. Instagram todavía no está conectado.')
            else:
                mark(cq, '✅ Publicada. Te aviso aquí con el link en cuanto ya se vea en la página (1 a 3 minutos).')
            pend = load(VERIFY) if os.path.exists(VERIFY) else []
            pend.append({'id': nid, 'reply': (cq.get('message') or {}).get('message_id'), 't': time.time()})
            save(VERIFY, pend)
            print('Publicada:', nid)
        elif accion == 'del':
            os.remove(path)
            if n.get('animado'):
                reservar_animado(nid, False)
            if n.get('reel'):
                reservar_reel(nid, False)
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


def publish_reel(item, api, uid, tok, site):
    import hashlib
    path = f'assets/ig/{item["id"]}/reel.mp4'
    local = hashlib.md5(open(path, 'rb').read()).hexdigest()
    url = f'{site}/{path}'
    for _ in range(40):  # espera a que la página tenga el video nuevo
        try:
            if hashlib.md5(requests.get(url + f'?t={time.time():.0f}', timeout=60).content).hexdigest() == local:
                break
        except Exception:
            pass
        time.sleep(10)
    c = requests.post(f'{api}/{uid}/media', data={'media_type': 'REELS', 'video_url': f'{url}?v={local[:8]}',
                      'caption': item['caption'], 'share_to_feed': 'true', 'thumb_offset': 2500, 'access_token': tok}, timeout=60).json()
    if 'id' not in c:
        raise RuntimeError(c)
    for _ in range(60):
        st = requests.get(f'{api}/{c["id"]}', params={'fields': 'status_code,status', 'access_token': tok}, timeout=30).json()
        if st.get('status_code') == 'FINISHED':
            break
        if st.get('status_code') == 'ERROR':
            raise RuntimeError(st)
        time.sleep(8)
    pub = requests.post(f'{api}/{uid}/media_publish', data={'creation_id': c['id'], 'access_token': tok}, timeout=60).json()
    if 'id' not in pub:
        raise RuntimeError(pub)


def publish_anim(item, api, uid, tok, site):
    """Carrusel con láminas en video (MP4 1080x1350) desde la web."""
    import hashlib
    base = f'assets/ig/{item["id"]}/anim'
    nums = [i for i in (1, 2, 3, 4) if os.path.exists(f'{base}/{i}.mp4')]
    local = [hashlib.md5(open(f'{base}/{i}.mp4', 'rb').read()).hexdigest() for i in nums]
    urls = [f'{site}/{base}/{i}.mp4' for i in nums]
    for _ in range(40):  # espera a que la página tenga los videos nuevos
        try:
            if all(hashlib.md5(requests.get(u + f'?t={time.time():.0f}', timeout=60).content).hexdigest() == l
                   for u, l in zip(urls, local)):
                break
        except Exception:
            pass
        time.sleep(10)
    kids = []
    for u, l in zip(urls, local):
        c = requests.post(f'{api}/{uid}/media', data={'media_type': 'VIDEO', 'video_url': f'{u}?v={l[:8]}',
                          'is_carousel_item': 'true', 'thumb_offset': 4000, 'access_token': tok}, timeout=60).json()
        if 'id' not in c:
            raise RuntimeError(c)
        kids.append(c['id'])
    for k in kids:  # cada video tiene que terminar de procesarse
        for _ in range(60):
            st = requests.get(f'{api}/{k}', params={'fields': 'status_code,status', 'access_token': tok}, timeout=30).json()
            if st.get('status_code') == 'FINISHED':
                break
            if st.get('status_code') == 'ERROR':
                raise RuntimeError(st)
            time.sleep(6)
        else:
            raise RuntimeError('Instagram tardó demasiado en procesar un video')
    car = requests.post(f'{api}/{uid}/media', data={'media_type': 'CAROUSEL', 'children': ','.join(kids),
                        'caption': item['caption'], 'access_token': tok}, timeout=60).json()
    if 'id' not in car:
        raise RuntimeError(car)
    for _ in range(40):
        st = requests.get(f'{api}/{car["id"]}', params={'fields': 'status_code', 'access_token': tok}, timeout=30).json()
        if st.get('status_code') == 'FINISHED':
            break
        if st.get('status_code') == 'ERROR':
            raise RuntimeError(st)
        time.sleep(6)
    pub = requests.post(f'{api}/{uid}/media_publish', data={'creation_id': car['id'], 'access_token': tok}, timeout=60).json()
    if 'id' not in pub:
        raise RuntimeError(pub)


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
        if item.get('kind') == 'reel':
            try:
                publish_reel(item, api, uid, tok, site)
                tg('sendMessage', chat_id=CHAT, text='🎬 Listo, el Reel ya está publicado en Instagram.', reply_to_message_id=item.get('reply'))
            except Exception as e:
                print('Reel falló:', e, file=sys.stderr)
                item['intentos'] = item.get('intentos', 0) + 1
                if item['intentos'] < 3:
                    rest.append(item)
                else:
                    tg('sendMessage', chat_id=CHAT, text=f'⚠️ No pude publicar el Reel en Instagram ({str(e)[:300]}).', reply_to_message_id=item.get('reply'))
            continue
        if item.get('animado'):
            try:
                publish_anim(item, api, uid, tok, site)
                reservar_animado(item['id'])
                tg('sendMessage', chat_id=CHAT, text='🎬 Listo, el carrusel animado ya está publicado en Instagram.', reply_to_message_id=item.get('reply'))
                continue
            except Exception as e:
                print('Carrusel animado falló, va el fijo:', e, file=sys.stderr)
                tg('sendMessage', chat_id=CHAT, text=f'⚠️ Instagram no aceptó los videos ({str(e)[:200]}). Subo el carrusel fijo en rosa.', reply_to_message_id=item.get('reply'))
                item.pop('animado', None)
        nums = [i for i in (1, 2, 3, 4) if os.path.exists(f'assets/ig/{item["id"]}/{i}.jpg')]
        urls = [f'{site}/assets/ig/{item["id"]}/{i}.jpg' for i in nums]
        import hashlib
        local = [hashlib.md5(open(f'assets/ig/{item["id"]}/{i}.jpg', 'rb').read()).hexdigest() for i in nums]
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


def video_embebible(kind, vid):
    """True si el video se puede reproducir dentro de nuestra página (algunos solo dejan verse en su sitio)."""
    site = os.environ.get('SITE', 'https://guayabailustrada.com.mx') + '/'
    try:
        if kind == 'vm':
            r = requests.get(f'https://player.vimeo.com/video/{vid}', headers={'Referer': site, 'User-Agent': 'Mozilla/5.0'}, timeout=20)
            t = r.text.lower()
            if r.status_code == 403 or 'privacy settings' in t or 'configuración de privacidad' in t:
                return False          # Vimeo: solo se deja ver en el sitio del dueño
            return True               # 200, o 401 (verificación anti-robots): sí se ve en navegadores
        r = requests.get('https://www.youtube.com/oembed', params={'url': f'https://www.youtube.com/watch?v={vid}', 'format': 'json'}, timeout=20)
        if r.status_code != 200:
            return False
        e = requests.get(f'https://www.youtube.com/embed/{vid}', headers={'Referer': site, 'User-Agent': 'Mozilla/5.0'}, timeout=20).text
        return 'playabilityStatus' not in e or '"status":"OK"' in e or 'UNPLAYABLE' not in e
    except Exception as ex:
        print('Revisión de video:', ex, file=sys.stderr)
        return True   # si no se pudo revisar, no lo quitamos


def revisar_videos():
    """Quita de notas y borradores los videos que no se pueden ver fuera de su sitio original."""
    quitados = []
    js = open('posts.js', encoding='utf-8').read()
    ids = re.findall(r'\{"id": "([^"]+)"', js) + [os.path.basename(f)[:-5] for f in glob.glob('drafts/*.json')]
    rev = load('drafts/.videos_ok.json') if os.path.exists('drafts/.videos_ok.json') else {}
    for nid in ids:
        n, put = note_get(nid)
        if not n:
            continue
        kind = 'vm' if n.get('vm') else 'yt' if n.get('yt') else None
        if not kind:
            continue
        key = f'{kind}:{n[kind]}'
        if key not in rev:
            rev[key] = video_embebible(kind, n[kind])
        if not rev[key]:
            for k in ('yt', 'vm', 'vt', 'th', 'mp4', 'auto_video'):
                n.pop(k, None)
            n['sin_video'] = True
            put(n); quitados.append(n.get('t', nid))
    save('drafts/.videos_ok.json', rev)
    return quitados


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


def thumb_backfill():
    """Guarda en el sitio la miniatura de los videos (YouTube o Vimeo) para que la tarjeta no dependa de otros servidores."""
    from PIL import Image
    js = open('posts.js', encoding='utf-8').read()
    for nid in re.findall(r'\{"id": "([^"]+)"', js):
        n, put = note_get(nid)
        if not n or n.get('th') or not (n.get('yt') or n.get('vm')):
            continue
        urls = ([f'https://i.ytimg.com/vi/{n["yt"]}/maxresdefault.jpg', f'https://i.ytimg.com/vi/{n["yt"]}/hqdefault.jpg']
                if n.get('yt') else [n.get('vt') or vimeo_thumb(n['vm']) or ''])
        for u in urls:
            try:
                r = requests.get(u, timeout=30)
                if r.status_code == 200 and len(r.content) > 5000:
                    dest = f'assets/work/nota-{nid}-video.webp'
                    Image.open(io.BytesIO(r.content)).convert('RGB').save(dest, 'WEBP', quality=86)
                    n['th'] = dest; put(n)
                    return True
            except Exception as e:
                print('Miniatura:', e, file=sys.stderr)
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
        quitados = revisar_videos()
        if quitados:
            commit('Notas: quitar videos que no se pueden ver fuera de su sitio')
            tg('sendMessage', chat_id=CHAT, text='🎬 Quité el video de ' + ', '.join(f'«{q[:60]}»' for q in quitados)
               + ': su dueño no deja que se vea fuera de su página. La nota queda con su foto de portada.')
        while thumb_backfill():
            pass
        migrar = [f for f in sorted(glob.glob('drafts/*.json')) if load(f).get('cands_v') != 2]
        if migrar:
            tg('sendMessage', chat_id=CHAT, text=f'🔄 Mejoré las fotos de tus {len(migrar)} notas pendientes: solo fotos reales en alta calidad, sin anuncios '
               'ni capturas; si no hay otra buena, se repite la misma. Te las vuelvo a mandar para que solo las apruebes.')
            for f in migrar:
                n = load(f); poner_candidatas(n); n['cands_v'] = 2; n.pop('tg', None); save(f, n)
            limpiar_repetidas()
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
            if os.path.exists(REHACER):
                ids = load(REHACER); os.remove(REHACER)
                for rid in ids:
                    rehacer_reel(rid)
                changed = True
            if os.path.exists(REENVIAR):
                ids = load(REENVIAR); os.remove(REENVIAR)
                for rid in ids:
                    enviar_reel(rid)
                changed = True
            send_pending()
            poll()
            try:
                if thumb_backfill():
                    changed = True
            except Exception as e:
                print('Miniatura:', e, file=sys.stderr)
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
