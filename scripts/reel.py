"""Reel vertical (1080x1920, 30 fps, 15 a 75 s) de una nota, con branding de Newsbrand.
# reinicio: version TikTok a pantalla completa (oct 18)

Uso: python scripts/reel.py datos.json salida.mp4
datos: img, img2, fotos (lista opcional), etiqueta, portada, titulo, marca, escenas o guion (texto de la voz),
       src (URL de la nota, para sacar clips del video de la campaña) o video (ruta local a un MP4).

Estructura:
  1) Gancho (0 a ~3 s): la primera toma con el titular grande y el marcatextos rosa.
  2) Cuerpo: una ESCENA por cada frase de la voz ("escenas" en los datos). SIEMPRE se ve video o foto:
       video  -> la toma del video de la campaña que corresponde ("desde"/"hasta" en segundos; si no viene,
                 la siguiente toma sin usar). Una frase larga encadena varias tomas; el video no se repite.
       foto   -> foto de lo que se menciona (URL, ruta o 'img'/'img2'), con una deriva muy lenta.
     Cortes suaves al ritmo de la voz (fundido de 0.16 s, sin zoom). Subtítulos tipo karaoke.
  3) Cierre (3 s): la última toma del video con el CTA para seguir la cuenta encima.
Solo se arma si la nota tiene video de la campaña.
Audio: voz con IA (scripts/voz.py) + música de fondo bajita.
"""
import functools, glob, json, math, os, re, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portada
import carrusel as C

W, H, FPS = 1080, 1920, 30
M = 72
INK, WHITE = '#0B0B0B', '#FFFFFF'
# Paleta propia del Reel (distinta del carrusel rosa y del animado naranja): morado uva + rosa claro
UVA, ROSA = '#6E1F5E', '#FFC6DD'
PINK = ROSA
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.path.join(R, 'assets', 'audio', 'musica', 'uplifting-hiphop-jazz-funk-60.mp3')   # la canción que eligió Sergio (versión de 60 s)
GANCHO, CIERRE, INICIO_VOZ = 3.2, 3.0, 0.35


@functools.lru_cache(maxsize=None)
def font(name, size):
    return portada.font(name, size)


C.font = font


def cl(x, a=0.0, b=1.0): return max(a, min(b, x))
def lin(t, a, b): return cl((t - a) / (b - a))
def eo(x): x = cl(x); return 1 - (1 - x) ** 3
def eio(x): x = cl(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def layer(w, h):
    im = Image.new('RGBA', (int(w), int(h)), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)


def paste(base, im, x, y, op=1.0):
    if op <= 0 or im is None:
        return
    if op < 1:
        im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * op)))
    base.alpha_composite(im, (int(x), int(y)))


def pill(text, f, bg, fg, padx=34, pady=18):
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    w = int(d0.textlength(text, font=f)); a, de = f.getmetrics()
    im, d = layer(w + 2 * padx, a + de + 2 * pady)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=bg)
    d.text((padx, pady + a), text, font=f, fill=fg, anchor='ls')
    return im


def text_block(text, maxw, max_lines, base, big, small, color, it_color=None, track=-0.035, lh=1.04):
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    fonts, ls, size = C.fitted(d0, text, maxw, max_lines, base, big, small, track=track)
    im, d = layer(maxw + 40, int(len(ls) * size * lh + size * .4) + 20)
    C.render(d, 20, 6, ls, fonts, size * lh, color, hl_bg=PINK, hl_fg=INK, it_color=it_color, track=track, pad=12)
    return im


def body_block(text, maxw, size, color, lines=6):
    fr = {'n': font('lg-regular.woff2', size), 'pk': font('lg-bold.woff2', size),
          'hl': font('lg-regular.woff2', size), 'it': font('lg-italic.woff2', size)}
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    rl = C.layout(d0, text, fr, maxw)[:lines]
    im, d = layer(maxw + 20, int(len(rl) * size * 1.35 + size))
    C.render(d, 10, 4, rl, fr, size * 1.35, color, pk=PINK)
    return im


# ---------------------------------------------------------------- fondos (fotos y clips)
def vertical(im, foco=(0.5, 0.45), zoom=1.0):
    """Pone cualquier imagen en 1080x1920. Si llenar la pantalla la ampliaría demasiado (se vería borrosa),
    la deja completa al centro sobre un fondo desenfocado de ella misma."""
    import encuadre
    im = im.convert('RGB')
    if PANTALLA_COMPLETA or im.height > im.width:    # video vertical (o versión TikTok): a pantalla completa
        if PANTALLA_COMPLETA and im.height <= im.width:
            return encuadre.recorte(im, (W, H), foco, zoom=zoom, destino=(0.5, 0.45))
        return encuadre.recorte(im, (W, H), foco, zoom=zoom, destino=(0.5, 0.42))
    fondo = im.resize((54, 96)).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
    fondo = Image.blend(fondo, Image.new('RGB', (W, H), UVA), 0.55)
    bw = W
    bh = int(im.height * bw / im.width)
    if bh > H * 0.62:
        bh = int(H * 0.62); bw = int(im.width * bh / im.height)
    banda = encuadre.recorte(im, (bw, bh), foco, zoom=zoom)
    fondo.paste(banda, ((W - bw) // 2, int(H * 0.40 - bh / 2)))
    return fondo


PANTALLA_COMPLETA = False   # versión TikTok: video horizontal recortado a pantalla completa (nunca el rectángulo al centro)
SALTO_INTRO = 7.0           # versión TikTok: se brincan los primeros segundos de tráileres (clasificación ESRB, logos, avisos)
SALTO_FINAL = 4.0           # y los últimos (logos, fechas y avisos legales)
TOTAL = 60.0          # todos los Reels duran exactamente un minuto
SONIDO_ORIGINAL = False   # Sergio no quiere el audio de fondo de los clips: solo voz y música
CIERRE_MIN = 2.6      # segundos mínimos del cierre con el CTA
TOMA_MIN = 1.0        # ningún clip dura menos de esto (los clips cortitos se ven como glitch)
ESCALA = 'scale=min(1920\\,iw):-2'
UA_VID = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}


def fps_de(vid):
    """Cuadros por segundo del video (24, 25 o 30). Si se arma a otra velocidad, se repiten cuadros y hay brincos."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                            '-of', 'csv=p=0', vid], capture_output=True, text=True, timeout=60).stdout.strip()
        a, b = (r.split('/') + ['1'])[:2]
        f = float(a) / float(b)
        return min((24, 25, 30), key=lambda x: abs(x - f)) if 20 < f < 61 else 30
    except Exception:
        return 30


def _descargar(url, ruta):
    import requests
    r = requests.get(url, headers=UA_VID, timeout=90, stream=True)
    if r.status_code != 200 or 'html' in r.headers.get('content-type', ''):
        return False
    tam = 0
    with open(ruta, 'wb') as f:
        for ch in r.iter_content(1 << 16):
            tam += len(ch)
            if tam > 150 * 1024 * 1024:
                break
            f.write(ch)
    return tam > 50000


def _ytdlp(url, ruta):
    """YouTube, Vimeo, TikTok, Instagram y otros reproductores (si yt-dlp está instalado). Si existe el secreto
    YT_COOKIES (cookies de una cuenta de YouTube en formato Netscape), se usan para que YouTube no bloquee."""
    if not shutil.which('yt-dlp'):
        return False
    extra = []
    if os.environ.get('YT_COOKIES'):
        ck = os.path.join(os.path.dirname(ruta), 'cookies.txt')
        if not os.path.exists(ck):
            open(ck, 'w').write(os.environ['YT_COOKIES'])
        extra = ['--cookies', ck]
    clientes = [[]]
    if re.search(r'youtube\.com|youtu\.be', url):     # si YouTube bloquea un cliente, se prueba con otros
        clientes += [['--extractor-args', f'youtube:player_client={c}'] for c in ('tv', 'web_safari', 'mweb', 'android_vr')]
    for cli in clientes:
        try:
            r = subprocess.run(['yt-dlp', '-q', '--no-playlist', '--max-filesize', '150M'] + extra + cli + ['-f',
                                'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b',
                                '--merge-output-format', 'mp4', '-o', ruta, url], capture_output=True, timeout=300)
        except Exception:
            continue
        if r.returncode == 0 and os.path.exists(ruta) and os.path.getsize(ruta) > 50000:
            return True
        print('yt-dlp', cli[-1:] or 'default', ':', r.stderr[-250:], file=sys.stderr)
    return False


INVIDIOUS = ['https://invidious.f5.si', 'https://inv.nadeko.net', 'https://yewtu.be', 'https://invidious.nerdvpn.de']


def _yt_id(url):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})', url)
    return m.group(1) if m else None


def invidious(url, ruta):
    """YouTube sin cookies: lo baja a través de un espejo público de Invidious (los servidores de GitHub están
    bloqueados por YouTube, los espejos no). Prefiere la pista de video MP4 de hasta 1080p (el audio no se usa)."""
    import requests
    vid = _yt_id(url)
    if not vid:
        return False
    bases = list(INVIDIOUS)
    try:
        r = requests.get('https://api.invidious.io/instances.json', params={'sort_by': 'health'}, timeout=20)
        for nombre, info in r.json():
            u = (info or {}).get('uri', '')
            if u.startswith('https://') and (info or {}).get('api') and u not in bases:
                bases.append(u)
    except Exception:
        pass
    for b in bases[:14]:
        try:
            r = requests.get(f'{b}/api/v1/videos/{vid}', params={'local': 'true'}, headers=UA_VID, timeout=25)
            if r.status_code != 200:
                print('Invidious', b, r.status_code, file=sys.stderr)
                continue
            j = r.json()
            def alto(f):
                m = re.search(r'(\d+)p', f.get('qualityLabel') or f.get('resolution') or '')
                return int(m.group(1)) if m else 0
            vids = [f for f in j.get('adaptiveFormats', []) if 'video/mp4' in f.get('type', '') and 'avc1' in f.get('type', '')
                    and 0 < alto(f) <= 1080]
            vids.sort(key=alto, reverse=True)
            opciones = vids[:2] + sorted(j.get('formatStreams', []), key=alto, reverse=True)[:1]
            for f in opciones:
                u = f.get('url', '')
                if u.startswith('/'):
                    u = b + u
                if u:
                    print('Invidious', b, 'probando', alto(f), 'p', file=sys.stderr)
                if u and _descargar(u, ruta):
                    print('Video de YouTube vía', b, alto(f), 'p', file=sys.stderr)
                    return True
        except Exception as e:
            print('Invidious', b, e, file=sys.stderr)
    return False


def _gh():
    tok, repo = os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPOSITORY', 'laguaya/la-guayaba-ilustrada-web')
    return ({'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'} if tok else None), repo


def _cache_nombre(url):
    import hashlib
    return hashlib.sha1(url.encode()).hexdigest()[:16] + '.mp4'


def cache_get(url, ruta):
    """Videos ya descargados una vez (YouTube y redes) se guardan en el Release "videos-cache" del repositorio:
    así un video que se bajó bien nunca vuelve a depender de que YouTube no bloquee."""
    import requests
    h, repo = _gh()
    if not h:
        return False
    try:
        r = requests.get(f'https://api.github.com/repos/{repo}/releases/tags/videos-cache', headers=h, timeout=30)
        if r.status_code != 200:
            return False
        a = next((a for a in r.json().get('assets', []) if a['name'] == _cache_nombre(url)), None)
        if not a:
            return False
        rr = requests.get(a['url'], headers={**h, 'Accept': 'application/octet-stream'}, timeout=300, stream=True)
        if rr.status_code != 200:
            return False
        with open(ruta, 'wb') as f:
            for ch in rr.iter_content(1 << 16):
                f.write(ch)
        print('Video desde caché:', url[:60], file=sys.stderr)
        return os.path.getsize(ruta) > 50000
    except Exception as e:
        print('Caché:', e, file=sys.stderr)
        return False


def cache_put(url, ruta):
    import requests
    h, repo = _gh()
    if not h or not os.path.exists(ruta) or os.path.getsize(ruta) > 1900 * 1024 * 1024:
        return
    try:
        r = requests.get(f'https://api.github.com/repos/{repo}/releases/tags/videos-cache', headers=h, timeout=30)
        if r.status_code == 404:
            r = requests.post(f'https://api.github.com/repos/{repo}/releases', headers=h, timeout=30,
                              json={'tag_name': 'videos-cache', 'name': 'Videos para Reels (caché)', 'prerelease': True,
                                    'body': 'Videos de YouTube y redes ya descargados para armar los Reels. No borrar.'})
        rel = r.json()
        up = rel['upload_url'].split('{')[0]
        with open(ruta, 'rb') as f:
            rr = requests.post(up, params={'name': _cache_nombre(url)}, data=f, timeout=600,
                               headers={**h, 'Content-Type': 'video/mp4'})
        print('Caché guardada:', url[:60], rr.status_code, file=sys.stderr)
    except Exception as e:
        print('Caché:', e, file=sys.stderr)


def bajar_url(url, ruta):
    """Baja un video REAL: MP4 directo, página con MP4 (Ads of the World), o YouTube/Vimeo/TikTok/Instagram con yt-dlp
    (YouTube necesita el secreto YT_COOKIES para que no lo bloquee)."""
    try:
        if re.search(r'\.(mp4|mov|m4v|webm)(\?|$)', url, re.I):
            return _descargar(url, ruta)
        if re.search(r'youtube\.com|youtu\.be|vimeo\.com|tiktok\.com|instagram\.com|x\.com|twitter\.com|facebook\.com', url, re.I):
            if cache_get(url, ruta):
                return True
            ok = _ytdlp(url, ruta) or (re.search(r'youtube\.com|youtu\.be', url) and invidious(url, ruta))
            if ok:
                cache_put(url, ruta)
            return bool(ok)
        import fuentes
        for u in fuentes.mp4s_de_pagina(url):
            if _descargar(u, ruta):
                return True
        return _ytdlp(url, ruta)
    except Exception as e:
        print('Video extra:', url, e, file=sys.stderr)
        return False


def bajar_video(data, tmp):
    """Video principal de la campaña."""
    if data.get('video') and os.path.exists(str(data['video'])):
        return data['video']
    urls = [data['mp4']] if data.get('mp4') else []
    if data.get('yt'):
        urls.append('https://www.youtube.com/watch?v=' + data['yt'])
    if data.get('vm'):
        urls.append('https://vimeo.com/' + str(data['vm']))
    if not urls and data.get('src'):
        try:
            import fuentes
            urls = fuentes.mp4s_de_pagina(data['src'])
        except Exception:
            urls = []
    for u in urls:
        if bajar_url(u, f'{tmp}/campana.mp4'):
            return f'{tmp}/campana.mp4'
    return None


def normalizar(ruta, salida):
    """Los videos de YouTube suelen venir en AV1 o VP9: al saltar a media toma ffmpeg a veces no saca cuadros.
    Se pasan una sola vez a H.264 (mismo tamaño y velocidad) para que cada corte sea exacto."""
    try:
        codec = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name',
                                '-of', 'csv=p=0', ruta], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        codec = ''
    if codec == 'h264':
        return ruta
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', ruta, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17',
                        '-pix_fmt', 'yuv420p', '-vf', 'scale=min(1920\\,iw):-2', salida], capture_output=True, text=True, timeout=1200)
    print('Video', codec, '-> h264', 'ok' if r.returncode == 0 else r.stderr[-300:], file=sys.stderr)
    return salida if r.returncode == 0 and os.path.exists(salida) else ruta


class Fuente:
    """Un video (la campaña o uno extra) con sus tomas reales, su recorte sin franjas y su encuadre fijo."""
    n = 0

    def __init__(self, ruta, tmp, nombre=''):
        import tomas as TM, encuadre
        Fuente.n += 1
        ruta = normalizar(ruta, f'{tmp}/norm{Fuente.n}.mp4')
        self.id, self.ruta, self.tmp, self.nombre = Fuente.n, ruta, tmp, nombre
        self.tomas, self.dur = TM.cortes(ruta, maximo=10 ** 6)       # solo cortes reales: nunca saltos dentro de una toma
        self.usados = []
        self.salto, self.fin_util = 0.0, self.dur
        if PANTALLA_COMPLETA and self.dur > 20:
            self.salto, self.fin_util = SALTO_INTRO, self.dur - SALTO_FINAL
            self.usados += [(0.0, self.salto), (self.fin_util, self.dur + 1)]
        self.audio = bool(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index',
                                          '-of', 'csv=p=0', ruta], capture_output=True, text=True, timeout=60).stdout.strip())
        m = self._muestras()
        self.crop = sin_bordes(m) if m else None
        self.foco = encuadre.foco(self.abrir(m[len(m) // 2]).convert('RGB')) if m else (0.5, 0.45)
        print('Fuente', self.id, nombre[:70], f'{self.dur:.1f}s', len(self.tomas), 'tomas', file=sys.stderr)

    def _muestras(self, n=7):
        carpeta = f'{self.tmp}/muestras{self.id}'; os.makedirs(carpeta, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', self.ruta, '-vf', f'fps={n / max(1.0, self.dur):.4f},{ESCALA}',
                        '-q:v', '3', f'{carpeta}/%03d.jpg'], capture_output=True, timeout=600)
        return sorted(glob.glob(f'{carpeta}/*.jpg'))

    def abrir(self, ruta):
        im = Image.open(ruta)
        return im.crop(self.crop) if self.crop else im

    def cuadros(self, k, desde, seg):
        carpeta = f'{self.tmp}/clip{self.id}_{k}'; os.makedirs(carpeta, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{desde:.3f}', '-i', self.ruta, '-t', f'{seg + 0.08:.3f}',
                        '-vf', f'fps={FPS},{ESCALA}', '-q:v', '2', f'{carpeta}/%05d.jpg'], capture_output=True, timeout=600)
        return sorted(glob.glob(f'{carpeta}/*.jpg'))

    def toma_libre(self, minimo=TOMA_MIN):
        """Primer pedazo sin usar de alguna toma (se puede seguir una toma donde se quedó, nunca repetir)."""
        for t0, t1 in self.tomas:
            x = t0
            for a, b in sorted(self.usados):
                if a <= x + 0.05 < b:
                    x = b
            fin = min([t1] + [a for a, b in self.usados if a > x + 0.05])
            if fin - x >= minimo:
                return x, fin
        return None


def sin_bordes(cuadros):
    """Detecta franjas negras fijas (arriba/abajo o a los lados) y regresa la caja útil."""
    caja = None
    for c in cuadros:
        im = Image.open(c).convert('L')
        b = im.point(lambda v: 255 if v > 22 else 0).getbbox()
        if not b:
            continue
        caja = b if caja is None else (min(caja[0], b[0]), min(caja[1], b[1]), max(caja[2], b[2]), max(caja[3], b[3]))
    if not caja:
        return None
    w, h = Image.open(cuadros[0]).size
    if (caja[2] - caja[0]) < w * 0.96 or (caja[3] - caja[1]) < h * 0.96:
        return caja
    return None



# ---------------------------------------------------------------- subtítulos karaoke
def grupos(palabras):
    """Junta las palabras de la voz en bloques cortos (máx. 3 palabras o 20 letras) para los subtítulos."""
    out, cur = [], []
    for i, p in enumerate(palabras):
        if cur and p[0] - cur[-1][1] > 0.22:          # pausa de la voz = fin de frase
            out.append(cur); cur = []
        cur.append(p)
        txt = ' '.join(x[2] for x in cur)
        if len(cur) >= 3 or len(txt) >= 20 or p[2][-1:] in '.,;:?!':
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def subtitulo(grupo, t):
    """Capa con el bloque de subtítulo; la palabra que suena va sobre una franja rosa."""
    f = font('lg-black.woff2', 78)
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    sp = d0.textlength(' ', font=f)
    ws = [w for _, _, w in grupo]
    anchos = [d0.textlength(w, font=f) for w in ws]
    total = sum(anchos) + sp * (len(ws) - 1)
    a, de = f.getmetrics()
    im, d = layer(total + 80, a + de + 50)
    x = 40
    for (ini, fin, w), aw in zip(grupo, anchos):
        activa = ini <= t < max(fin, ini + 0.12) or (t >= fin and w is ws[-1] and t < fin + 0.4)
        if activa:
            d.rounded_rectangle((x - 12, 14, x + aw + 12, 14 + a + de + 8), radius=10, fill=ROSA)
            d.text((x, 18 + a), w, font=f, fill=UVA, anchor='ls')
        else:
            d.text((x, 18 + a), w, font=f, fill=WHITE, anchor='ls', stroke_width=5, stroke_fill=UVA)
        x += aw + sp
    return im


# ---------------------------------------------------------------- escenas
def preparar(data):
    g = Image.new('L', (1, H))
    for y in range(H):
        t = max(0.0, (y - H * .45) / (H * .45)); g.putpixel((0, y), int(255 * min(1.0, t) ** .9 * .85))
    abajo = Image.new('RGBA', (W, H), (60, 14, 50, 0)); abajo.putalpha(g.resize((W, H)))
    top = Image.linear_gradient('L').rotate(180).resize((W, 380)).point(lambda v: int(v * .6))
    arriba = Image.new('RGBA', (W, 380), (60, 14, 50, 0)); arriba.putalpha(top)
    L = {
        'abajo': abajo, 'arriba': arriba,
        'brand': pill('NEWSBRAND · LA GUAYABA ILUSTRADA', font('lg-bold.woff2', 26), (255, 255, 255, 46), WHITE, 26, 14),
        'tag': pill((data.get('etiqueta') or 'NOTICIAS').upper(), font('lg-black.woff2', 34), ROSA, UVA, 30, 16),
        'marca': pill((data.get('marca') or '').upper(), font('lg-black.woff2', 30), ROSA, UVA, 24, 13) if data.get('marca') else None,
        'cta': text_block('Síguenos para no perderte la próxima', W - 2 * M, 2, 'lg-black.woff2', 76, 56, WHITE),
        'bio': pill('@lgi.newsbrand', font('lg-black.woff2', 40), ROSA, UVA, 40, 22),
    }
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    fonts, ls, size = C.fitted(d0, data['portada'], W - 2 * M, 4, 'lg-black.woff2', 112, 64)
    L['gancho'] = (fonts, ls, size)
    return L


def gancho(base, t, L):
    """Titular grande que sube suave renglón por renglón y luego el marcatextos pinta las franjas."""
    fonts, ls, size = L['gancho']
    lh = size * 1.08
    y0 = 1500 - len(ls) * lh
    paste(base, L['tag'], M, y0 - 100 + (1 - eo(lin(t, .1, .5))) * 30, eo(lin(t, .1, .5)))
    run = [0]

    def marca():
        k = run[0]; run[0] += 1
        return eio(lin(t, 0.95 + k * 0.4, 1.45 + k * 0.4))
    for i, ln in enumerate(ls):
        p = eo(lin(t, .2 + i * .15, .6 + i * .15))
        capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        C.render(ImageDraw.Draw(capa), M, y0 + i * lh + (1 - p) * 30, [ln], fonts, lh, WHITE,
                 hl_bg=ROSA, hl_fg=UVA, pad=12, marca=marca)
        if p < 1:
            capa.putalpha(capa.getchannel('A').point(lambda v: int(v * p)))
        base.alpha_composite(capa)


def cierre(base, t, L):
    """CTA sobre el video (nunca fondo de color): aparece con un fundido suave."""
    a = eio(lin(t, 0.1, 0.9))
    y = 1330
    paste(base, L['cta'], M - 10, y, a)
    b = eio(lin(t, 0.5, 1.3))
    paste(base, L['bio'], M, y + L['cta'].height + 24, b)


def guion_de(data):
    es = data.get('escenas')
    if isinstance(es, list) and es and all(isinstance(e, dict) and e.get('voz') for e in es):
        return ' '.join(e['voz'].strip() for e in es)
    g = (data.get('guion') or '').strip()
    if g:
        return g
    partes = [re.sub(r'[*_\[\]]', '', data.get('portada', '')).strip().rstrip('.') + '.']
    if data.get('resumen'):
        partes.append(re.sub(r'[\[\]]', '', data['resumen']))
    info = data.get('info') or []
    if info:
        partes.append(re.sub(r'[\[\]]', '', info[0]))
    partes.append('Síguenos para más noticias de marcas todos los días.')
    return ' '.join(partes)


# ---------------------------------------------------------------- escenas: lo que se ve con cada frase
def escenas_de(data):
    """Lista de escenas [{'voz': frase, 'ver': 'video'|'foto'|'dato'|'frase', ...}].
    Si la nota no trae escenas, cada frase del guion es una escena con su propia toma del video."""
    es = data.get('escenas')
    if isinstance(es, list) and es and all(isinstance(e, dict) and e.get('voz') for e in es):
        return [dict(e) for e in es]
    out = []
    for f in re.split(r'(?<=[.!?…])\s+', guion_de(data)):
        if not f.strip():
            continue
        if out and len(out[-1]['voz'].split()) < 7:
            out[-1]['voz'] += ' ' + f
        else:
            out.append({'voz': f, 'ver': 'video'})
    return out


def _norm(w):
    return re.sub(r'[^0-9a-záéíóúüñ]', '', w.lower())


def tiempos(escenas, palabras, limpiar):
    """Segundo en que la voz empieza cada escena."""
    guion = []
    for i, e in enumerate(escenas):
        for w in limpiar(e['voz']).split():
            if _norm(w):
                guion.append((_norm(w), i))
    ini, j = [None] * len(escenas), 0
    for a, _, w in palabras:
        n = _norm(w)
        if not n or not guion:
            continue
        k = next((k for k in range(j, min(j + 6, len(guion))) if guion[k][0] == n), None)
        if k is None:
            k = min(j, len(guion) - 1)
        j = k + 1
        i = guion[k][1]
        if ini[i] is None:
            ini[i] = a
    ini[0] = 0.0
    for i in range(1, len(ini)):                      # escenas sin palabras reconocidas: justo después de la anterior
        if ini[i] is None or ini[i] < ini[i - 1]:
            ini[i] = ini[i - 1] + 0.5
    return ini


def bajar_foto(ref, tmp, k):
    """Foto de una escena: ruta local, 'img'/'img2' (fotos de la nota) o URL."""
    if not ref:
        return None
    if os.path.exists(str(ref)):
        try:
            return Image.open(ref).convert('RGB')
        except Exception:
            return None
    if str(ref).startswith('http'):
        try:
            import fuentes, requests, io
            r = requests.get(ref, headers=fuentes.UA, timeout=40)
            if r.status_code == 200 and len(r.content) > 5000:
                im = Image.open(io.BytesIO(r.content)).convert('RGB')
                if min(im.size) >= 300:
                    return im
        except Exception as e:
            print('Foto de escena:', e, file=sys.stderr)
    return None


def plan(escenas, ini, fin_cuerpo, total, principal, extras, data, tmp):
    """Convierte las escenas en tramos: [{'a','b','tipo': 'video'|'foto', ...}]. Siempre hay video o foto.
    Orden para cubrir cada frase: la toma que pidió el redactor -> tomas nuevas de la campaña -> tomas nuevas de
    los videos extra (otras campañas, la marca, el producto) -> fotos -> y solo si ya no hay nada, la toma menos usada."""
    import encuadre
    pedidas = {data.get(e['foto']) if e.get('foto') in ('img', 'img2') else e.get('foto')
               for e in escenas if e.get('foto')}
    fotos_nota = [p for p in (data.get('img'), data.get('img2')) if p and os.path.exists(p)]
    fotos_nota += [p for p in (data.get('fotos') or []) if p and os.path.exists(p) and p not in fotos_nota]
    fotos_nota = [p for p in fotos_nota if p not in pedidas]
    fi, k, tramos = [0], [0], []
    fuentes_todas = ([principal] if principal else []) + extras
    por_url = {f.nombre: f for f in extras}

    def foto_libre():
        while fi[0] < len(fotos_nota):
            p = fotos_nota[fi[0]]; fi[0] += 1
            im = bajar_foto(p, tmp, 0)
            if im:
                return im
        return None

    def poner_foto(a, b, im):
        tramos.append(dict(a=a, b=b, tipo='foto', im=im, foco=encuadre.foco(im)))

    def poner_video(F, a, d, desde, hasta=None):
        """Pone un clip de la fuente F desde `desde` (sin pasarse de `hasta`). Regresa los segundos que cubrió."""
        margen = 1.0 / FPS                               # 1 cuadro de margen: nunca se cuela la toma vecina
        desde = max(0.0, desde, F.salto) + margen
        fin = F.fin_util - margen
        if hasta is not None and hasta > desde + 0.3:
            fin = min(fin, hasta - margen)
        hay = fin - desde
        if hay < min(TOMA_MIN, d) - 0.01:
            return 0.0
        largo = min(d, hay)
        if d - largo < TOMA_MIN and d - largo > 0.05:     # lo que sobraría es muy cortito: mejor cámara un poco lenta
            vel = max(0.8, hay / d)
            largo = min(d, hay / vel)
        else:
            vel = 1.0
        # fin natural de la toma (donde cortó el editor original) para poder acomodar el corte ahí
        fin_toma = next((t1 for t0, t1 in F.tomas if t0 - 0.05 <= desde < t1), F.dur) - margen
        fin_toma = min(fin_toma, fin) if hasta is not None else fin_toma
        cola = max(0.0, min(0.6, fin_toma - (desde + largo * vel)))
        cs = F.cuadros(k[0], desde, largo * vel + cola); k[0] += 1
        if len(cs) < 3:
            print('Sin cuadros:', F.id, f'{desde:.2f}', f'{largo:.2f}', file=sys.stderr)
            F.usados.append((desde - margen, desde + largo * vel + margen))   # no volver a intentar ese tramo
            return 0.0
        tramos.append(dict(a=a, b=a + largo, tipo='video', cuadros=cs, vel=vel, F=F, desde=desde, fin_toma=fin_toma, off=0.0))
        F.usados.append((desde - margen, desde + largo * vel + cola + margen))
        return largo

    def rellenar(a, b, e=None):
        primera = True
        while b - a > 0.05:
            d, cubierto = b - a, 0.0
            if primera and e and e.get('desde') is not None:
                F = por_url.get(e.get('video'), principal) if isinstance(e.get('video'), str) else principal
                if F:
                    h = e.get('hasta')
                    cubierto = poner_video(F, a, d, float(e['desde']), float(h) if h is not None else None)
            elif primera and e and e.get('video') in por_url:
                F = por_url[e['video']]
                tl = F.toma_libre(min(TOMA_MIN, d))
                if tl:
                    cubierto = poner_video(F, a, d, *tl)
            primera = False
            if not cubierto:
                for F in fuentes_todas:                  # toma nueva: primero la campaña, luego los videos extra
                    tl = F.toma_libre(min(TOMA_MIN, d))
                    if tl:
                        cubierto = poner_video(F, a, d, *tl)
                        if cubierto:
                            break
            if not cubierto and not fuentes_todas:       # solo si no hay ningún video se usa una foto
                im = foto_libre()
                if im:
                    poner_foto(a, min(b, a + max(2.5, min(d, 4.5))), im)
                    cubierto = tramos[-1]['b'] - a
            if not cubierto and fuentes_todas:          # ya no queda nada nuevo: la toma más larga menos usada
                opciones = [(F, t0, t1) for F in fuentes_todas for t0, t1 in F.tomas if t1 - t0 >= min(TOMA_MIN, d)]
                if opciones:
                    F, t0, t1 = max(opciones, key=lambda o: (-sum(1 for x, y in o[0].usados if x < o[2] and y > o[1]), o[2] - o[1]))
                    cubierto = poner_video(F, a, d, t0, t1)
            if not cubierto:
                estirar(b)
                break
            a += cubierto
            if b - a < 0.3:
                estirar(b)
                break

    def estirar(b):
        if not tramos:
            return
        L = tramos[-1]
        if L['tipo'] == 'video' and b > L['b']:
            L['vel'] *= (L['b'] - L['a']) / (b - L['a'])
        L['b'] = max(L['b'], b)

    for i, e in enumerate(escenas):
        a = 0.0 if i == 0 else max(0.0, ini[i] - 0.08)
        b = fin_cuerpo if i == len(escenas) - 1 else max(a + 0.3, ini[i + 1] - 0.08)
        if not (principal or extras) and ((e.get('ver') or '').lower() == 'foto' or e.get('foto')):   # Sergio: puro video
            ref = e.get('foto')
            im = bajar_foto(data.get(ref) if ref in ('img', 'img2') else ref, tmp, i)
            if im:
                poner_foto(a, b, im)
                continue
        rellenar(a, b, e)
    # cierre: la última toma de la campaña (normalmente el producto o el logo) detrás del CTA
    hecho = 0.0
    if principal and principal.tomas and not PANTALLA_COMPLETA:   # en TikTok el final del tráiler son logos y avisos
        t0, t1 = principal.tomas[-1]
        hecho = poner_video(principal, fin_cuerpo, total - fin_cuerpo, t0, t1)
    if not hecho:
        rellenar(fin_cuerpo, total)
    estirar(total)
    ajustar_cortes(tramos)
    return tramos


def ajustar_cortes(tramos):
    """Mueve cada corte (máx. 0.5 s) al punto donde el editor original cambió de toma: así los cortes caen
    en movimientos naturales y no a media acción."""
    for i in range(len(tramos) - 1):
        L, N = tramos[i], tramos[i + 1]
        if L['tipo'] != 'video' or L.get('fin_toma') is None:
            continue
        c = L['a'] + (L['fin_toma'] - L['desde']) / L['vel'] - L['off']
        ultimo = L['a'] + (len(L['cuadros']) - 1) / FPS / L['vel'] - L['off']
        if L['b'] < c <= min(L['b'] + 0.5, ultimo) and N['b'] - c >= 1.0:
            d = c - L['b']
            L['b'] = c; N['a'] = c; N['off'] = N.get('off', 0.0) + d
        elif L['b'] - 0.45 <= c < L['b'] and c - L['a'] >= 1.0:
            d = L['b'] - c
            if N['tipo'] == 'video':
                cabe = (len(N['cuadros']) - 1) / FPS / N['vel'] - N.get('off', 0.0)
                if cabe < (N['b'] - N['a']) + d:
                    continue
            L['b'] = c; N['a'] = c


def imagen_tramo(tr, tl):
    """Imagen del tramo en su segundo local tl (siempre video o foto)."""
    if tr['tipo'] == 'video':
        F, cs = tr['F'], tr['cuadros']
        pos = (tl + tr.get('off', 0.0)) * tr['vel'] * FPS + 1e-6
        i0 = min(len(cs) - 1, int(pos))
        im = vertical(F.abrir(cs[i0]), F.foco)
        f = pos - int(pos)
        if tr['vel'] < 1 and f > 0.08 and i0 + 1 < len(cs):     # cámara lenta: mezcla los dos cuadros vecinos
            im = Image.blend(im, vertical(F.abrir(cs[i0 + 1]), F.foco), f)
        return im.convert('RGBA')
    if 'base' not in tr:
        tr['base'] = vertical(tr['im'], tr['foco'])
    d = max(0.5, tr['b'] - tr['a'])
    z = 1.0 + 0.04 * cl(tl / d)                        # acercamiento muy lento y continuo
    w, h = W / z, H / z
    x0, y0 = (W - w) / 2, (H - h) * 0.45
    return tr['base'].resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + w, y0 + h)).convert('RGBA')


def videos_extra(data, escenas, tmp):
    """Videos de apoyo: los que puso el redactor ("videos" y los "video" de cada escena)."""
    urls = []
    for u in list(data.get('videos') or []) + [e.get('video') for e in escenas]:
        if isinstance(u, str) and (u.startswith('http') or os.path.exists(u)) and u not in urls:
            urls.append(u)
    out = []
    for i, u in enumerate(urls[:12]):
        ruta = u if os.path.exists(u) else f'{tmp}/extra{i}.mp4'
        if ruta == u or bajar_url(u, ruta):
            try:
                F = Fuente(ruta, tmp, u)
                if F.dur >= 1.5:
                    out.append(F)
            except Exception as e:
                print('Video extra:', u, e, file=sys.stderr)
    return out


# palabras que la voz de IA acentúa mal en cualquier nota (verbos en -iar que se conjugan como "cambiar")
PRON_FIJA = {'financian': 'finánsian', 'financia': 'finánsia', 'financiamos': 'finansiámos',
             'Beetlejuice': 'Bítelyus'}


def pronunciado(texto, pron):
    """Cambia los nombres extranjeros por cómo se dicen en español de México ("Bill Murray" -> "Bil Mórrei")
    solo para la voz; los subtítulos se quedan con la escritura real."""
    for orig in sorted(pron, key=len, reverse=True):
        texto = re.sub(r'(?<!\w)' + re.escape(orig) + r'(?!\w)', pron[orig], texto, flags=re.I)
    # sin puntos suspensivos: la voz los lee como pausas largas y el Reel pierde ritmo
    texto = re.sub(r'\s*(\.\.\.|…)\s*', ', ', texto)
    texto = re.sub(r',\s*([,.!?¡¿])', r'\1', texto)
    return texto


def apretar(mp3, palabras, salida, max_sil=0.12):
    """Quita los silencios largos entre frases (los deja en ~0.12 s) sin acelerar la voz, y recorre los tiempos
    de cada palabra para que los subtítulos y los cortes sigan cayendo justo."""
    import numpy as np
    p = subprocess.run(['ffmpeg', '-hide_banner', '-i', mp3, '-af', 'silencedetect=n=-34dB:d=0.16', '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=120).stderr
    ini = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', p)]
    fin = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', p)]
    cortes = [(a + max_sil / 2, b - max_sil / 2) for a, b in zip(ini, fin) if b - a > max_sil and a > 0.05]
    if not cortes:
        return mp3, palabras
    sr = 44100
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-f', 's16le', '-ac', '2', '-ar', str(sr), '-'],
                         capture_output=True, timeout=120).stdout
    x = np.frombuffer(pcm, np.int16).reshape(-1, 2)
    partes, t = [], 0.0
    for a, b in cortes:
        partes.append(x[int(t * sr):int(a * sr)]); t = b
    partes.append(x[int(t * sr):])
    y = np.concatenate(partes)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ac', '2', '-ar', str(sr), '-i', '-', '-b:a', '192k', salida],
                   input=y.tobytes(), check=True, timeout=120)

    def mover(tt):
        quita = 0.0
        for a, b in cortes:
            if tt >= b:
                quita += b - a
            elif tt > a:
                quita += tt - a
        return tt - quita
    print('Pausas recortadas:', len(cortes), f'{sum(b - a for a, b in cortes):.1f}s', file=sys.stderr)
    return salida, [(mover(a), mover(b), w) for a, b, w in palabras]


def restaurar(palabras, pron):
    """En los tiempos de la voz, vuelve a poner la escritura real de cada nombre que se pronunció distinto."""
    for orig, fon in pron.items():
        f = [_norm(w) for w in fon.split() if _norm(w)]
        o = orig.split()
        if not f or not o:
            continue
        out, i = [], 0
        while i < len(palabras):
            ventana = [_norm(w) for _, _, w in palabras[i:i + len(f)]]
            if ventana == f:
                a, b = palabras[i][0], palabras[i + len(f) - 1][1]
                cola = re.sub(r'^.*?([.,;:?!…]*)$', r'\1', palabras[i + len(f) - 1][2])
                paso = (b - a) / len(o)
                for k, w in enumerate(o):
                    out.append((a + k * paso, a + (k + 1) * paso, w + (cola if k == len(o) - 1 else '')))
                i += len(f)
            else:
                out.append(palabras[i]); i += 1
        palabras = out
    return palabras


def make(data, out, tiktok=False):
    """tiktok=True: misma voz y guion, pero video a pantalla completa, sin intro ni final del tráiler
    y con el titular completo desde el primer cuadro (en TikTok la gente decide en el segundo 1)."""
    import voz
    tmp = tempfile.mkdtemp()
    global FPS, PANTALLA_COMPLETA
    PANTALLA_COMPLETA = bool(tiktok)
    try:
        escenas = escenas_de(data)
        pron = dict(PRON_FIJA)
        pron.update({k: v for k, v in (data.get('pronunciar') or {}).items() if k and v})
        grabada = data.get('voz_audio') if data.get('voz_audio') and os.path.exists(data['voz_audio']) else None
        cache_mp3, cache_js = os.path.join(os.path.dirname(out) or '.', 'voz.mp3'), os.path.join(os.path.dirname(out) or '.', 'voz.json')
        reusar = tiktok and not grabada and os.path.exists(cache_mp3) and os.path.exists(cache_js)
        if reusar:    # versión TikTok: la misma voz del Reel de Instagram (no se gastan créditos de ElevenLabs otra vez)
            mp3 = f'{tmp}/voz_apretada.mp3'; shutil.copy(cache_mp3, mp3)
            c = json.load(open(cache_js, encoding='utf-8'))
            palabras, dvoz = [tuple(x) for x in c['palabras']], c['dvoz']
        elif grabada:   # voz que Sergio ya generó (ElevenLabs): se le acortan los silencios largos y se alinea con el guion
            mp3 = f'{tmp}/voz.mp3'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', grabada, '-af',
                            'silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-38dB:stop_silence=0.22',
                            '-ar', '44100', mp3], check=True)
            palabras, dvoz = voz.alinear(mp3, pronunciado(guion_de(data), pron))
        else:
            (palabras, dvoz), mp3 = voz.sintetizar(pronunciado(guion_de(data), pron), f'{tmp}/voz.mp3')
        if not reusar:
            palabras = restaurar(palabras, pron)      # los subtítulos salen con la escritura correcta
            if mp3:                                   # ritmo: sin silencios largos entre frases (la voz no se acelera)
                mp3, palabras = apretar(mp3, palabras, f'{tmp}/voz_apretada.mp3')
                dvoz = max([b for _, b, _ in palabras] + [0]) + 0.15
                try:                                  # se guarda para armar la versión de TikTok con la misma voz
                    shutil.copy(mp3, cache_mp3)
                    json.dump({'palabras': [list(x) for x in palabras], 'dvoz': dvoz}, open(cache_js, 'w', encoding='utf-8'))
                except Exception as e:
                    print('No guardé la voz:', e, file=sys.stderr)
        total = TOTAL
        # la voz tiene que caber en el minuto: si se pasa, se acelera un poco (máx. 25 %) sin cambiar el tono
        cabe = total - CIERRE_MIN - INICIO_VOZ - 0.4
        if grabada:            # con voz grabada, la última frase (el CTA hablado) puede sonar debajo del cierre
            cabe = total - INICIO_VOZ - 0.5
        tempo = 1.0
        if mp3 and dvoz > cabe:
            tempo = min(1.25, dvoz / cabe)
            palabras = [(a / tempo, b / tempo, w) for a, b, w in palabras]
            dvoz /= tempo
        palabras = [(a + INICIO_VOZ, b + INICIO_VOZ, w) for a, b, w in palabras]
        fin_cuerpo = min(total - CIERRE_MIN, INICIO_VOZ + dvoz + 0.5)
        L = preparar(data)
        vid = bajar_video(data, tmp)
        for u in ([] if vid else (data.get('videos') or [])):   # sin video de la campaña: el primer video real de apoyo
            if bajar_url(u, f'{tmp}/campana.mp4'):
                vid = f'{tmp}/campana.mp4'
                print('Video principal (de apoyo):', u, file=sys.stderr)
                break
        if not vid:
            raise RuntimeError('La nota no tiene video de la campaña para el Reel')
        FPS = fps_de(vid)                                   # se arma a los cuadros por segundo del video original
        principal = Fuente(vid, tmp, 'campana')
        if principal.dur < 2:
            raise RuntimeError('No pude sacar el video de la campaña')
        extras = videos_extra(data, escenas, tmp)
        ini = tiempos(escenas, palabras, voz.limpiar)
        tramos = plan(escenas, ini, fin_cuerpo, total, principal, extras, data, tmp)
        print('Reel:', [(round(x['a'], 1), round(x['b'], 1), x['tipo'] + ('' if x['tipo'] == 'foto' else str(x['F'].id))) for x in tramos],
              file=sys.stderr)
        G = [g for g in grupos(palabras)]
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-']
        # tope de bitrate: el Reel de 1 minuto queda en ~18 MB (Cloudflare Pages rechaza archivos de más de 25 MB
        # y si uno se pasa, la página entera deja de actualizarse)
        pr = subprocess.Popen(cmd + ['-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-maxrate', '2300k', '-bufsize', '4600k',
                                     '-pix_fmt', 'yuv420p',
                                     '-r', str(FPS), f'{tmp}/video.mp4'], stdin=subprocess.PIPE)
        ti = 0
        for i in range(int(round(total * FPS))):
            t = i / FPS
            while ti < len(tramos) - 1 and t >= tramos[ti]['b'] - 1e-6:
                ti += 1
            tr = tramos[ti]
            im = imagen_tramo(tr, max(0.0, t - tr['a']))      # corte directo, limpio, al ritmo de la voz
            im.alpha_composite(L['abajo']); im.alpha_composite(L['arriba'], (0, 0))
            paste(im, L['brand'], M, 150)
            if t < GANCHO:
                gancho(im, t + (1.0 if PANTALLA_COMPLETA else 0.0), L)
            else:
                if L['marca']:
                    paste(im, L['marca'], M, 230, eo(lin(t, GANCHO, GANCHO + .4)))
                if t >= fin_cuerpo:
                    cierre(im, t - fin_cuerpo, L)
                else:
                    g = next((g for g in G if g[0][0] - 0.05 <= t <= g[-1][1] + 0.25), None)
                    if g:
                        s = subtitulo(g, t)
                        paste(im, s, (W - s.width) / 2, 1380)
            buf = __import__('io').BytesIO()
            im.convert('RGB').save(buf, 'JPEG', quality=90)
            pr.stdin.write(buf.getvalue())
        pr.stdin.close(); pr.wait()
        if pr.returncode:
            raise RuntimeError('ffmpeg falló armando el video del Reel')
        # audio: voz + sonido original de cada clip (se baja solo mientras habla la voz) + música bajita
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{tmp}/video.mp4']
        filtros, entradas, bus = [], 1, []
        if mp3:
            ms = int(INICIO_VOZ * 1000)
            cmd += ['-i', mp3]
            filtros.append(f'[{entradas}:a]atempo={tempo:.4f},adelay={ms}|{ms},volume=1.0,apad=whole_dur={total:.3f},asplit=3[v][vsc][vsc2]'); entradas += 1
        for tr in tramos:
            if not SONIDO_ORIGINAL or tr['tipo'] != 'video' or not tr['F'].audio:
                continue
            ini = tr['desde'] + tr.get('off', 0.0) * tr['vel']
            dur = tr['b'] - tr['a']
            cmd += ['-ss', f'{ini:.3f}', '-t', f'{dur * tr["vel"] + 0.05:.3f}', '-i', tr['F'].ruta]
            ms = int(tr['a'] * 1000)
            vel = f'atempo={max(0.5, tr["vel"]):.4f},' if tr['vel'] < 0.999 else ''
            filtros.append(f'[{entradas}:a]aformat=sample_rates=44100:channel_layouts=stereo,{vel}'
                           f'afade=t=in:d=0.03,afade=t=out:st={max(0.0, dur - 0.05):.3f}:d=0.05,'
                           f'adelay={ms}|{ms}[s{entradas}]')
            bus.append(f'[s{entradas}]'); entradas += 1
        if bus:
            filtros.append(f'{"".join(bus)}amix=inputs={len(bus)}:duration=longest:normalize=0,volume=0.9[clips]')
            if mp3:   # cuando habla la voz, el sonido del video baja; en las pausas vuelve a escucharse
                filtros.append('[clips][vsc]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[orig]')
            else:
                filtros.append('[clips]anull[orig]')
        if os.path.exists(MUSIC):
            # la música se oye siempre, pero la voz manda: baja un poco mientras habla y sube en las pausas
            cmd += ['-stream_loop', '-1', '-i', MUSIC]
            if mp3:
                filtros.append(f'[{entradas}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.11,'
                               f'afade=t=out:st={total - 1.8:.2f}:d=1.8[m0]')
                filtros.append(f'[m0][{"vsc2" if bus else "vsc"}]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=450:makeup=1[m]')
            else:
                filtros.append(f'[{entradas}:a]volume=0.9,afade=t=out:st={total - 1.8:.2f}:d=1.8[m]')
            entradas += 1

        if mp3:                                          # salidas de la voz que no se usaron
            usadas = ';'.join(filtros)
            for lab in ('vsc', 'vsc2'):
                if usadas.count(f'[{lab}]') < 2:
                    filtros.append(f'[{lab}]anullsink')
        mez = ('[v]' if mp3 else '') + ('[orig]' if bus else '') + ('[m]' if os.path.exists(MUSIC) else '')
        n_in = mez.count('[')
        if n_in:
            filtros.append(f'{mez}amix=inputs={n_in}:duration=longest:normalize=0,alimiter=limit=0.95[a]' if n_in > 1 else f'{mez}anull[a]')
            cmd += ['-filter_complex', ';'.join(filtros), '-map', '0:v', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k']
        cmd += ['-c:v', 'copy', '-t', f'{total:.3f}', '-movflags', '+faststart', out]
        subprocess.run(cmd, check=True)
        if os.path.getsize(out) > 22 * 1024 * 1024:     # seguro extra: nunca más de 22 MB
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c:v', 'libx264', '-preset', 'medium', '-b:v', '2000k',
                            '-maxrate', '2000k', '-bufsize', '4000k', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                            '-movflags', '+faststart', f'{tmp}/chico.mp4'], check=True)
            shutil.move(f'{tmp}/chico.mp4', out)
        return out
    finally:
        PANTALLA_COMPLETA = False
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2], tiktok='--tiktok' in sys.argv)
