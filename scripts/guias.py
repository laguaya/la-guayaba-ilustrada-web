"""Guías LGI: video vertical de contenido guardable (pasos, resúmenes, calendarios), con voz.
Diseño propio, distinto al de las notas: papel crema con cuadrícula, titulares en serif, rosa neón como
marcatextos, tarjetas negras y barra de avance. Uso: make(data, salida) con data = r['ig'] de drafts/reels/<id>.json
cuando "formato" es "guia". Cada escena trae su "voz"; la escena dura lo que dura su voz.
"""
import sys, os, io, math, subprocess, glob, shutil, tempfile
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
from PIL import Image, ImageDraw, ImageFilter
from portada import font

W, H, FPS = 1080, 1920, 30
PAPEL, LINEA, INK, PINK, CREMA2, WHITE = '#F3EEE4', '#E3DACB', '#0B0B0B', '#FF3674', '#FBF8F2', '#FFFFFF'
M = 80
MUSIC = os.path.join(R, 'assets', 'audio', 'musica', 'uplifting-hiphop-jazz-funk-60.mp3')


def cl(x, a=0., b=1.): return max(a, min(b, x))
def eo(x): x = cl(x); return 1 - (1 - x) ** 3
def back(x):
    x = cl(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def fondo():
    im = Image.new('RGB', (W, H), PAPEL); d = ImageDraw.Draw(im)
    for x in range(0, W, 60): d.line((x, 0, x, H), fill=LINEA, width=1)
    for y in range(0, H, 60): d.line((0, y, W, y), fill=LINEA, width=1)
    return im


PUNT = '.,;:!?"\''


def wrap(d, text, f, maxw):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t.replace('*', ''), font=f) <= maxw: cur = t
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out


def texto(text, size, maxw, fuente='serif.woff2', color=INK, lh=1.12, marca=PINK, max_lines=6, min_size=40):
    """Capa RGBA con texto; *palabras* llevan marcatextos rosa detrás."""
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    while True:
        f = font(fuente, size); ls = wrap(d0, text, f, maxw)
        if len(ls) <= max_lines or size <= min_size: break
        size -= 4
    alto = int(len(ls) * size * lh + size * 0.4)
    im = Image.new('RGBA', (maxw + 20, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    y = 0; dentro = False
    for ln in ls:
        x = 0
        for i, w in enumerate(ln.split()):
            ini, fin = w.startswith('*'), w.rstrip(PUNT).endswith('*')
            if ini: dentro = True
            limpio = w.replace('*', '')
            pal = limpio + (' ' if i < len(ln.split()) - 1 else '')
            ww = d.textlength(pal, font=f)
            if dentro:
                d.rectangle((x - 6, y + size * 0.38, x + d.textlength(limpio, font=f) + 6, y + size * 1.02), fill=marca)
            d.text((x, y), pal, font=f, fill=color)
            x += ww
            if fin: dentro = False
        y += size * lh
    return im


def pill(text, size, bg=INK, fg=PAPEL, padx=30, pady=16, fuente='lg-black.woff2'):
    f = font(fuente, size); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    w = int(d0.textlength(text, font=f)); a, de = f.getmetrics()
    im = Image.new('RGBA', (w + 2 * padx, a + de + 2 * pady), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=bg)
    d.text((padx, pady), text, font=f, fill=fg)
    return im


def marcador(color=PINK):
    """Ícono de marcador (guardar) dibujado."""
    im = Image.new('RGBA', (56, 72), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(4, 0), (52, 0), (52, 70), (28, 50), (4, 70)], fill=color)
    return im


def barra(t, total, paso, pasos):
    """Encabezado fijo: sello de la serie + 'guárdalo' + avance."""
    im = Image.new('RGBA', (W, 230), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    p = pill('GUÍAS LGI', 30); im.alpha_composite(p, (M, 90))
    g = pill('GUÁRDALO', 30, bg=PINK, fg=INK, padx=70); im.alpha_composite(g, (W - M - g.width, 90))
    im.alpha_composite(marcador(INK).resize((28, 36)), (W - M - g.width + 24, 90 + (g.height - 36) // 2))
    # avance
    if pasos:
        ancho = (W - 2 * M - (pasos - 1) * 12) / pasos
        for i in range(pasos):
            x = M + i * (ancho + 12)
            d.rounded_rectangle((x, 190, x + ancho, 200), 5, fill=INK if i < paso else LINEA)
    return im


def tarjeta_foto(ruta, w, h, ang=-2.5):
    im = Image.open(ruta).convert('RGB')
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    x = (im.width - w) // 2; y = int((im.height - h) * 0.4); im = im.crop((x, y, x + w, y + h))
    marco = Image.new('RGBA', (w + 28, h + 28), WHITE)
    mk = Image.new('L', marco.size, 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, marco.width - 1, marco.height - 1), 26, fill=255)
    marco.paste(im, (14, 14)); marco.putalpha(mk)
    sombra = Image.new('RGBA', (marco.width + 60, marco.height + 60), (0, 0, 0, 0))
    sm = Image.new('L', sombra.size, 0); ImageDraw.Draw(sm).rounded_rectangle((30, 40, 30 + marco.width, 40 + marco.height), 26, fill=70)
    sombra.putalpha(sm.filter(ImageFilter.GaussianBlur(18)))
    sombra.alpha_composite(marco, (30, 30))
    return sombra.rotate(ang, resample=Image.BICUBIC, expand=True)


def caja(titulo, cuerpo, w, fondo_=INK, fg=PAPEL, acento=PINK):
    t = texto(cuerpo, 44, w - 80, 'lg-regular.woff2', fg, lh=1.32, max_lines=6, min_size=30)
    lab = font('lg-black.woff2', 30)
    alto = t.height + 120
    im = Image.new('RGBA', (w, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, alto - 1), 34, fill=fondo_)
    d.text((40, 38), titulo, font=lab, fill=acento)
    im.alpha_composite(t, (40, 90))
    return im


class Escena:
    def __init__(self, dur, piezas, paso=0):
        self.dur, self.piezas, self.paso = dur, piezas, paso   # piezas: (capa, x, y, t_entra, efecto)


def pinta(base, capa, x, y, a, dy=0, escala=1.0):
    if a <= 0: return
    c = capa
    if escala != 1.0:
        c = c.resize((max(1, int(c.width * escala)), max(1, int(c.height * escala))), Image.BICUBIC)
        x += (capa.width - c.width) / 2; y += (capa.height - c.height) / 2
    if a < 1:
        c = c.copy(); c.putalpha(c.getchannel('A').point(lambda v: int(v * a)))
    base.alpha_composite(c, (int(x), int(y + dy)))


def render(escenas, pasos, out, voces=None):
    """voces: lista de (mp3, inicio_en_segundos) que se mezclan encima de la música."""
    tmp = out + '.video.mp4'
    pr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    base0 = fondo().convert('RGBA')
    total = sum(e.dur for e in escenas)
    for e in escenas:
        n = int(e.dur * FPS)
        for i in range(n):
            t = i / FPS
            im = base0.copy()
            im.alpha_composite(barra(t, total, e.paso, pasos), (0, 0))
            sale = cl((t - (e.dur - 0.35)) / 0.35)
            for capa, x, y, te, ef in e.piezas:
                p = (t - te) / 0.55
                if ef == 'rebote':
                    pinta(im, capa, x, y, cl(p * 2) * (1 - sale), 0, 0.6 + 0.4 * back(p))
                elif ef == 'flota':
                    pinta(im, capa, x, y, cl(p * 2) * (1 - sale), (1 - eo(p)) * 60 + math.sin(t * 1.4) * 6)
                else:
                    pinta(im, capa, x, y, eo(p) * (1 - sale), (1 - eo(p)) * 50 - sale * 30)
            b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=90); pr.stdin.write(b.getvalue())
    pr.stdin.close(); pr.wait()
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp, '-stream_loop', '-1', '-i', MUSIC]
    voces = [v for v in (voces or []) if v[0] and os.path.exists(v[0])]
    for mp3, _ in voces:
        cmd += ['-i', mp3]
    vol = 0.11 if voces else 0.55
    f = [f'[1:a]volume={vol},afade=t=in:d=0.6,afade=t=out:st={total - 1.5:.2f}:d=1.5,atrim=0:{total:.2f}[m]']
    mez = '[m]'
    for k, (_, ini) in enumerate(voces):
        ms = int(ini * 1000)
        f.append(f'[{k + 2}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={ms}|{ms}[v{k}]'); mez += f'[v{k}]'
    f.append(f'{mez}amix=inputs={1 + len(voces)}:duration=first:normalize=0,alimiter=limit=0.95[a]')
    subprocess.run(cmd + ['-filter_complex', ';'.join(f), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                          '-t', f'{total:.2f}', '-movflags', '+faststart', out], check=True)
    os.remove(tmp)


def portada(foto, etiqueta, titulo, sub, dur=4.5, fotos=None):
    pz = []
    if fotos:
        for k, fp in enumerate(fotos[:3]):
            c = tarjeta_foto(fp, 560, 420, ang=[-6, 4, -2][k])
            pz.append((c, [M - 20, W - M - c.width + 20, (W - c.width) / 2][k], [300, 380, 560][k], 0.1 + k * 0.25, 'flota'))
        ty = 1130
    elif foto:
        c = tarjeta_foto(foto, 900, 700)
        pz.append((c, (W - c.width) / 2, 300, 0.1, 'flota')); ty = 1160
    else:
        ty = 760
    e = pill(etiqueta, 30, bg=PINK, fg=INK); pz.append((e, M, ty, 0.3, 'rebote'))
    tt = texto(titulo, 116, W - 2 * M, max_lines=4, min_size=70); pz.append((tt, M, ty + 96, 0.5, 'sube'))
    s = texto(sub, 46, W - 2 * M, 'lg-medium.woff2', lh=1.3); pz.append((s, M, ty + 120 + tt.height, 0.9, 'sube'))
    return Escena(dur, pz, 0)


def centrar(capas, gap=40, y_min=270, y_max=1800):
    alto = sum(c.height for c in capas) + gap * (len(capas) - 1)
    y = max(y_min, y_min + (y_max - y_min - alto) / 2)
    pos = []
    for c in capas:
        pos.append(y); y += c.height + gap
    return pos


def paso_escena(n, pasos, titulo, cuerpo, ejemplo, dur=6.0):
    num = texto(f'{n:02d}', 360, 700, 'serif-italic.woff2', PINK, max_lines=1)
    tt = texto(titulo, 104, W - 2 * M, max_lines=3, min_size=70)
    cu = texto(cuerpo, 50, W - 2 * M, 'lg-regular.woff2', lh=1.32, max_lines=5, min_size=36)
    cj = caja('EJEMPLO EN MÉXICO', ejemplo, W - 2 * M)
    ys = centrar([num, tt, cu, cj], gap=44)
    return Escena(dur, [(num, M - 10, ys[0], 0.0, 'rebote'), (tt, M, ys[1], 0.35, 'sube'),
                        (cu, M, ys[2], 0.8, 'sube'), (cj, M, ys[3], 1.5, 'sube')], n)


def lista_escena(titulo, filas, pasos, dur):
    pz = [(texto(titulo, 100, W - 2 * M, max_lines=2), M, 300, 0.0, 'sube')]
    y = 560
    for k, (fecha, dia, evento, idea) in enumerate(filas):
        im = Image.new('RGBA', (W - 2 * M, 230), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, 200, 210), 30, fill=INK)
        d.text((100, 80), fecha, font=font('serif.woff2', 64 if len(fecha) < 4 else 52), fill=PAPEL, anchor='mm')
        d.text((100, 160), dia, font=font('lg-black.woff2', 26), fill=PINK, anchor='mm')
        d.text((236, 18), evento, font=font('serif.woff2', 54), fill=INK)
        im.alpha_composite(texto(idea, 34, W - 2 * M - 250, 'lg-regular.woff2', lh=1.3, max_lines=3, min_size=28), (238, 92))
        pz.append((im, M, y, 0.5 + k * 1.1, 'sube')); y += 255
    return Escena(dur, pz, 1)


def item_escena(n, foto, marca, titulo, cuerpo, pasos, dur=5.0):
    pz = []
    if foto:
        c = tarjeta_foto(foto, 900, 700, ang=[-2, 2][n % 2]); pz.append((c, (W - c.width) / 2, 280, 0.0, 'flota'))
    num = pill(f'#{n}', 56, bg=PINK, fg=INK, padx=36); pz.append((num, M, 1060, 0.3, 'rebote'))
    m = pill(marca.upper(), 30); pz.append((m, M + num.width + 20, 1078, 0.45, 'rebote'))
    tt = texto(titulo, 100, W - 2 * M, max_lines=3, min_size=64); pz.append((tt, M, 1200, 0.6, 'sube'))
    cu = texto(cuerpo, 48, W - 2 * M, 'lg-regular.woff2', lh=1.32, max_lines=4); pz.append((cu, M, 1230 + tt.height, 1.0, 'sube'))
    return Escena(dur, pz, n)


def cierre(titulo, sub, pasos, dur=4.0):
    mk = marcador().resize((200, 258))
    tt = texto(titulo, 124, W - 2 * M, max_lines=3)
    sb = texto(sub, 50, W - 2 * M, 'lg-medium.woff2', lh=1.3)
    b = pill('SÍGUENOS · @lgi.newsbrand', 38, padx=44, pady=26)
    ys = centrar([mk, tt, sb, b], gap=50)
    return Escena(dur, [(mk, M, ys[0], 0.0, 'rebote'), (tt, M, ys[1], 0.3, 'sube'), (sb, M, ys[2], 0.7, 'sube'), (b, M, ys[3], 1.1, 'rebote')], pasos)




def _foto_local(ref, tmp, k):
    if not ref:
        return None
    if os.path.exists(os.path.join(R, ref)):
        return os.path.join(R, ref)
    if str(ref).startswith('http'):
        import requests
        try:
            r = requests.get(ref, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
            ruta = os.path.join(tmp, f'foto{k}.img'); open(ruta, 'wb').write(r.content)
            Image.open(ruta).verify()
            return ruta
        except Exception as e:
            print('Foto guía:', e, file=sys.stderr)
    return None


def make(data, out):
    import voz, reel
    tmp = tempfile.mkdtemp()
    try:
        pron = dict(reel.PRON_FIJA); pron.update({k: v for k, v in (data.get('pronunciar') or {}).items() if k and v})
        esc = data['escenas']
        pasos = sum(1 for e in esc if e.get('tipo') in ('paso', 'item')) or 1
        escenas, voces, t0, n = [], [], 0.0, 0
        for k, e in enumerate(esc):
            mp3, dv = None, 0.0
            if e.get('voz'):
                (pal, dv), mp3 = voz.sintetizar(reel.pronunciado(e['voz'], pron), os.path.join(tmp, f'v{k}.mp3'))
            tipo = e.get('tipo')
            if tipo == 'portada':
                fotos = [f for f in (_foto_local(x, tmp, f'{k}_{j}') for j, x in enumerate(e.get('fotos') or [])) if f]
                foto = _foto_local(e.get('foto'), tmp, k) or (fotos[0] if fotos and len(fotos) == 1 else None)
                sc = portada(foto, e.get('etiqueta', 'GUÍA'), e['titulo'], e.get('sub', ''), fotos=fotos if len(fotos) > 1 else None)
            elif tipo == 'paso':
                n += 1; sc = paso_escena(n, pasos, e['titulo'], e.get('cuerpo', ''), e.get('ejemplo', ''))
            elif tipo == 'item':
                n += 1; sc = item_escena(n, _foto_local(e.get('foto'), tmp, k), e.get('marca', ''), e['titulo'], e.get('cuerpo', ''), pasos)
            elif tipo == 'lista':
                sc = lista_escena(e['titulo'], [tuple(f) for f in e['filas']], pasos, 9.0)
            else:
                sc = cierre(e['titulo'], e.get('sub', ''), pasos)
            if tipo == 'cierre':
                sc.paso = pasos
            sc.dur = max(sc.dur if not e.get('voz') else 3.0, dv + 0.9)
            if tipo == 'lista' and dv:            # las filas aparecen repartidas mientras habla la voz
                filas = sc.piezas[1:]
                for j, (c, x, y, te, ef) in enumerate(filas):
                    filas[j] = (c, x, y, 0.4 + j * max(0.6, (dv - 1.0) / max(1, len(filas))), ef)
                sc.piezas = sc.piezas[:1] + filas
            escenas.append(sc); voces.append((mp3, t0 + 0.25)); t0 += sc.dur
        render(escenas, pasos, out, voces)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
