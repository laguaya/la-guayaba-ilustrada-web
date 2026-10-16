"""Saca las fotos reales de la nota original (y las miniaturas del video, si la nota tiene uno).

candidatas(nota) -> lista de rutas locales (máximo 4), la mejor primero.
Filtra logos, íconos, anuncios, imágenes chicas y repetidas.
"""
import io, os, re, sys
from urllib.parse import urljoin, urlparse
import requests
from PIL import Image

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/126.0 Safari/537.36', 'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8'}
MALAS = re.compile(r'logo|icon|avatar|favicon|placeholder|blank\.|pixel|emoji|gravatar|badge|(?<![a-z])ads?[_/-]', re.I)
REDES = re.compile(r'(instagram\.com|facebook\.com|fb\.watch|tiktok\.com|x\.com/|twitter\.com)', re.I)


def _attr(tag, name):
    m = re.search(name + r'\s*=\s*["\']([^"\']+)["\']', tag, re.I)
    return m.group(1).strip() if m else None


def _mejor_srcset(ss):
    best, bw = None, -1
    for part in ss.split(','):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1 and bits[1].endswith('w'):
            try: w = int(bits[1][:-1])
            except ValueError: w = 0
        if w >= bw:
            best, bw = bits[0], w
    return best


_CACHE = {}


def pagina(src):
    if src not in _CACHE:
        try:
            _CACHE[src] = requests.get(src, headers=UA, timeout=25).text
        except Exception as e:
            print('Fuente:', e, file=sys.stderr)
            _CACHE[src] = ''
    return _CACHE[src]


def cuerpo(html):
    body = html
    m = re.search(r'<article[\s\S]+?</article>', html, re.I)
    if m and len(m.group(0)) > 2000:
        body = m.group(0)
    cut = re.search(r'relacionad|related|te puede interesar|te recomendamos|más noticias|lo más leído|most read|'
                    r'you may also like|read more|lee también|newsletter', body, re.I)
    if cut and cut.start() > 1500:
        body = body[:cut.start()]
    return body


def video_de_pagina(src):
    """Busca el video (YouTube o Vimeo) que trae la nota original. Regresa ('yt'|'vm', id) o None."""
    if not src or REDES.search(src):
        return None
    html = pagina(src)
    if not html:
        return None
    for zona in (cuerpo(html), html):
        m = re.search(r'(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})', zona)
        v = re.search(r'(?:player\.vimeo\.com/video/|vimeo\.com/)(\d{6,})', zona)
        if m and (not v or m.start() < v.start()):
            return ('yt', m.group(1))
        if v:
            return ('vm', v.group(1))
        if zona is not html and len(zona) < len(html):
            continue
    return None


def urls_de_pagina(src):
    """Imagen principal (og:image) primero y luego las del cuerpo de la nota."""
    if not src or REDES.search(src):
        return []
    html = pagina(src)
    if not html:
        return []
    out = []
    for prop in ('og:image', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'):
        for m in re.finditer(r'<meta[^>]+(?:property|name)\s*=\s*["\']' + re.escape(prop) + r'["\'][^>]*>', html, re.I):
            c = _attr(m.group(0), 'content')
            if c: out.append(c)
    body = cuerpo(html)
    for tag in re.findall(r'<(?:img|source)\b[^>]*>', body, re.I):
        u = None
        for a in ('data-srcset', 'srcset'):
            v = _attr(tag, a)
            if v:
                u = _mejor_srcset(v); break
        u = u or _attr(tag, 'data-lazy-src') or _attr(tag, 'data-src') or _attr(tag, 'data-original') or _attr(tag, 'src')
        if u: out.append(u)
    seen, res = set(), []
    for u in out:
        u = urljoin(src, u.replace('&amp;', '&'))
        if u.startswith('data:') or re.search(r'\.(svg|gif)(\?|$)', u, re.I) or MALAS.search(urlparse(u).path):
            continue
        if u not in seen:
            seen.add(u); res.append(u)
    return res[:18]


def urls_de_video(n):
    out = []
    if n.get('yt'):
        out += [f'https://i.ytimg.com/vi/{n["yt"]}/maxresdefault.jpg', f'https://i.ytimg.com/vi/{n["yt"]}/sddefault.jpg']
    if n.get('vt'):
        out.append(n['vt'])
    return out


def _sin_franjas(im):
    """Quita franjas negras o blancas (letterbox) alrededor de la imagen."""
    from PIL import ImageChops
    for fondo in ((0, 0, 0),):
        diff = ImageChops.difference(im, Image.new('RGB', im.size, fondo)).convert('L').point(lambda v: 255 if v > 12 else 0)
        box = diff.getbbox()
        if box and (box[2] - box[0]) * (box[3] - box[1]) < im.size[0] * im.size[1] * 0.93:
            im = im.crop(box)
    return im


def _huella(im):
    g = im.convert('L').resize((9, 8))
    p = list(g.getdata())
    return sum(1 << i for i in range(64) if p[(i // 8) * 9 + i % 8] > p[(i // 8) * 9 + i % 8 + 1])


def _parecidas(a, b):
    return bin(a ^ b).count('1') <= 12


MIN_W, MIN_H = 1200, 650          # súper alta calidad: nada que se pixelee en PC
CAPTURA = re.compile(r'screen.?shot|captura|pantallazo|screen-?cap', re.I)
_PORTADAS = {}


def urls_de_portada(src):
    """Imágenes que el sitio repite en su página principal (anuncios, banners, logos): no son de la nota."""
    try:
        p = urlparse(src); home = f'{p.scheme}://{p.netloc}/'
    except Exception:
        return set()
    if home not in _PORTADAS:
        html = pagina(home)
        us = set()
        for tag in re.findall(r'<(?:img|source)\b[^>]*>', html, re.I):
            for a in ('src', 'data-src', 'data-lazy-src'):
                v = _attr(tag, a)
                if v: us.add(urljoin(home, v).split('?')[0])
        _PORTADAS[home] = us
    return _PORTADAS[home]


def es_captura_o_grafico(im):
    """Capturas de pantalla, banners y gráficos planos: mucho color liso (fondos blancos, interfaces)."""
    sm = im.convert('RGB').resize((160, 90))
    q = sm.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    counts = sorted(q.getcolors() or [], reverse=True)
    total = 160 * 90
    return bool(counts) and counts[0][0] / total > 0.38


def candidatas(n, carpeta='assets/work', maximo=4, solo_video=False, registro=None):
    """registro: {huella_hex: id_de_nota} de fotos ya usadas en otras notas (anuncios que se repiten)."""
    nid = n['id']
    registro = registro if registro is not None else {}
    os.makedirs(carpeta, exist_ok=True)
    vids = urls_de_video(n)
    pag = [] if solo_video else urls_de_pagina(n.get('src', ''))
    excluir = set() if solo_video else urls_de_portada(n.get('src', ''))
    lista = vids + [u for u in pag if u.split('?')[0] not in excluir]
    og = pag[0] if pag else None
    rutas, huellas, respaldo = [], [], None
    for u in lista:
        if len(rutas) >= maximo:
            break
        if CAPTURA.search(u):
            continue
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code != 200 or len(r.content) < 15000:
                continue
            im = Image.open(io.BytesIO(r.content)); im.load()
            im = _sin_franjas(im.convert('RGB'))
        except Exception:
            continue
        w, h = im.size
        if not (0.5 <= w / h <= 2.4):
            continue
        hu = _huella(im)
        if any(_parecidas(hu, x) for x in huellas):
            continue
        if any(_parecidas(hu, int(k, 16)) for k, v in registro.items() if v != nid):
            continue                                  # la misma foto en otra nota = anuncio del sitio
        buena = w >= MIN_W and h >= MIN_H
        plana = es_captura_o_grafico(im)
        if not buena or plana:
            if u == og and w >= 1000 and respaldo is None:
                respaldo = (im, hu)                   # la imagen principal de la nota, por si no hay otra
            continue
        rutas.append(_guardar(im, f'{carpeta}/nota-{nid}-foto-src{len(rutas) + 1}{"v" if solo_video else ""}.webp'))
        huellas.append(hu); registro[format(hu, 'x')] = nid
    if not rutas and respaldo:
        im, hu = respaldo
        rutas.append(_guardar(im, f'{carpeta}/nota-{nid}-foto-src1.webp')); registro[format(hu, 'x')] = nid
    return rutas


def _guardar(im, dest):
    w, h = im.size
    if w > 2600:
        im = im.resize((2600, int(h * 2600 / w)), Image.LANCZOS)
    im.save(dest, 'WEBP', quality=92, method=5)
    return dest


def credito(src):
    try:
        host = urlparse(src).hostname or ''
    except Exception:
        return ''
    host = re.sub(r'^www\.', '', host)
    nombres = {'merca20.com': 'Merca2.0', 'reasonwhy.es': 'Reason Why', 'adsoftheworld.com': 'Ads of the World'}
    return nombres.get(host, host)


if __name__ == '__main__':
    import json
    n = json.loads(sys.argv[1])
    print(candidatas(n, sys.argv[2] if len(sys.argv) > 2 else '/tmp'))
