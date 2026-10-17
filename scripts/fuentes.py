"""Saca las fotos reales de la nota original (y las miniaturas del video, si la nota tiene uno).

candidatas(nota) -> lista de rutas locales (máximo 4), la mejor primero.
Filtra logos, íconos, anuncios, imágenes chicas y repetidas; separa collages y deja al final las fotos con texto.
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


MIN_W, MIN_H = 1200, 480          # súper alta calidad: nada que se pixelee en PC
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


def paneles(im, prof=0):
    """Si la imagen es un collage (2 o más fotos pegadas con una línea recta), regresa cada foto por separado."""
    try:
        import numpy as np
    except Exception:
        return [im]
    g = np.asarray(im.convert('L').resize((min(im.width, 900), int(im.height * min(im.width, 900) / im.width))), dtype=np.int16)
    h, w = g.shape
    def corte(a, n):
        d = np.abs(np.diff(a, axis=1)) > 28              # salto fuerte entre columnas vecinas
        frac = d.mean(axis=0)
        lo, hi = int(n * .22), int(n * .78)
        if hi <= lo:
            return None
        k = lo + int(np.argmax(frac[lo:hi]))
        return k + 1 if frac[k] > .72 else None
    x = corte(g, w)
    if x:
        X = int(x * im.width / w)
        izq, der = im.crop((0, 0, X, im.height)), im.crop((X, 0, im.width, im.height))
        return [q for p in (izq, der) for q in (paneles(_recorta_borde(p), prof + 1) if prof < 2 else [_recorta_borde(p)])]
    y = corte(g.T, h)
    if y:
        Y = int(y * im.height / h)
        return [q for p in (im.crop((0, 0, im.width, Y)), im.crop((0, Y, im.width, im.height)))
                for q in (paneles(_recorta_borde(p), prof + 1) if prof < 2 else [_recorta_borde(p)])]
    return [im]


def _recorta_borde(p):
    """Quita la línea separadora del collage (unos pixeles en cada orilla)."""
    m = max(2, int(min(p.size) * .012))
    return p.crop((m, m, p.width - m, p.height - m))


def palabras(im):
    """Cuántas palabras legibles trae la foto (texto encimado, capturas, anuncios). Usa tesseract si está."""
    import shutil, subprocess, tempfile
    if not shutil.which('tesseract'):
        return 0
    k = min(1.0, 1400 / im.width)
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        im.convert('L').resize((int(im.width * k), int(im.height * k))).save(f.name)
        try:
            out = subprocess.run(['tesseract', f.name, '-', '--psm', '11', 'tsv'], capture_output=True, text=True, timeout=60).stdout
        except Exception:
            return 0
    n = 0
    for ln in out.splitlines()[1:]:
        c = ln.split('\t')
        if len(c) >= 12:
            try:
                conf = float(c[10])
            except ValueError:
                continue
            if conf >= 70 and sum(ch.isalpha() for ch in c[11]) >= 3:
                n += 1
    return n


def mp4s_de_pagina(src):
    """Videos MP4 directos que trae la nota (por ejemplo Ads of the World los sirve así)."""
    if not src or REDES.search(src):
        return []
    html = pagina(src)
    out = []
    for u in re.findall(r'https?://[^"\'\s<>()]+?\.mp4(?:\?[^"\'\s<>()]*)?', html):
        u = u.replace('&amp;', '&')
        if u not in out:
            out.append(u)
    return out[:2]


def fotogramas(url, cuantos=14):
    """Saca cuadros nítidos y sin letras del video de la campaña. Regresa imágenes PIL, la mejor primero."""
    import shutil, subprocess, tempfile
    if not shutil.which('ffmpeg'):
        return []
    try:
        import numpy as np
    except Exception:
        np = None
    with tempfile.TemporaryDirectory() as tmp:
        vid = f'{tmp}/v.mp4'
        try:
            r = requests.get(url, headers=UA, timeout=90, stream=True)
            if r.status_code != 200:
                return []
            tam = 0
            with open(vid, 'wb') as f:
                for ch in r.iter_content(1 << 16):
                    tam += len(ch)
                    if tam > 150 * 1024 * 1024:
                        break
                    f.write(ch)
            dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', vid],
                                       capture_output=True, text=True, timeout=60).stdout.strip() or 0)
        except Exception as e:
            print('Video:', e, file=sys.stderr)
            return []
        if dur <= 1:
            return []
        res = []
        for k in range(cuantos):
            t = dur * (0.06 + 0.88 * k / max(1, cuantos - 1))
            out = f'{tmp}/f{k}.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', vid, '-frames:v', '1', out],
                           capture_output=True, timeout=60)
            if not os.path.exists(out):
                continue
            im = _sin_franjas(Image.open(out).convert('RGB'))
            g = im.convert('L').resize((320, int(320 * im.height / im.width)))
            if np is not None:
                a = np.asarray(g, dtype=np.float32)
                nitidez = float(np.abs(np.diff(a, axis=0)).mean() + np.abs(np.diff(a, axis=1)).mean())
                brillo = float(a.mean())
            else:
                nitidez, brillo = 10.0, 128.0
            if brillo < 28 or brillo > 235 or es_captura_o_grafico(im):
                continue                                   # negros, blancos, placas de logo
            if palabras(im) >= 2:
                continue                                   # cuadros con letras (supers, cierres)
            res.append((nitidez, im))
        res.sort(key=lambda x: -x[0])
        return [im for _, im in res]


def buscar_fuentes(consulta, excluir=(), maximo=5):
    """Busca en la web otras notas de la misma noticia (para tener más fotos). Regresa URLs de artículos."""
    from urllib.parse import quote, unquote, parse_qs
    out = []
    try:
        r = requests.get('https://html.duckduckgo.com/html/?q=' + quote(consulta), headers=UA, timeout=25)
        for href in re.findall(r'class="result__a"[^>]*href="([^"]+)"', r.text):
            href = href.replace('&amp;', '&')
            if 'uddg=' in href:
                href = unquote(parse_qs(urlparse(href).query).get('uddg', [''])[0])
            host = (urlparse(href).hostname or '').replace('www.', '')
            if not href.startswith('http') or REDES.search(href) or any(e in host for e in excluir):
                continue
            if re.search(r'youtube|wikipedia|pinterest|amazon\.|mercadolibre', host):
                continue
            if href not in out:
                out.append(href)
            if len(out) >= maximo:
                break
    except Exception as e:
        print('Búsqueda:', e, file=sys.stderr)
    return out


def candidatas(n, carpeta='assets/work', maximo=4, solo_video=False, registro=None):
    """registro: {huella_hex: id_de_nota} de fotos ya usadas en otras notas (anuncios que se repiten)."""
    nid = n['id']
    registro = registro if registro is not None else {}
    os.makedirs(carpeta, exist_ok=True)
    vids = urls_de_video(n)
    pag, excluir = [], set()
    if not solo_video:
        for fuente in [n.get('src', '')] + list(n.get('fuentes') or []):   # la nota original y otras notas del mismo tema
            if not fuente:
                continue
            ex = urls_de_portada(fuente)
            excluir |= ex
            pag += [u for u in urls_de_pagina(fuente) if u not in pag]
    lista = vids + [u for u in pag if u.split('?')[0] not in excluir]
    evitar = set(n.get('evitar') or [])                 # fotos que Sergio ya no quiere ver
    lista = [u for u in lista if u not in evitar]
    lista = [u for u in lista if not CAPTURA.search(u)] + [u for u in lista if CAPTURA.search(u)]   # "Screenshot..." al final
    og = pag[0] if pag else None
    rutas, huellas, respaldo, segunda = [], [], None, []
    for u in lista:
        if len(rutas) >= maximo:
            break
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code != 200 or len(r.content) < 15000:
                continue
            im = Image.open(io.BytesIO(r.content)); im.load()
            im = _sin_franjas(im.convert('RGB'))
        except Exception:
            continue
        piezas = paneles(im)
        if len(piezas) > 1 and im.width >= 1000 and respaldo is None and not es_captura_o_grafico(im):
            respaldo = (im, _huella(im), 1)               # el collage completo, si ningún panel sirve
        for im in piezas:
            if len(rutas) >= maximo:
                break
            w, h = im.size
            panel = len(piezas) > 1
            if not (0.5 <= w / h <= 2.4) and not panel:
                continue
            hu = _huella(im)
            if any(_parecidas(hu, x) for x in huellas):
                continue
            if any(_parecidas(hu, int(k, 16)) for k, v in registro.items() if v != nid):
                continue                                  # la misma foto en otra nota = anuncio del sitio
            buena = (w >= MIN_W and h >= MIN_H) or (panel and w >= 860 and h >= 1000)
            plana = es_captura_o_grafico(im)
            if buena and not plana and palabras(im) >= 2:
                segunda.append((im, hu))                  # trae letras (encimadas o del empaque): va después de las limpias
                continue
            if not buena or plana:
                prio = 2 if panel else 1
                if (u == og or panel) and w >= 860 and not plana and (respaldo is None or respaldo[2] < prio):
                    respaldo = (im, hu, prio)             # por si no hay otra mejor
                continue
            rutas.append(_guardar(im, f'{carpeta}/nota-{nid}-foto-src{len(rutas) + 1}{"v" if solo_video else ""}.webp'))
            huellas.append(hu); registro[format(hu, 'x')] = nid
    if len(rutas) < 2 and not solo_video:              # pocas fotos: saca cuadros del video de la campaña
        for mp4 in mp4s_de_pagina(n.get('src', '')):
            for im in fotogramas(mp4):
                if len(rutas) >= maximo:
                    break
                w, h = im.size
                if w < 1200 or h < 480:
                    continue
                hu = _huella(im)
                if any(_parecidas(hu, x) for x in huellas):
                    continue
                rutas.append(_guardar(im, f'{carpeta}/nota-{nid}-foto-src{len(rutas) + 1}.webp'))
                huellas.append(hu); registro[format(hu, 'x')] = nid
            if len(rutas) >= 2:
                break
    for im, hu in segunda:                            # solo si faltan fotos limpias
        if rutas:                                     # mejor repetir una foto limpia que usar una con letras
            break
        rutas.append(_guardar(im, f'{carpeta}/nota-{nid}-foto-src{len(rutas) + 1}{"v" if solo_video else ""}.webp'))
        huellas.append(hu); registro[format(hu, 'x')] = nid
    if not rutas and respaldo:
        im, hu, _ = respaldo
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
