"""Reel vertical (1080x1920, 30 fps, 15 a 40 s) de una nota, con branding de Newsbrand.

Uso: python scripts/reel.py datos.json salida.mp4
datos: img, img2, fotos (lista opcional), etiqueta, portada, titulo, marca, guion (texto de la voz),
       src (URL de la nota, para sacar clips del video de la campaña) o video (ruta local a un MP4).

Estructura:
  1) Gancho (0 a ~3 s): foto o clip de la campaña con el titular grande y el marcatextos rosa.
  2) Cuerpo: el video de la campaña corriendo de corrido, en horizontal al centro sobre su propio fondo
     desenfocado en morado, con subtítulos tipo karaoke sincronizados con la voz en off.
  3) Cierre morado uva (3 s): "¿Quieres saber más de esta nota?" + link en la bio.
Solo se arma si la nota tiene video de la campaña (no usa fotos).
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
MUSIC = os.path.join(R, 'assets', 'audio', 'reel.m4a')
GANCHO, CIERRE, INICIO_VOZ, SEG = 3.2, 3.0, 0.35, 2.6


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
    if im.height > im.width:                         # video vertical: a pantalla completa
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


def video_corrido(ruta, tmp, segundos):
    """Cuadros del video de la campaña, una sola pasada (máximo lo que dure el Reel)."""
    carpeta = f'{tmp}/video'; os.makedirs(carpeta, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '0.2', '-i', ruta, '-t', f'{segundos:.2f}',
                    '-vf', f'fps={FPS},scale=min(1920\\,iw):-2', '-q:v', '2', f'{carpeta}/%05d.jpg'], capture_output=True, timeout=600)
    return sorted(glob.glob(f'{carpeta}/*.jpg'))


def bajar_video(data, tmp):
    if data.get('video') and os.path.exists(data['video']):
        return data['video']
    try:
        import fuentes, requests
        urls = [data['mp4']] if data.get('mp4') else (fuentes.mp4s_de_pagina(data['src']) if data.get('src') else [])
        for u in urls:
            r = requests.get(u, headers=fuentes.UA, timeout=90, stream=True)
            if r.status_code != 200:
                continue
            ruta = f'{tmp}/campana.mp4'; tam = 0
            with open(ruta, 'wb') as f:
                for ch in r.iter_content(1 << 16):
                    tam += len(ch)
                    if tam > 150 * 1024 * 1024:
                        break
                    f.write(ch)
            return ruta
    except Exception as e:
        print('Video de campaña:', e, file=sys.stderr)
    return None


TRANS = 0.6   # segundos de la transición cuando el video vuelve a empezar


CORTE = [None]   # caja sin franjas negras del video (si el video vertical viene dentro de un cuadro horizontal)


def sin_bordes(cuadros):
    """Detecta franjas negras fijas (arriba/abajo o a los lados) en el video y regresa la caja útil."""
    from PIL import ImageChops
    caja = None
    n = len(cuadros)
    for i in range(1, 10):
        im = Image.open(cuadros[min(n - 1, int(n * i / 10))]).convert('L')
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


def abrir(cuadros, i):
    im = Image.open(cuadros[i])
    return im.crop(CORTE[0]) if CORTE[0] else im


def cuadro_fondo(cuadros, foco, t):
    """Cuadro del video en el segundo t. Si el video es más corto que el Reel, se repite y el cambio
    del final al inicio se hace con una transición suave (fundido con un leve acercamiento)."""
    n = len(cuadros)
    dur = n / FPS
    ciclo = max(0.5, dur - TRANS)                     # cada vuelta empieza TRANS segundos antes de acabar la anterior
    k = int(t // ciclo)
    local = t - k * ciclo                             # tiempo dentro de la vuelta actual
    actual = vertical(abrir(cuadros, min(n - 1, int(local * FPS))), foco)
    if k > 0 and local < TRANS:                       # mezcla con el final de la vuelta anterior
        prev_t = local + ciclo
        prev = vertical(abrir(cuadros, min(n - 1, int(prev_t * FPS))), foco)
        a = local / TRANS
        a = a * a * (3 - 2 * a)
        z = 1 + 0.04 * (1 - a)                        # el video nuevo entra con un pequeño acercamiento
        if z != 1:
            w, h = actual.size
            actual = actual.resize((int(w * z), int(h * z)), Image.BILINEAR).crop(
                (int((w * z - w) / 2), int((h * z - h) / 2), int((w * z - w) / 2) + w, int((h * z - h) / 2) + h))
        return Image.blend(prev, actual, a)
    return actual


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
        'cta': text_block('¿Quieres saber _más_ de esta nota?', W - 2 * M, 3, 'lg-black.woff2', 128, 80, WHITE, it_color=ROSA),
        'cta2': body_block('Léela completa en guayabailustrada.com.mx', W - 2 * M, 44, WHITE, 2),
        'bio': pill('LINK EN LA BIO  →', font('lg-black.woff2', 46), ROSA, UVA, 54, 30),
        'firma': text_block('LG.I', 400, 1, 'lg-bold.woff2', 110, 100, WHITE, track=-0.05),
        'sigue': pill('@lgi.newsbrand', font('lg-bold.woff2', 36), WHITE, UVA, 30, 16),
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


def cierre(t, L):
    im = Image.new('RGBA', (W, H), UVA)
    cta = L['cta']; a = eo(lin(t, .15, .7)); y = 560
    paste(im, cta, M - 20, y + (1 - a) * 60, a)
    y += cta.height + 30
    b = eo(lin(t, .45, 1.0)); paste(im, L['cta2'], M - 10, y + (1 - b) * 40, b)
    y += L['cta2'].height + 70
    c = eo(lin(t, .7, 1.1)); pulso = 1 - 0.04 * max(0.0, math.sin(max(0, t - 1.2) * math.pi / 0.9)) ** 8
    bio = L['bio']
    k = c * pulso
    if k != 1:
        bio = bio.resize((max(1, int(bio.width * k)), max(1, int(bio.height * k))), Image.BILINEAR)
    paste(im, bio, M + (L['bio'].width - bio.width) / 2, y + (L['bio'].height - bio.height) / 2, min(1, c))
    paste(im, L['firma'], M - 20, 1480, eo(lin(t, 1.0, 1.5)))
    paste(im, L['sigue'], W - M - L['sigue'].width, 1510, eo(lin(t, 1.1, 1.6)))
    return im


def guion_de(data):
    g = (data.get('guion') or '').strip()
    if g:
        return g
    partes = [re.sub(r'[*_\[\]]', '', data.get('portada', '')).strip().rstrip('.') + '.']
    if data.get('resumen'):
        partes.append(re.sub(r'[\[\]]', '', data['resumen']))
    info = data.get('info') or []
    if info:
        partes.append(re.sub(r'[\[\]]', '', info[0]))
    partes.append('La nota completa está en el link de la bio.')
    return ' '.join(partes)


def make(data, out):
    import voz
    tmp = tempfile.mkdtemp()
    try:
        (palabras, dvoz), mp3 = voz.sintetizar(guion_de(data), f'{tmp}/voz.mp3')
        palabras = [(a + INICIO_VOZ, b + INICIO_VOZ, w) for a, b, w in palabras]
        total = max(15.0, min(48.0, INICIO_VOZ + dvoz + 0.5 + CIERRE))   # nunca se corta la voz
        fin_cuerpo = total - CIERRE
        L = preparar(data)
        vid = bajar_video(data, tmp)
        if not vid:
            raise RuntimeError('La nota no tiene video de la campaña para el Reel')
        cuadros = video_corrido(vid, tmp, total)
        if len(cuadros) < FPS * 3:
            raise RuntimeError('No pude sacar el video de la campaña')
        import encuadre
        CORTE[0] = sin_bordes(cuadros)                      # un video vertical metido en cuadro horizontal sale a pantalla completa
        foco = encuadre.foco(abrir(cuadros, len(cuadros) // 3).convert('RGB'))
        G = [g for g in grupos(palabras)]
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-']
        pr = subprocess.Popen(cmd + ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                                     '-r', str(FPS), f'{tmp}/video.mp4'], stdin=subprocess.PIPE)
        for i in range(int(total * FPS)):
            t = i / FPS
            if t >= fin_cuerpo:
                im = cierre(t - fin_cuerpo, L)
                if t - fin_cuerpo < 0.3:                   # transición: el cierre sube desde abajo
                    k = eio((t - fin_cuerpo) / 0.3)
                    prev = Image.new('RGBA', (W, H), UVA)
                    prev.alpha_composite(im, (0, int(H * (1 - k))))
                    im = prev
            else:
                im = cuadro_fondo(cuadros, foco, t).convert('RGBA')
                im.alpha_composite(L['abajo']); im.alpha_composite(L['arriba'], (0, 0))
                paste(im, L['brand'], M, 150)
                if t < GANCHO:
                    gancho(im, t, L)
                else:
                    if L['marca']:
                        paste(im, L['marca'], M, 230, eo(lin(t, GANCHO, GANCHO + .4)))
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
        # audio: voz + música bajita (y si no hubo voz, solo música)
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{tmp}/video.mp4']
        filtros, entradas = [], 1
        if mp3:
            cmd += ['-i', mp3]; filtros.append(f'[{entradas}:a]adelay={int(INICIO_VOZ * 1000)}|{int(INICIO_VOZ * 1000)},volume=1.0[v]'); entradas += 1
        if os.path.exists(MUSIC):
            cmd += ['-stream_loop', '-1', '-i', MUSIC]
            vol = 0.14 if mp3 else 0.9
            filtros.append(f'[{entradas}:a]volume={vol},afade=t=out:st={total - 1.5:.2f}:d=1.5[m]'); entradas += 1
        if filtros:
            mez = ''.join(x for x in ('[v]' if mp3 else '', '[m]' if os.path.exists(MUSIC) else ''))
            n_in = mez.count('[')
            if n_in > 1:
                filtros.append(f'{mez}amix=inputs={n_in}:duration=longest:normalize=0[a]')
            else:
                filtros.append(f'{mez}anull[a]')
            cmd += ['-filter_complex', ';'.join(filtros), '-map', '0:v', '-map', '[a]', '-c:a', 'aac', '-b:a', '160k']
        cmd += ['-c:v', 'copy', '-t', f'{total:.2f}', '-movflags', '+faststart', out]
        subprocess.run(cmd, check=True)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2])
