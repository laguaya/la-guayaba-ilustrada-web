"""Estilos de Guías LGI. Cada tipo de guía tiene su propio diseño:
- "playbook" (Cópiale a...): foto a sangre arriba, fondo negro, número gigante rosa, tarjeta blanca de ejemplo con foto.
- "top" (resumen de la semana): cuenta regresiva 3-2-1, foto completa con zoom lento, número enorme y franja superior.
- "calendario" (fechas del mes en México): papel crema, hojas de calendario arrancables, polaroids. Sale en carrusel
  (1080x1350) y en video (las mismas láminas dentro del vertical, pasando como si se deslizaran).
Se elige con data["estilo"]. Las fotos van en assets/libres/<tema>/ (scripts/fotos_libres.py) o assets/work/.
"""
import os, io, math, subprocess, tempfile, shutil, sys, json
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


def pill_icono(icono, texto_, size, bg=PINK, fg=INK, padx=34, alto=None, gap=14):
    """Píldora con ícono + texto centrados de verdad (usa la caja real de las letras, no las métricas)."""
    f = font('lg-black.woff2', size); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    x0, y0, x1, y1 = d0.textbbox((0, 0), texto_, font=f)
    ic = icono.resize((int(size * 0.9), int(size * 0.9 * icono.height / icono.width)))
    alto = alto or int(size * 2.1)
    ancho = padx * 2 + ic.width + gap + (x1 - x0)
    im = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, ancho - 1, alto - 1), alto // 2, fill=bg)
    im.alpha_composite(ic, (padx, (alto - ic.height) // 2))
    d.text((padx + ic.width + gap - x0, (alto - (y1 - y0)) // 2 - y0), texto_, font=f, fill=fg)
    return im


def boton(icono, texto_, size=44, bg=WHITE, fg=INK, w=None):
    f = font('lg-black.woff2', size); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    bx0, by0, bx1, by1 = d0.textbbox((0, 0), texto_, font=f); tw = bx1 - bx0
    ic = icono.resize((size, int(size * icono.height / icono.width)))
    ancho = w or tw + ic.width + 110; alto = size + 70
    im = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, ancho - 1, alto - 1), 30, fill=bg)
    x0 = (ancho - tw - ic.width - 24) // 2
    im.alpha_composite(ic, (x0, (alto - ic.height) // 2))
    d.text((x0 + ic.width + 24 - bx0, (alto - (by1 - by0)) // 2 - by0), texto_, font=f, fill=fg)
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
    def __init__(self, dur, fondo, piezas, encabezado=None, sub_y=1700, salida=True):
        self.dur, self.fondo, self.piezas, self.encabezado = dur, fondo, piezas, encabezado
        self.sub_y, self.salida, self.subs = sub_y, salida, []


_TMPS = []


def cuadros(video, w, h, dur, desde=0.0):
    """Saca los cuadros de un video (recortado a w x h, en bucle si es corto) a una carpeta temporal."""
    d = tempfile.mkdtemp(); _TMPS.append(d)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-stream_loop', '-1', '-ss', str(desde), '-i', video, '-t', f'{dur + 0.5:.2f}',
                    '-vf', f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS}', '-q:v', '3',
                    os.path.join(d, '%05d.jpg')], check=True)
    fs = sorted(os.listdir(d))
    return [os.path.join(d, f) for f in fs]


def subtitulo_en(im, e, t):
    if not e.subs: return
    import reel
    tv = t - 0.25
    for k, g in enumerate(e.subs):
        fin = e.subs[k + 1][0][0] if k + 1 < len(e.subs) else g[-1][1] + 0.6
        if g[0][0] - 0.05 <= tv < fin:
            c = reel.subtitulo(g, tv)
            im.alpha_composite(c, (int((W - c.width) / 2), int(e.sub_y)))
            return


def render(escenas, out, voces):
    tmp = out + '.video.mp4'
    pr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for e in escenas:
        n = int(e.dur * FPS)
        for i in range(n):
            t = i / FPS
            im = e.fondo(t).convert('RGBA')
            sale = cl((t - (e.dur - 0.3)) / 0.3) if e.salida else 0.0
            for capa, x, y, te, ef in e.piezas:
                p = (t - te) / 0.5
                if callable(capa): capa = capa(t)
                if ef == 'rebote': pinta(im, capa, x, y, cl(p * 2) * (1 - sale), 0, 0.6 + 0.4 * back(p))
                elif ef == 'izq': pinta(im, capa, x - (1 - eo(p)) * 160, y, cl(p * 1.6) * (1 - sale))
                elif ef == 'fijo': pinta(im, capa, x, y, 1.0)
                elif ef == 'flota': pinta(im, capa, x, y, cl(p * 2) * (1 - sale), (1 - eo(p)) * 70 + math.sin(t * 1.4 + x) * 7)
                elif ef == 'desliza':   # lámina de carrusel que entra desde la derecha
                    pinta(im, capa, x + (1 - eo(p * 0.8)) * W, y, 1.0)
                else: pinta(im, capa, x, y, eo(p) * (1 - sale), (1 - eo(p)) * 50 - sale * 30)
            if e.encabezado: im.alpha_composite(e.encabezado(t), (0, 0))
            subtitulo_en(im, e, t)
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
def pb_fondo(foto, dur, alto=1150, video=None, desde=0.0):
    base = Image.new('RGB', (W, H), NEGRO)
    cs = cuadros(video, W, alto, dur, desde) if video else None
    img = cubrir(foto, W, alto) if (foto and not cs) else None
    grad = degradado(W, alto, alto * 0.40, alto * 0.86, a1=255)
    top = degradado(W, 260, 0, 260, a0=150, a1=0)

    def f(t):
        im = base.copy().convert('RGBA')
        if cs:
            im.paste(Image.open(cs[min(len(cs) - 1, int(t * FPS))]).convert('RGB'), (0, 0))
        elif img:
            im.paste(zoom(img, t, dur), (0, 0))
        if cs or img:
            im.alpha_composite(grad, (0, 0)); im.alpha_composite(top, (0, 0))
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
    th, pad = 250, 30
    x = pad + th + 34 if foto else 40
    t = txt(texto_, 42, w - x - 40, 'lg-medium.woff2', INK, lh=1.25, max_lines=6, min_size=30)
    fl = font('lg-black.woff2', 24); lx0, ly0, lx1, ly1 = ImageDraw.Draw(Image.new('RGB', (4, 4))).textbbox((0, 0), etiqueta, font=fl)
    bloque = (ly1 - ly0) + 18 + t.height - int(42 * 0.3)      # etiqueta + espacio + texto (sin el aire de abajo)
    alto = max(th + 2 * pad, bloque + 2 * 44)
    im = Image.new('RGBA', (w, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, alto - 1), 30, fill=WHITE)
    if foto:
        f = cubrir(foto, th, alto - 2 * pad); mk = Image.new('L', f.size, 0)
        ImageDraw.Draw(mk).rounded_rectangle((0, 0, f.width - 1, f.height - 1), 20, fill=255)
        im.paste(f, (pad, pad), mk)
    y0 = (alto - bloque) // 2
    d.text((x - lx0, y0 - ly0), etiqueta, font=fl, fill=PINK)
    im.alpha_composite(t, (x, y0 + (ly1 - ly0) + 18 - int(42 * 0.08)))
    return im


def pb_portada(e, dur, serie):
    tt = txt(e['titulo'], 112, W - 2 * M, max_lines=4, min_size=70)
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', GRIS, lh=1.25)
    y = 1170
    return Esc(dur, pb_fondo(e.get('foto'), dur, 1300, e.get('_video'), e.get('desde', 0)),
               [(tt, M, y, 0.2, 'izq'), (sb, M, y + tt.height + 20, 0.7, 'sube')], pb_encabezado(serie, 0, 0), sub_y=880)


def pb_paso(e, n, pasos, dur, serie):
    num = txt(f'{n:02d}', 300, 700, 'lg-black.woff2', PINK, max_lines=1)
    tt = txt(e['titulo'], 92, W - 2 * M, max_lines=3, min_size=60)
    cu = txt(e.get('cuerpo', ''), 44, W - 2 * M, 'lg-regular.woff2', GRIS, lh=1.3, max_lines=4, min_size=32)
    cj = tarjeta_ejemplo(e.get('ejemplo', ''), e.get('ejemplo_foto'), W - 2 * M)
    y = 820
    pz = [(num, M - 14, y, 0.0, 'rebote'), (tt, M, y + 290, 0.3, 'izq'), (cu, M, y + 310 + tt.height, 0.7, 'sube')]
    pz.append((cj, M, min(H - cj.height - 70, y + 340 + tt.height + cu.height), 1.3, 'sube'))
    return Esc(dur, pb_fondo(e.get('foto'), dur, 1000, e.get('_video'), e.get('desde', 0)), pz, pb_encabezado(serie, n, pasos), sub_y=600)


def pb_cierre(e, dur, serie, pasos):
    tt = txt(e['titulo'], 104, W - 2 * M, max_lines=5, min_size=64)
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', GRIS, lh=1.3)
    b1 = boton(avion(INK), 'MÁNDASELO', 46, PINK, INK, W - 2 * M)
    b2 = boton(G.marcador(WHITE), 'GUÁRDALO', 46, (40, 40, 40), WHITE, W - 2 * M)
    ys = G.centrar([tt, sb, b1, b2], gap=46, y_min=300, y_max=1700)
    return Esc(dur, pb_fondo(e.get('foto'), dur, 900, e.get('_video'), e.get('desde', 0)) if (e.get('foto') or e.get('_video')) else (lambda t: Image.new('RGB', (W, H), NEGRO)),
               [(tt, M, ys[0], 0.1, 'izq'), (sb, M, ys[1], 0.6, 'sube'), (b1, M, ys[2], 1.0, 'rebote'), (b2, M, ys[3], 1.3, 'rebote')],
               pb_encabezado(serie, pasos, pasos), sub_y=1730)


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


def top_fondo(foto, dur, video=None, desde=0.0):
    cs = cuadros(video, W, H, dur, desde) if video else None
    img = cubrir(foto, W, H, 0.4) if not cs else None
    grad = degradado(W, H, 900, 1500, color=(0, 0, 0), a1=245)

    def f(t):
        b = (Image.open(cs[min(len(cs) - 1, int(t * FPS))]) if cs else zoom(img, t, dur, 1.02, 1.12)).convert('RGBA')
        b.alpha_composite(grad); return b
    return f


def top_portada(e, dur, rotulo):
    fotos = [f for f in (e.get('fotos') or []) if ruta(f)][:3]
    vids = e.get('_videos') or []
    nt = max(len(fotos), len(vids)) or 1; tw = W // nt + 1
    tiras = []
    for k in range(nt):
        v = vids[k] if k < len(vids) else None
        tiras.append(('v', cuadros(v, tw, H, dur, (e.get('desdes') or [0] * 3)[k])) if v else ('f', cubrir(fotos[k], tw, H)))

    def fondo(t):
        im = Image.new('RGBA', (W, H), NEGRO)
        for k, (tipo, s) in enumerate(tiras):
            fr = Image.open(s[min(len(s) - 1, int(t * FPS))]).convert('RGB') if tipo == 'v' else zoom(s, t + k, dur + 3, 1.0, 1.1)
            im.paste(fr, (k * (W // nt), 0))
        im.alpha_composite(degradado(W, H, 700, 1300, (0, 0, 0), 60, 230))
        return im
    bloque = Image.new('RGBA', (W - 2 * M, 10), (0, 0, 0, 0))
    tt = txt(e['titulo'], 120, W - 2 * M - 60, 'lg-black.woff2', INK, acento=WHITE, max_lines=4, min_size=70)
    caja = Image.new('RGBA', (W - 2 * M, tt.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(caja).rounded_rectangle((0, 0, caja.width - 1, caja.height - 1), 44, fill=PINK); caja.alpha_composite(tt, (30, 40))
    sb = txt(e.get('sub', ''), 48, W - 2 * M, 'lg-bold.woff2', WHITE)
    y = 1050
    return Esc(dur, fondo, [(caja, M, y, 0.2, 'rebote'), (sb, M, y + caja.height + 30, 0.7, 'sube')], top_encabezado(rotulo), sub_y=840)


def top_item(e, n, dur, rotulo):
    num = txt(str(n), 560, 500, 'lg-black.woff2', PINK, max_lines=1)
    m = pill(e.get('marca', '').upper(), 34, bg=WHITE, fg=INK)
    tt = txt(e['titulo'], 96, W - 2 * M, max_lines=3, min_size=60)
    cu = txt(e.get('cuerpo', ''), 46, W - 2 * M, 'lg-regular.woff2', '#E6E6E6', lh=1.3, max_lines=4)
    y_cu = H - 150 - cu.height; y_tt = y_cu - 20 - tt.height; y_m = y_tt - 30 - m.height; y_n = y_m - 560
    return Esc(dur, top_fondo(e['foto'], dur, e.get('_video'), e.get('desde', 0)), [(num, M - 30, y_n, 0.0, 'rebote'), (m, M, y_m, 0.35, 'izq'),
                                                 (tt, M, y_tt, 0.55, 'izq'), (cu, M, y_cu, 0.95, 'sube')], top_encabezado(rotulo), sub_y=300)


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
               [(tt, M, ys[0], 0.1, 'izq'), (circ, M, ys[1], 0.6, 'rebote'), (sb, M, ys[2], 1.0, 'sube'), (b, M, ys[3], 1.4, 'rebote')], sub_y=1720)


# ---------- CALENDARIO (carrusel 4:5 y video animado) ----------
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


def polaroid_viva(ref, w, h, ang=0, dur=6.0, fase=0.0):
    """Polaroid cuya foto se mueve (acercamiento + paneo) y que se mece un poco. Devuelve f(t) -> capa."""
    big = cubrir(ref, int(w * 1.22), int(h * 1.22))
    marco = Image.new('RGBA', (w + 48, h + 48), WHITE)
    s0 = Image.new('RGBA', (marco.width + 60, marco.height + 60), (0, 0, 0, 0))
    sm = Image.new('L', s0.size, 0); ImageDraw.Draw(sm).rectangle((30, 42, 30 + marco.width, 42 + marco.height), fill=80)
    s0.putalpha(sm.filter(ImageFilter.GaussianBlur(16)))
    dx = (1 if int(fase * 10) % 2 else -1)

    def f(t):
        p = eo(cl(t / max(dur, 1)))
        z = 1.0 + 0.16 * p                                  # acerca
        cw, ch = big.width / (1.0 * z) / 1.0, big.height / z
        cw, ch = min(cw, big.width), min(ch, big.height)
        cx = (big.width - cw) / 2 + dx * (big.width - cw) / 2 * (p - 0.5)   # panea
        cy = (big.height - ch) / 2
        foto = big.crop((int(cx), int(cy), int(cx + cw), int(cy + ch))).resize((w, h), Image.BILINEAR)
        m = marco.copy(); m.paste(foto, (24, 24))
        c = s0.copy(); c.alpha_composite(m, (30, 30))
        return c.rotate(ang + math.sin(t * 1.1 + fase) * 1.4, resample=Image.BICUBIC, expand=True)
    return f


def _sello():
    lam = papel(CW, CH)
    p = G.pill('GUÍAS LGI', 26); lam.alpha_composite(p, (60, 56))
    g = pill_icono(G.marcador(INK), 'GUÁRDALO', 26, alto=p.height); lam.alpha_composite(g, (CW - 60 - g.width, 56))
    return lam


def _num(lam, n, total):
    if total:
        ImageDraw.Draw(lam).text((CW // 2, CH - 50), f'{n} / {total}', font=font('lg-bold.woff2', 28), fill=(120, 110, 100), anchor='mm')
    return lam


def pz_portada(e, total, dur):
    fondo = _num(_sello(), 1, total); pz = []
    fotos = [f for f in (e.get('fotos') or []) if ruta(f)][:3]
    for k, f in enumerate(fotos):
        pz.append((polaroid_viva(f, 290, 300, [-7, 5, -3][k], dur, k * 1.3), [20, 345, 670][k], [160, 215, 150][k], 0.5 + k * 0.2, 'flota'))
    tt = G.texto(e['titulo'], 104, CW - 120, max_lines=4, min_size=60)
    sb = G.texto(e.get('sub', ''), 40, CW - 120, 'lg-medium.woff2', lh=1.3)
    dz = G.pill('DESLIZA  →', 30, bg=INK, fg=PAPEL, padx=36)
    pz += [(tt, 60, 680, 1.1, 'sube'), (sb, 60, 700 + tt.height, 1.5, 'sube'), (dz, CW - 60 - dz.width, CH - 130, 1.9, 'rebote')]
    return fondo, pz


def pz_fecha(e, n, total, dur):
    fondo = _num(_sello(), n, total); pz = []
    if ruta(e.get('foto')):
        pv = polaroid_viva(e['foto'], 620, 480, 3, dur, n)
        pz.append((pv, CW - pv(0).width - 20, 140, 0.45, 'flota'))
    pz.append((hoja(e['dia'], e.get('mes', 'NOV'), e.get('semana', ''), 330, 400, -5), 30, 200, 0.75, 'rebote'))
    tt = G.texto(e['titulo'], 82, CW - 120, max_lines=2, min_size=56)
    y = 750; pz.append((tt, 60, y, 1.05, 'izq')); y += tt.height + 4
    if e.get('nota'):
        nt = G.texto(e['nota'], 36, CW - 120, 'lg-medium.woff2', lh=1.25, max_lines=2); pz.append((nt, 60, y, 1.3, 'sube')); y += nt.height + 10
    cj = G.caja('IDEA PARA TU MARCA', e.get('idea', ''), CW - 120)
    pz.append((cj, 60, y + 14, 1.5, 'sube'))
    return fondo, pz


def pz_mes(e, n, total, dur):
    fondo = _num(_sello(), n, total); pz = []
    tt = G.texto(e['titulo'], 84, CW - 120, max_lines=2); pz.append((tt, 60, 150, 0.45, 'izq'))
    x0, y0, cw, chh = 60, 170 + tt.height + 30, (CW - 120) / 7, 104
    rejilla = Image.new('RGBA', (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(rejilla)
    for k, s in enumerate(DIAS):
        d.text((x0 + cw * k + cw / 2, y0), s, font=font('lg-black.woff2', 28), fill=INK, anchor='mm')
    marcados = {int(k): v for k, v in (e.get('marcados') or {}).items()}
    col0, dias_mes = e.get('inicio', 6), e.get('dias', 30)
    circulos = []
    for dnum in range(1, dias_mes + 1):
        i = col0 + dnum - 1; r_, c = divmod(i, 7)
        cx, cy = x0 + cw * c + cw / 2, y0 + 70 + r_ * chh
        d.text((cx, cy), str(dnum), font=font('serif.woff2', 50), fill=INK, anchor='mm')
        if dnum in marcados:
            ci = Image.new('RGBA', (96, 96), (0, 0, 0, 0)); dc = ImageDraw.Draw(ci)
            dc.ellipse((4, 4, 92, 92), fill=PINK if marcados[dnum] != 'rango' else '#FFC2D4')
            dc.text((48, 48), str(dnum), font=font('serif.woff2', 50), fill=INK, anchor='mm')
            circulos.append((ci, cx - 48, cy - 48))
    pz.append((rejilla, 0, 0, 0.7, 'sube'))
    for k, (ci, x, y) in enumerate(circulos): pz.append((ci, x, y, 1.1 + k * 0.18, 'rebote'))
    filas = (col0 + dias_mes - 1) // 7 + 1; yl = y0 + 70 + filas * chh - 30
    for k, ln in enumerate(e.get('leyenda', [])):
        t_ = G.texto(ln, 34, CW - 120, 'lg-medium.woff2', lh=1.2, max_lines=1, min_size=26)
        pz.append((t_, 60, yl + k * 50, 1.4 + k * 0.25, 'izq'))
    return fondo, pz


def pz_cierre(e, n, total, dur):
    fondo = Image.new('RGBA', (CW, CH), INK)
    ImageDraw.Draw(fondo).text((CW // 2, CH - 60), '@lgi.newsbrand', font=font('lg-black.woff2', 30), fill=PINK, anchor='mm')
    tt = txt(e['titulo'], 96, CW - 120, 'serif.woff2', PAPEL, acento=PINK, lh=1.1, max_lines=5)
    sb = txt(e.get('sub', ''), 42, CW - 120, 'lg-medium.woff2', '#CFC8BC', lh=1.3)
    b1 = boton(G.marcador(INK), 'GUÁRDALO', 44, PINK, INK, CW - 120)
    b2 = boton(avion(PAPEL), 'MÁNDASELO A QUIEN LLEVA TUS REDES', 34, (45, 45, 45), PAPEL, CW - 120)
    ys = G.centrar([tt, sb, b1, b2], gap=44, y_min=120, y_max=CH - 120)
    return fondo, [(tt, 60, ys[0], 0.45, 'izq'), (sb, 60, ys[1], 0.9, 'sube'), (b1, 60, ys[2], 1.3, 'rebote'), (b2, 60, ys[3], 1.6, 'rebote')]


def laminas_pz(data, durs=None):
    esc = data['escenas']; total = len(esc); out = []
    durs = durs or [6.0] * total
    for k, e in enumerate(esc):
        t = e.get('tipo')
        if t == 'portada': out.append(pz_portada(e, total, durs[k]))
        elif t == 'fecha': out.append(pz_fecha(e, k + 1, total, durs[k]))
        elif t == 'mes': out.append(pz_mes(e, k + 1, total, durs[k]))
        else: out.append(pz_cierre(e, k + 1, total, durs[k]))
    return out


def componer(fondo, pz, t=0.0):
    lam = fondo.copy()
    for capa, x, y, te, ef in pz:
        c = capa(t) if callable(capa) else capa
        lam.alpha_composite(c, (int(x), int(y)))
    return lam


def carrusel(data, carpeta):
    os.makedirs(carpeta, exist_ok=True); rutas = []
    for k, (fondo, pz) in enumerate(laminas_pz(data), 1):
        p = os.path.join(carpeta, f'{k:02d}.jpg'); componer(fondo, pz).convert('RGB').save(p, quality=93); rutas.append(p)
    return rutas


def cal_escenas(data, durs):
    """Video: la lámina entra deslizándose y luego cada elemento entra por su lado; las fotos se mueven todo el tiempo."""
    lams = laminas_pz(data, durs); n = len(lams); esc = []
    fondo0 = papel(W, H)
    y0 = 200
    for k, (fondo, pz) in enumerate(lams):
        prev = componer(*lams[k - 1], durs[k - 1]) if k else None

        def fondo_f(t, prev=prev, fondo=fondo):
            im = fondo0.copy()
            a = eo(cl(t / 0.45))
            if prev is not None: im.alpha_composite(prev, (int(-a * W), y0))
            im.alpha_composite(fondo, (int((1 - a) * W) if prev is not None else 0, y0))
            return im

        def enc(t, k=k):
            im = Image.new('RGBA', (W, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            ancho = (W - 2 * M - (n - 1) * 10) / n
            for i in range(n):
                x = M + i * (ancho + 10)
                d.rounded_rectangle((x, 120, x + ancho, 130), 5, fill=INK if i < k or (i == k and t > 0.3) else LINEA)
            return im
        piezas = [(c, x, y + y0, max(0.0, te - (0.45 if k == 0 else 0)), ef) for c, x, y, te, ef in pz]
        esc.append(Esc(durs[k], fondo_f, piezas, enc, sub_y=y0 + CH + 50, salida=False))
    return esc


# ---------- armado ----------
def _video(e, tmp, k):
    """Resuelve "video": ruta local (assets/libres_v/...), URL directa o de página/YouTube (se baja con reel.bajar_url)."""
    v = e.get('video')
    if not v: return None
    if isinstance(v, str) and ruta(v): return ruta(v)
    import reel, hashlib
    dest = os.path.join(tmp, 'v_' + hashlib.md5(json.dumps(v).encode()).hexdigest()[:10] + '.mp4')
    if os.path.exists(dest): return dest
    for u in (v if isinstance(v, list) else [v]):
        if reel.bajar_url(u, dest) and os.path.exists(dest) and os.path.getsize(dest) > 50000:
            return dest
    print('Guía: sin video para escena', k, v, file=sys.stderr)
    return None


def make(data, out):
    import voz, reel
    tmp = tempfile.mkdtemp()
    try:
        pron = dict(reel.PRON_FIJA); pron.update({k: v for k, v in (data.get('pronunciar') or {}).items() if k and v})
        esc = data['escenas']; estilo = data['estilo']
        mp3s, durs, pals = [], [], []
        for k, e in enumerate(esc):
            mp3, dv, pal = None, 0.0, []
            if e.get('voz'):
                (pal, dv), mp3 = voz.sintetizar(reel.pronunciado(e['voz'], pron), os.path.join(tmp, f'v{k}.mp3'))
            if pal: pal = reel.restaurar(pal, pron)          # subtítulos con la escritura real (Baileys, no Béilis)
            e['_video'] = _video(e, tmp, k)
            if e.get('videos'):
                e['_videos'] = [_video({'video': v}, tmp, f'{k}_{j}') for j, v in enumerate(e['videos'])]
            mp3s.append(mp3); durs.append(max(3.0, dv + 0.9)); pals.append(pal or [])
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
        if data.get('subtitulos', True):
            for sc, pal in zip(escenas, pals):
                sc.subs = reel.grupos(pal) if pal else []
        voces, t0 = [], 0.0
        for sc, mp3 in zip(escenas, mp3s):
            voces.append((mp3, t0 + 0.25)); t0 += sc.dur
        render(escenas, out, voces)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        while _TMPS: shutil.rmtree(_TMPS.pop(), ignore_errors=True)
