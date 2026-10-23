"""Estilos de Guías LGI. Cada tipo de guía tiene su propio diseño:
- "playbook" (Cópiale a...): foto a sangre arriba, fondo negro, número gigante rosa, tarjeta blanca de ejemplo con foto.
- "top" (resumen de la semana): cuenta regresiva 3-2-1, foto completa con zoom lento, número enorme y franja superior.
- "calendario" (fechas del mes en México): papel crema, hojas de calendario arrancables, polaroids. Sale en carrusel
  (1080x1350) y en video (las mismas láminas dentro del vertical, pasando como si se deslizaran).
Se elige con data["estilo"]. Las fotos van en assets/libres/<tema>/ (scripts/fotos_libres.py) o assets/work/.
"""
import os, io, math, subprocess, tempfile, shutil, sys
from PIL import Image, ImageDraw, ImageFilter
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
from portada import font
import guias as G
from guias import W, H, FPS, M, cl, eo, back, pinta, wrap, PUNT

PINK, INK, WHITE, PAPEL, LINEA = G.PINK, G.INK, G.WHITE, G.PAPEL, G.LINEA
NEGRO = '#0E0E0E'
GRIS = '#B9B9B9'


# ---------- utilidades ----------
def ruta(ref):
    if not ref: return None
    p = ref if os.path.isabs(ref) else os.path.join(R, ref)
    return p if os.path.exists(p) else None


def cubrir(ref, w, h, foco=0.45):
    im = Image.open(ruta(ref)).convert('RGB')
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x = (im.width - w) // 2; y = int((im.height - h) * foco)
    return im.crop((x, y, x + w, y + h))


def zoom(img, t, dur, z0=1.0, z1=1.08):
    """Ken Burns: acerca poco a poco."""
    z = z0 + (z1 - z0) * cl(t / max(dur, 0.1))
    w, h = img.size; cw, ch = int(w / z), int(h / z)
    x, y = (w - cw) // 2, (h - ch) // 2
    return img.crop((x, y, x + cw, y + ch)).resize((w, h), Image.BILINEAR)


def degradado(w, h, y0, y1, color=(14, 14, 14), a0=0, a1=255):
    g = Image.new('L', (1, h), 0)
    for y in range(h):
        g.putpixel((0, y), int(a0 + (a1 - a0) * cl((y - y0) / max(1, y1 - y0))))
    capa = Image.new('RGBA', (w, h), color + (0,)); capa.putalpha(g.resize((w, h)))
    return capa


def txt(text, size, maxw, fuente='lg-black.woff2', color=WHITE, acento=PINK, lh=1.08, max_lines=6, min_size=34, modo='color'):
    """Texto con *palabras* destacadas: modo 'color' (palabra en rosa) o 'marca' (marcatextos)."""
    if modo == 'marca':
        return G.texto(text, size, maxw, fuente, color, lh=lh, marca=acento, max_lines=max_lines, min_size=min_size)
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    while True:
        f = font(fuente, size); ls = wrap(d0, text, f, maxw)
        if len(ls) <= max_lines or size <= min_size: break
        size -= 4
    im = Image.new('RGBA', (maxw + 20, int(len(ls) * size * lh + size * 0.35)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    y, dentro = 0, False
    for ln in ls:
        x = 0; pals = ln.split()
        for i, w in enumerate(pals):
            if w.startswith('*'): dentro = True
            fin = w.rstrip(PUNT).endswith('*')
            pal = w.replace('*', '') + (' ' if i < len(pals) - 1 else '')
            d.text((x, y), pal, font=f, fill=acento if dentro else color)
            x += d.textlength(pal, font=f)
            if fin: dentro = False
        y += size * lh
    return im


def pill(text, size, bg=PINK, fg=INK, padx=26, pady=14, fuente='lg-black.woff2'):
    return G.pill(text, size, bg=bg, fg=fg, padx=padx, pady=pady, fuente=fuente)


def avion(color, s=60):
    """Ícono de 'enviar' (avión de papel)."""
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(2, s * .45), (s - 2, 2), (s * .55, s - 2), (s * .42, s * .58)], fill=color)
    d.polygon([(s * .42, s * .58), (s - 2, 2), (s * .5, s * .62)], fill=(0, 0, 0, 90))
    return im


def boton(icono, texto_, size=44, bg=WHITE, fg=INK, w=None):
    f = font('lg-black.woff2', size); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    tw = int(d0.textlength(texto_, font=f)); ic = icono.resize((size + 14, size + 14))
    ancho = w or tw + ic.width + 110; alto = size + 70
    im = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, ancho - 1, alto - 1), 30, fill=bg)
    x0 = (ancho - tw - ic.width - 24) // 2
    im.alpha_composite(ic, (x0, (alto - ic.height) // 2))
    d.text((x0 + ic.width + 24, alto // 2), texto_, font=f, fill=fg, anchor='lm')
    return im


def polaroid(ref, w, h, ang=0, pie=None):
    foto = cubrir(ref, w, h)
    extra = 90 if pie else 24
    m = Image.new('RGBA', (w + 48, h + 24 + extra), WHITE)
    m.paste(foto, (24, 24))
    if pie:
        ImageDraw.Draw(m).text((m.width // 2, h + 24 + extra // 2 + 4), pie, font=font('serif-italic.woff2', 40), fill=INK, anchor='mm')
    s = Image.new('RGBA', (m.width + 60, m.height + 60), (0, 0, 0, 0))
    sm = Image.new('L', s.size, 0); ImageDraw.Draw(sm).rectangle((30, 42, 30 + m.width, 42 + m.height), fill=80)
    s.putalpha(sm.filter(ImageFilter.GaussianBlur(16))); s.alpha_composite(m, (30, 30))
    return s.rotate(ang, resample=Image.BICUBIC, expand=True)


class Esc:
    def __init__(self, dur, fondo, piezas, encabezado=None):
        self.dur, self.fondo, self.piezas, self.encabezado = dur, fondo, piezas, encabezado


def render(escenas, out, voces):
    tmp = out + '.video.mp4'
    pr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for e in escenas:
        n = int(e.dur * FPS)
        for i in range(n):
            t = i / FPS
            im = e.fondo(t).convert('RGBA')
            sale = cl((t - (e.dur - 0.3)) / 0.3)
            for capa, x, y, te, ef in e.piezas:
                p = (t - te) / 0.5
                if ef == 'rebote': pinta(im, capa, x, y, cl(p * 2) * (1 - sale), 0, 0.6 + 0.4 * back(p))
                elif ef == 'izq': pinta(im, capa, x - (1 - eo(p)) * 160, y, cl(p * 1.6) * (1 - sale))
                elif ef == 'fijo': pinta(im, capa, x, y, 1.0)
                elif ef == 'desliza':   # lámina de carrusel que entra desde la derecha
                    pinta(im, capa, x + (1 - eo(p * 0.8)) * W, y, 1.0)
                else: pinta(im, capa, x, y, eo(p) * (1 - sale), (1 - eo(p)) * 50 - sale * 30)
            if e.encabezado: im.alpha_composite(e.encabezado(t), (0, 0))
            b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=90); pr.stdin.write(b.getvalue())
    pr.stdin.close(); pr.wait()
    total = sum(e.dur for e in escenas)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp, '-stream_loop', '-1', '-i', G.MUSIC]
    voces = [v for v in voces if v[0] and os.path.exists(v[0])]
    for mp3, _ in voces: cmd += ['-i', mp3]
    f = [f'[1:a]volume={0.11 if voces else 0.55},afade=t=in:d=0.6,afade=t=out:st={total - 1.5:.2f}:d=1.5,atrim=0:{total:.2f}[m]']
    mez = '[m]'
    for k, (_, ini) in enumerate(voces):
        ms = int(ini * 1000)
        f.append(f'[{k + 2}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={ms}|{ms}[v{k}]'); mez += f'[v{k}]'
    f.append(f'{mez}amix=inputs={1 + len(voces)}:duration=first:normalize=0,alimiter=limit=0.95[a]')
    subprocess.run(cmd + ['-filter_complex', ';'.join(f), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                          '-t', f'{total:.2f}', '-movflags', '+faststart', out], check=True)
    os.remove(tmp)


# ---------- PLAYBOOK (Cópiale a...) ----------
def pb_fondo(foto, dur, alto=1150):
    base = Image.new('RGB', (W, H), NEGRO)
    img = cubrir(foto, W, alto) if foto else None
    grad = degradado(W, alto, alto * 0.45, alto, a1=255)
    top = degradado(W, 260, 0, 260, a0=150, a1=0)

    def f(t):
        im = base.copy().convert('RGBA')
        if img:
            im.paste(zoom(img, t, dur), (0, 0)); im.alpha_composite(grad, (0, 0)); im.alpha_composite(top, (0, 0))
        return im
    return f


def pb_encabezado(serie, paso, pasos):
    im = Image.new('RGBA', (W, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    p = pill(serie, 30); im.alpha_composite(p, (M, 90))
    d.text((M + p.width + 22, 90 + p.height // 2), 'GUÍAS LGI', font=font('lg-black.woff2', 30), fill=WHITE, anchor='lm')
    if pasos:
        for i in range(pasos):
            cx = W - M - (pasos - 1 - i) * 44 - 12
            d.ellipse((cx - 12, 90 + p.height // 2 - 12, cx + 12, 90 + p.height // 2 + 12), fill=PINK if i < paso else (90, 90, 90))
    return lambda t: im


def tarjeta_ejemplo(texto_, foto, w, etiqueta='ASÍ LO HARÍA UN NEGOCIO EN MÉXICO'):
    th = 250
    t = txt(texto_, 42, w - th - 110, 'lg-medium.woff2', INK, lh=1.25, max_lines=6, min_size=30)
    alto = max(th + 60, t.height + 120)
    im = Image.new('RGBA', (w, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, alto - 1), 30, fill=WHITE)
    x = 34
    if foto:
        f = cubrir(foto, th, alto - 60); mk = Image.new('L', f.size, 0)
        ImageDraw.Draw(mk).rounded_rectangle((0, 0, f.width - 1, f.height - 1), 20, fill=255)
        im.paste(f, (30, 30), mk); x = th + 64
    d.text((x, 34), etiqueta, font=font('lg-black.woff2', 24), fill=PINK)
    im.alpha_composite(t, (x, 80))
    return im.rotate(-1.5, resample=Image.BICUBIC, expand=True)


def pb_portada(e, dur, serie):
    tt = txt(e['titulo'], 112, W - 2 * M, max_lines=4, min_size=70)
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', GRIS, lh=1.25)
    y = 1170
    return Esc(dur, pb_fondo(e.get('foto'), dur, 1300), [(tt, M, y, 0.2, 'izq'), (sb, M, y + tt.height + 20, 0.7, 'sube')],
               pb_encabezado(serie, 0, 0))


def pb_paso(e, n, pasos, dur, serie):
    num = txt(f'{n:02d}', 300, 700, 'lg-black.woff2', PINK, max_lines=1)
    tt = txt(e['titulo'], 92, W - 2 * M, max_lines=3, min_size=60)
    cu = txt(e.get('cuerpo', ''), 44, W - 2 * M, 'lg-regular.woff2', GRIS, lh=1.3, max_lines=4, min_size=32)
    cj = tarjeta_ejemplo(e.get('ejemplo', ''), e.get('ejemplo_foto'), W - 2 * M + 20)
    y = 820
    pz = [(num, M - 14, y, 0.0, 'rebote'), (tt, M, y + 290, 0.3, 'izq'), (cu, M, y + 310 + tt.height, 0.7, 'sube')]
    pz.append((cj, M - 20, min(H - cj.height - 70, y + 340 + tt.height + cu.height), 1.3, 'sube'))
    return Esc(dur, pb_fondo(e.get('foto'), dur, 1000), pz, pb_encabezado(serie, n, pasos))


def pb_cierre(e, dur, serie, pasos):
    tt = txt(e['titulo'], 104, W - 2 * M, max_lines=5, min_size=64)
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', GRIS, lh=1.3)
    b1 = boton(avion(INK), 'MÁNDASELO', 46, PINK, INK, W - 2 * M)
    b2 = boton(G.marcador(WHITE), 'GUÁRDALO', 46, (40, 40, 40), WHITE, W - 2 * M)
    ys = G.centrar([tt, sb, b1, b2], gap=46, y_min=300, y_max=1700)
    return Esc(dur, pb_fondo(e.get('foto'), dur, 900) if e.get('foto') else (lambda t: Image.new('RGB', (W, H), NEGRO)),
               [(tt, M, ys[0], 0.1, 'izq'), (sb, M, ys[1], 0.6, 'sube'), (b1, M, ys[2], 1.0, 'rebote'), (b2, M, ys[3], 1.3, 'rebote')],
               pb_encabezado(serie, pasos, pasos))


# ---------- TOP (resumen de la semana, cuenta regresiva) ----------
def top_encabezado(rotulo):
    im = Image.new('RGBA', (W, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((0, 70, W, 150), fill=PINK)
    f = font('lg-black.woff2', 34)
    txt_ = f'{rotulo}   /   '
    tw = d.textlength(txt_, font=f)
    tira = Image.new('RGBA', (int(tw * 4), 80), (0, 0, 0, 0)); dt = ImageDraw.Draw(tira)
    for k in range(4): dt.text((k * tw, 40), txt_, font=f, fill=INK, anchor='lm')

    def fx(t):
        c = im.copy(); c.alpha_composite(tira, (int(-(t * 90) % tw), 70)); return c
    return fx


def top_fondo(foto, dur):
    img = cubrir(foto, W, H, 0.4)
    grad = degradado(W, H, 900, 1500, color=(0, 0, 0), a1=245)
    return lambda t: (lambda b: (b.alpha_composite(grad), b)[1])(zoom(img, t, dur, 1.02, 1.12).convert('RGBA'))


def top_portada(e, dur, rotulo):
    fotos = [f for f in (e.get('fotos') or []) if ruta(f)][:3]
    tiras = [cubrir(f, W // len(fotos) + 1, H) for f in fotos]

    def fondo(t):
        im = Image.new('RGBA', (W, H), NEGRO)
        for k, s in enumerate(tiras):
            im.paste(zoom(s, t + k, dur + 3, 1.0, 1.1), (k * (W // len(tiras)), 0))
        im.alpha_composite(degradado(W, H, 700, 1300, (0, 0, 0), 60, 230))
        return im
    bloque = Image.new('RGBA', (W - 2 * M, 10), (0, 0, 0, 0))
    tt = txt(e['titulo'], 120, W - 2 * M - 60, 'lg-black.woff2', INK, acento=WHITE, max_lines=4, min_size=70)
    caja = Image.new('RGBA', (W - 2 * M, tt.height + 80), PINK); caja.alpha_composite(tt, (30, 40))
    sb = txt(e.get('sub', ''), 48, W - 2 * M, 'lg-bold.woff2', WHITE)
    y = 1050
    return Esc(dur, fondo, [(caja, M, y, 0.2, 'rebote'), (sb, M, y + caja.height + 30, 0.7, 'sube')], top_encabezado(rotulo))


def top_item(e, n, dur, rotulo):
    num = txt(str(n), 560, 500, 'lg-black.woff2', PINK, max_lines=1)
    m = pill(e.get('marca', '').upper(), 34, bg=WHITE, fg=INK)
    tt = txt(e['titulo'], 96, W - 2 * M, max_lines=3, min_size=60)
    cu = txt(e.get('cuerpo', ''), 46, W - 2 * M, 'lg-regular.woff2', '#E6E6E6', lh=1.3, max_lines=4)
    y_cu = H - 150 - cu.height; y_tt = y_cu - 20 - tt.height; y_m = y_tt - 30 - m.height; y_n = y_m - 560
    return Esc(dur, top_fondo(e['foto'], dur), [(num, M - 30, y_n, 0.0, 'rebote'), (m, M, y_m, 0.35, 'izq'),
                                                 (tt, M, y_tt, 0.55, 'izq'), (cu, M, y_cu, 0.95, 'sube')], top_encabezado(rotulo))


def top_cierre(e, dur, rotulo):
    tt = txt(e['titulo'], 130, W - 2 * M, 'lg-black.woff2', INK, acento=WHITE, max_lines=3)
    circ = Image.new('RGBA', (W - 2 * M, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(circ)
    for k in range(3):
        cx = 130 + k * ((W - 2 * M - 260) // 2)
        d.ellipse((cx - 120, 10, cx + 120, 250), fill=INK)
        d.text((cx, 130), str(k + 1), font=font('lg-black.woff2', 150), fill=PINK, anchor='mm')
    sb = txt(e.get('sub', ''), 52, W - 2 * M, 'lg-bold.woff2', INK, lh=1.25)
    b = boton(G.marcador(PINK), 'SÍGUENOS · @lgi.newsbrand', 40, INK, WHITE, W - 2 * M)
    ys = G.centrar([tt, circ, sb, b], gap=60, y_min=260)
    return Esc(dur, lambda t: Image.new('RGB', (W, H), PINK),
               [(tt, M, ys[0], 0.1, 'izq'), (circ, M, ys[1], 0.6, 'rebote'), (sb, M, ys[2], 1.0, 'sube'), (b, M, ys[3], 1.4, 'rebote')])


# ---------- CALENDARIO (carrusel 4:5 y video) ----------
CW, CH = 1080, 1350
DIAS = ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM']


def papel(w, h):
    im = Image.new('RGBA', (w, h), PAPEL); d = ImageDraw.Draw(im)
    for x in range(0, w, 54): d.line((x, 0, x, h), fill=LINEA)
    for y in range(0, h, 54): d.line((0, y, w, y), fill=LINEA)
    return im


def hoja(dia, mes, semana, w=330, h=390, ang=-4):
    """Hoja de calendario arrancable con aros."""
    im = Image.new('RGBA', (w + 40, h + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 34, 20 + w, 34 + h), 26, fill=WHITE)
    d.rounded_rectangle((20, 34, 20 + w, 34 + 100), 26, fill=PINK); d.rectangle((20, 100, 20 + w, 134), fill=PINK)
    d.text((20 + w // 2, 84), mes, font=font('lg-black.woff2', 40), fill=INK, anchor='mm')
    fs = 190 if len(dia) <= 2 else (128 if len(dia) <= 5 else 104)
    d.text((20 + w // 2, 134 + (h - 134) * 0.47), dia, font=font('serif.woff2', fs), fill=INK, anchor='mm')
    d.text((20 + w // 2, 34 + h - 46), semana, font=font('lg-black.woff2', 30), fill=PINK, anchor='mm')
    for x in (20 + w * 0.28, 20 + w * 0.72):
        d.rounded_rectangle((x - 12, 6, x + 12, 66), 12, fill=INK)
    s = Image.new('RGBA', (im.width + 50, im.height + 50), (0, 0, 0, 0))
    sm = Image.new('L', s.size, 0); ImageDraw.Draw(sm).rounded_rectangle((25, 70, 25 + w + 40, 70 + h), 26, fill=70)
    s.putalpha(sm.filter(ImageFilter.GaussianBlur(14))); s.alpha_composite(im, (25, 25))
    return s.rotate(ang, resample=Image.BICUBIC, expand=True)


def sello(lam, n, total):
    d = ImageDraw.Draw(lam)
    p = G.pill('GUÍAS LGI', 26); lam.alpha_composite(p, (60, 56))
    g = G.pill('GUÁRDALO', 26, bg=PINK, fg=INK, padx=60); lam.alpha_composite(g, (CW - 60 - g.width, 56))
    lam.alpha_composite(G.marcador(INK).resize((24, 31)), (CW - 60 - g.width + 22, 56 + (g.height - 31) // 2))
    if total:
        d.text((CW // 2, CH - 50), f'{n} / {total}', font=font('lg-bold.woff2', 28), fill=(120, 110, 100), anchor='mm')


def lam_portada(e, total):
    lam = papel(CW, CH); sello(lam, 1, total)
    fotos = [f for f in (e.get('fotos') or []) if ruta(f)][:3]
    for k, f in enumerate(fotos):
        p = polaroid(f, 290, 300, [-7, 5, -3][k])
        lam.alpha_composite(p, ([20, 345, 670][k], [160, 215, 150][k]))
    h = hoja(e.get('dia', 'NOV'), e.get('mes', '2026'), e.get('semana', ''), 260, 300, 6)
    tt = G.texto(e['titulo'], 104, CW - 120, max_lines=4, min_size=60)
    lam.alpha_composite(tt, (60, 680))
    sb = G.texto(e.get('sub', ''), 40, CW - 120, 'lg-medium.woff2', lh=1.3)
    lam.alpha_composite(sb, (60, 700 + tt.height))
    dz = G.pill('DESLIZA  →', 30, bg=INK, fg=PAPEL, padx=36); lam.alpha_composite(dz, (CW - 60 - dz.width, CH - 130))
    return lam


def lam_fecha(e, n, total):
    lam = papel(CW, CH); sello(lam, n, total)
    f = ruta(e.get('foto'))
    if f:
        p = polaroid(f, 620, 480, 3); lam.alpha_composite(p, (CW - p.width - 20, 140))
    h = hoja(e['dia'], e.get('mes', 'NOV'), e.get('semana', ''), 330, 400, -5)
    lam.alpha_composite(h, (30, 200))
    tt = G.texto(e['titulo'], 82, CW - 120, max_lines=2, min_size=56)
    y = 750; lam.alpha_composite(tt, (60, y)); y += tt.height + 4
    if e.get('nota'):
        nt = G.texto(e['nota'], 36, CW - 120, 'lg-medium.woff2', lh=1.25, max_lines=2); lam.alpha_composite(nt, (60, y)); y += nt.height + 10
    cj = G.caja('IDEA PARA TU MARCA', e.get('idea', ''), CW - 120)
    lam.alpha_composite(cj, (60, y + 14))
    return lam


def lam_mes(e, n, total):
    """Mini calendario del mes con las fechas marcadas: la lámina que más se guarda."""
    lam = papel(CW, CH); sello(lam, n, total)
    tt = G.texto(e['titulo'], 84, CW - 120, max_lines=2); lam.alpha_composite(tt, (60, 150))
    d = ImageDraw.Draw(lam)
    x0, y0, cw, chh = 60, 170 + tt.height + 30, (CW - 120) / 7, 104
    for k, s in enumerate(DIAS):
        d.text((x0 + cw * k + cw / 2, y0), s, font=font('lg-black.woff2', 28), fill=INK, anchor='mm')
    marcados = {int(k): v for k, v in (e.get('marcados') or {}).items()}
    col0, dias_mes = e.get('inicio', 6), e.get('dias', 30)
    for dnum in range(1, dias_mes + 1):
        i = col0 + dnum - 1; r_, c = divmod(i, 7)
        cx, cy = x0 + cw * c + cw / 2, y0 + 70 + r_ * chh
        if dnum in marcados:
            d.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=PINK if marcados[dnum] != 'rango' else '#FFC2D4')
        d.text((cx, cy), str(dnum), font=font('serif.woff2', 50), fill=INK, anchor='mm')
    filas = (col0 + dias_mes - 1) // 7 + 1
    yl = y0 + 70 + filas * chh - 30
    for k, ln in enumerate(e.get('leyenda', [])):
        t_ = G.texto(ln, 34, CW - 120, 'lg-medium.woff2', lh=1.2, max_lines=1, min_size=26); lam.alpha_composite(t_, (60, yl + k * 50))
    return lam


def lam_cierre(e, n, total):
    lam = Image.new('RGBA', (CW, CH), INK); d = ImageDraw.Draw(lam)
    tt = txt(e['titulo'], 96, CW - 120, 'serif.woff2', PAPEL, acento=PINK, lh=1.1, max_lines=5)
    sb = txt(e.get('sub', ''), 42, CW - 120, 'lg-medium.woff2', '#CFC8BC', lh=1.3)
    b1 = boton(G.marcador(INK), 'GUÁRDALO', 44, PINK, INK, CW - 120)
    b2 = boton(avion(PAPEL), 'MÁNDASELO A QUIEN LLEVA TUS REDES', 34, (45, 45, 45), PAPEL, CW - 120)
    ys = G.centrar([tt, sb, b1, b2], gap=44, y_min=120, y_max=CH - 120)
    for c, y in zip([tt, sb, b1, b2], ys): lam.alpha_composite(c, (60, int(y)))
    d.text((CW // 2, CH - 60), '@lgi.newsbrand', font=font('lg-black.woff2', 30), fill=PINK, anchor='mm')
    return lam


def laminas(data):
    esc = data['escenas']; total = len(esc); out = []
    for k, e in enumerate(esc):
        t = e.get('tipo')
        if t == 'portada': out.append(lam_portada(e, total))
        elif t == 'fecha': out.append(lam_fecha(e, k + 1, total))
        elif t == 'mes': out.append(lam_mes(e, k + 1, total))
        else: out.append(lam_cierre(e, k + 1, total))
    return out


def carrusel(data, carpeta):
    os.makedirs(carpeta, exist_ok=True); rutas = []
    for k, lam in enumerate(laminas(data), 1):
        p = os.path.join(carpeta, f'{k:02d}.jpg'); lam.convert('RGB').save(p, quality=93); rutas.append(p)
    return rutas


def cal_escenas(data, durs):
    """Video: cada lámina entra deslizándose sobre papel vertical, con barra de avance arriba."""
    lams = laminas(data); n = len(lams); esc = []
    fondo0 = papel(W, H).convert('RGB')
    y = (H - CH) // 2 + 40
    for k, lam in enumerate(lams):
        prev = lams[k - 1] if k else None

        def fondo(t, prev=prev):
            im = fondo0.copy().convert('RGBA')
            if prev is not None:
                im.alpha_composite(prev, (int(-eo(t / 0.4) * W), y))
            return im

        def enc(t, k=k):
            im = Image.new('RGBA', (W, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            ancho = (W - 2 * M - (n - 1) * 10) / n
            for i in range(n):
                x = M + i * (ancho + 10)
                d.rounded_rectangle((x, 150, x + ancho, 160), 5, fill=INK if i <= k else LINEA)
            return im
        esc.append(Esc(durs[k], fondo, [(lam, 0, y, 0.0, 'desliza')], enc))
    return esc


# ---------- armado ----------
def make(data, out):
    import voz, reel
    tmp = tempfile.mkdtemp()
    try:
        pron = dict(reel.PRON_FIJA); pron.update({k: v for k, v in (data.get('pronunciar') or {}).items() if k and v})
        esc = data['escenas']; estilo = data['estilo']
        mp3s, durs = [], []
        for k, e in enumerate(esc):
            mp3, dv = None, 0.0
            if e.get('voz'):
                (pal, dv), mp3 = voz.sintetizar(reel.pronunciado(e['voz'], pron), os.path.join(tmp, f'v{k}.mp3'))
            mp3s.append(mp3); durs.append(max(3.0, dv + 0.9))
        serie = data.get('serie', 'GUÍA'); rot = data.get('rotulo', 'TOP 3 DE LA SEMANA')
        pasos = sum(1 for e in esc if e.get('tipo') in ('paso', 'item'))
        escenas, n = [], 0
        if estilo == 'calendario':
            escenas = cal_escenas(data, durs)
        else:
            orden = list(range(pasos, 0, -1)) if estilo == 'top' else list(range(1, pasos + 1))
            for k, e in enumerate(esc):
                t, d = e.get('tipo'), durs[k]
                if estilo == 'playbook':
                    if t == 'portada': sc = pb_portada(e, d, serie)
                    elif t == 'paso': n += 1; sc = pb_paso(e, n, pasos, d, serie)
                    else: sc = pb_cierre(e, d, serie, pasos)
                else:
                    if t == 'portada': sc = top_portada(e, d, rot)
                    elif t == 'item': sc = top_item(e, orden[n], d, rot); n += 1
                    else: sc = top_cierre(e, d, rot)
                escenas.append(sc)
        voces, t0 = [], 0.0
        for sc, mp3 in zip(escenas, mp3s):
            voces.append((mp3, t0 + 0.25)); t0 += sc.dur
        render(escenas, out, voces)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
