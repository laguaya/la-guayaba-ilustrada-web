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


def urls_de_pagina(src):
    """Imagen principal (og:image) primero y luego las del cuerpo de la nota."""
    if not src or REDES.search(src):
        return []
    try:
        html = requests.get(src, headers=UA, timeout=25).text
    except Exception as e:
        print('Fuente:', e, file=sys.stderr)
        return []
    out = []
    for prop in ('og:image', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'):
        for m in re.finditer(r'<meta[^>]+(?:property|name)\s*=\s*["\']' + re.escape(prop) + r'["\'][^>]*>', html, re.I):
            c = _attr(m.group(0), 'content')
            if c: out.append(c)
    # solo el cuerpo de la nota si se puede ubicar
    body = html
    m = re.search(r'<article[\s\S]+?</article>', html, re.I)
    if m and len(m.group(0)) > 2000:
        body = m.group(0)
    # corta antes de "relacionadas", "lo más leído", etc. para no traer fotos de otras notas
    cut = re.search(r'relacionad|related|te puede interesar|te recomendamos|más noticias|lo más leído|most read|'
                    r'you may also like|read more|lee también|newsletter', body, re.I)
    if cut and cut.start() > 1500:
        body = body[:cut.start()]
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
    for fondo in ((0, 0, 0), (255, 255, 255)):
        diff = ImageChops.difference(im, Image.new('RGB', im.size, fondo)).convert('L').point(lambda v: 255 if v > 24 else 0)
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


def candidatas(n, carpeta='assets/work', maximo=4, solo_video=False):
    nid = n['id']
    os.makedirs(carpeta, exist_ok=True)
    lista = urls_de_video(n) + ([] if solo_video else urls_de_pagina(n.get('src', '')))
    rutas, huellas = [], []
    for k, u in enumerate(lista):
        if len(rutas) >= maximo:
            break
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code != 200 or len(r.content) < 8000:
                continue
            im = Image.open(io.BytesIO(r.content))
            im.load()
            im = _sin_franjas(im.convert('RGB'))
        except Exception:
            continue
        w, h = im.size
        if w < 600 or h < 380 or not (0.5 <= w / h <= 2.6):
            continue
        hu = _huella(im)
        if any(_parecidas(hu, x) for x in huellas):
            continue
        if w > 2400:
            im = im.resize((2400, int(h * 2400 / w)), Image.LANCZOS)
        dest = f'{carpeta}/nota-{nid}-foto-src{len(rutas) + 1}{"v" if solo_video else ""}.webp'
        im.save(dest, 'WEBP', quality=88)
        rutas.append(dest); huellas.append(hu)
    return rutas


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
