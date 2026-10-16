"""Carrusel de Instagram (1080x1350) para cada nota de La Guayaba Ilustrada.

Uso: python scripts/carrusel.py datos.json carpeta_salida
datos.json:
{
  "img": "ruta/a/la/foto",
  "etiqueta": "ÚLTIMA HORA" | "NOTICIAS" | ...,
  "portada": "Titular gancho con *palabras resaltadas*",
  "titulo": "Titular de la segunda lámina con _palabra en itálica_",
  "resumen": "Resumen corto con [palabras clave] en rosa.",
  "marca": "Nombre de la marca o tema (va en la pestaña)",
  "fecha": "14 OCTUBRE 2026"
}
Marcas de texto:  *texto* = marcatextos rosa   _texto_ = Linear Grotesk itálica   [texto] = rosa en negritas
Genera 1.jpg (portada), 2.jpg (la nota) y 3.jpg (cierre).
"""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageOps, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portada import font

W, H = 1080, 1350
PINK, INK, WHITE, WASH = '#FF3674', '#0B0B0B', '#FFFFFF', '#FFF2F6'
M = 64
TOTAL = 4
# Animación (la usa carrusel_video.py). None = imagen fija.
# A = {'t': segundos}. Cada lámina mueve UNA sola cosa: un golpe rápido, pausa y otra vez.
A = None
PERIODO, GOLPE, INICIO = 2.0, 0.45, 0.6


def golpe():
    """0 en reposo; sube y baja a 1 durante GOLPE segundos, cada PERIODO segundos."""
    if A is None or A['t'] < INICIO:
        return 0.0
    f = (A['t'] - INICIO) % PERIODO
    if f >= GOLPE:
        return 0.0
    import math
    return math.sin(math.pi * f / GOLPE)


def _foto(ruta, size, destino, zoom=1.0):
    """Foto recortada para que lo importante quede centrado en 'destino' (fracción del recuadro)."""
    import encuadre
    im = _abrir(ruta)
    return encuadre.recorte(im, size, encuadre.foco(ruta), zoom=zoom, destino=destino)


# ---------- texto enriquecido ----------
def tw(d, text, f, track=0.0):
    """Ancho del texto con espaciado entre letras (track en em, como en la web)."""
    if not track:
        return d.textlength(text, font=f)
    t = f.size * track
    return sum(d.textlength(c, font=f) + t for c in text) - t


def dt(d, xy, text, f, fill, track=0.0):
    if not track:
        d.text(xy, text, font=f, fill=fill); return
    x, y = xy
    t = f.size * track
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + t

def tokens(text):
    """Devuelve palabras; cada palabra es una lista de (texto, estilo) pegados sin espacio."""
    words, cur, style = [], [], 'n'
    for part in re.split(r'(\*|_|\[|\])', text):
        if part == '*': style = 'n' if style == 'hl' else 'hl'; continue
        if part == '_': style = 'n' if style == 'it' else 'it'; continue
        if part == '[': style = 'pk'; continue
        if part == ']': style = 'n'; continue
        pieces = part.split(' ')
        for k, w in enumerate(pieces):
            if k > 0 and cur:
                words.append(cur); cur = []
            if w:
                cur.append((w, style))
    if cur:
        words.append(cur)
    return words


def layout(d, text, fonts, maxw, track=0.0):
    """Líneas de segmentos (texto, estilo, ancho, espacio_antes)."""
    sp = d.textlength(' ', font=fonts['n'])
    lines, cur, cw = [], [], 0
    for word in tokens(text):
        segs = [(w, s, tw(d, w, fonts[s], track)) for w, s in word]
        ww = sum(x[2] for x in segs)
        if cur and cw + sp + ww > maxw:
            lines.append(cur); cur, cw = [], 0
        gap = sp if cur else 0
        for k, (w, s, x) in enumerate(segs):
            cur.append((w, s, x, gap if k == 0 else 0))
        cw += gap + ww
    if cur:
        lines.append(cur)
    return lines


def render(d, x, y, lines, fonts, lh, color, hl_bg=PINK, hl_fg=INK, pk=PINK, align='left', maxw=None, pad=10, it_color=None, track=0.0, hop_it=0.0):
    for ln in lines:
        lw = sum(w + g for _, _, w, g in ln)
        cx = x + ((maxw - lw) / 2 if align == 'center' and maxw else 0)
        i = 0
        size = fonts['n'].size
        while i < len(ln):
            w, s, ww, g = ln[i]
            if s == 'hl':
                j, run = i, 0
                while j < len(ln) and ln[j][1] == 'hl':
                    run += ln[j][2] + (ln[j][3] if j > i else 0); j += 1
                cx += g
                d.rectangle((cx - pad, y + size * 0.06, cx + run + pad, y + size * 1.06), fill=hl_bg)
                for k in range(i, j):
                    if k > i:
                        cx += ln[k][3]
                    dt(d, (cx, y), ln[k][0], fonts['hl'], hl_fg, track); cx += ln[k][2]
                i = j
                continue
            cx += g
            if s == 'it':
                dt(d, (cx, y + hop_it), w, fonts['it'], it_color or color, track)
            else:
                dt(d, (cx, y), w, fonts[s], pk if s == 'pk' else color, track)
            cx += ww; i += 1
        y += lh
    return y


def fitted(d, text, maxw, max_lines, base, big, small, step=2, it_scale=1.0, it_font='lg-italic.woff2', track=0.0):
    for size in range(big, small, -step):
        fonts = {'n': font(base, size), 'hl': font(base, size), 'pk': font(base, size),
                 'it': font(it_font, int(size * it_scale))}
        ls = layout(ImageDraw.Draw(Image.new('RGB', (4, 4))), text, fonts, maxw, track)
        if len(ls) <= max_lines:
            return fonts, ls, size
    return fonts, ls, size


# ---------- piezas ----------
def counter(d, n, dark=True):
    t = f'{n}/{TOTAL}'
    f = font('lg-medium.woff2', 26)
    w = d.textlength(t, font=f) + 36
    x1, y1 = W - M, M - 6
    d.rounded_rectangle((x1 - w, y1, x1, y1 + 46), radius=23, fill=(0, 0, 0) if dark else (255, 255, 255))
    d.text((x1 - w / 2, y1 + 24), t, font=f, fill=WHITE if dark else INK, anchor='mm')


def header(d, color, n, dark_counter=True):
    f = font('lg-bold.woff2', 22)
    d.text((M, M + 17), 'LA GUAYABA ILUSTRADA', font=f, fill=color, anchor='lm')
    counter(d, n, dark_counter)
    d.line((M, M + 64, W - M, M + 64), fill=color, width=2)


def slide1(data, out):
    can = _foto(data['img'], (W, H), (0.5, 0.36), zoom=1.0 + 0.045 * golpe())
    g = Image.new('L', (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.28) / (H * 0.45))
        g.putpixel((0, y), int(255 * min(1.0, t) ** 0.85 * 0.92))
    can.paste(Image.new('RGB', (W, H), INK), (0, 0), g.resize((W, H)))
    top = Image.linear_gradient('L').rotate(180).resize((W, 320)).point(lambda v: int(v * 0.7))
    can.paste(Image.new('RGB', (W, 320), INK), (0, 0), top)
    d = ImageDraw.Draw(can)
    header(d, WHITE, 1, dark_counter=True)

    maxw = W - 2 * M
    foot = H - M - 26
    fonts, ls, size = fitted(d, data['portada'], maxw, 4, 'lg-black.woff2', 104, 56)
    lh = size * 1.08
    y = foot - 74 - len(ls) * lh
    # etiqueta
    fe = font('lg-black.woff2', 30)
    et = data.get('etiqueta', 'NOTICIAS').upper()
    ew = d.textlength(et, font=fe) + 44
    d.rounded_rectangle((M, y - 84, M + ew, y - 30), radius=27, fill=PINK)
    d.text((M + ew / 2, y - 56), et, font=fe, fill=INK, anchor='mm')
    render(d, M, y, ls, fonts, lh, WHITE, hl_bg=PINK, hl_fg=INK, pad=12)
    d.line((M, foot - 34, W - M, foot - 34), fill=WHITE, width=2)
    fm = font('lg-bold.woff2', 24)
    d.text((M, foot), data.get('fecha', ''), font=fm, fill=WHITE, anchor='lm')
    d.text((W - M, foot), 'DESLIZA PARA SABER MÁS  →', font=fm, fill=WHITE, anchor='rm')
    can.save(out, 'JPEG', quality=92, optimize=True)


_CACHE = {}


def _abrir(ruta):
    if ruta not in _CACHE:
        _CACHE[ruta] = Image.open(ruta).convert('RGB')
    return _CACHE[ruta]


def _fondo(arriba):
    """Fondo rosa claro con luz arriba o abajo (se calcula una sola vez)."""
    key = ('fondo', arriba)
    if key not in _CACHE:
        can = Image.new('RGB', (W, H), WASH)
        glow = Image.new('L', (W, H), 0)
        box = (-200, -520, W + 200, 520) if arriba else (-200, H - 520, W + 200, H + 520)
        ImageDraw.Draw(glow).ellipse(box, fill=150)
        glow = glow.filter(ImageFilter.GaussianBlur(160))
        can.paste(Image.new('RGB', (W, H), '#FFC2D4'), (0, 0), glow)
        _CACHE[key] = can
    return _CACHE[key].copy()


def slide2(data, out):
    can = _fondo(True)
    d = ImageDraw.Draw(can)
    header(d, INK, 2, dark_counter=True)

    maxw = W - 2 * M
    TR = -0.035
    fonts, ls, size = fitted(d, data['titulo'], maxw, 3, 'lg-black.woff2', 80, 48, track=TR)
    y = M + 108
    y = render(d, M, y - 18 * golpe(), ls, fonts, size * 1.0, INK, hl_bg=PINK, hl_fg=INK, it_color=PINK, track=TR) + 18 * golpe()
    # resumen
    y += 38
    fr = {'n': font('lg-regular.woff2', 36), 'pk': font('lg-bold.woff2', 36),
          'hl': font('lg-regular.woff2', 36), 'it': font('lg-italic.woff2', 36)}
    rl = layout(d, data['resumen'], fr, maxw)[:5]
    y = render(d, M, y, rl, fr, 48, INK, pk=PINK)
    # foto con etiqueta de la marca (rectángulo recto, separado del pie)
    foot_h = 64
    ph_top = int(y + 40)
    ph_bottom = H - M - foot_h
    ph = _foto(data.get('img2') or data['img'], (W - 2 * M, ph_bottom - ph_top), (0.5, 0.5))
    can.paste(ph, (M, ph_top))
    ft = font('lg-black.woff2', 30)
    label = data.get('marca', '')
    if label:
        lw = tw(d, label.upper(), ft, 0.02) + 44
        d.rectangle((M, ph_bottom - 58, M + lw, ph_bottom), fill=PINK)
        dt(d, (M + 22, ph_bottom - 46), label.upper(), ft, INK, 0.02)
    d.line((M, H - M - 30, W - M, H - M - 30), fill=INK, width=2)
    fm = font('lg-medium.woff2', 22)
    d.text((M, H - M), 'la guayaba ilustrada', font=fm, fill=INK, anchor='ls')
    d.text((W - M, H - M), 'noticias de marketing, diseño y branding', font=fm, fill=INK, anchor='rs')
    can.save(out, 'JPEG', quality=92, optimize=True)


def info_de(data):
    """Texto de la lámina de información: lista de párrafos (campo 'info'; acepta también los viejos 'puntos')."""
    t = data.get('info') or data.get('puntos') or []
    if isinstance(t, str):
        t = [x for x in re.split(r'\n\s*\n|\n', t) if x.strip()]
    return [x.strip() for x in t if x and x.strip()][:4]


def slide_info(data, out, n):
    """Lámina de pura información en párrafos, con el mismo diseño de la lámina 2."""
    can = _fondo(False)
    d = ImageDraw.Draw(can)
    header(d, INK, n, dark_counter=True)
    maxw = W - 2 * M
    TR = -0.035
    fonts, ls, size = fitted(d, data.get('info_titulo') or 'Lo que tienes que _saber_', maxw, 2, 'lg-black.woff2', 84, 56, track=TR)
    y = M + 108
    y = render(d, M, y, ls, fonts, size * 1.0, INK, it_color=PINK, track=TR, hop_it=-20 * golpe()) + 36
    pars = info_de(data)
    disponible = H - M - 70 - y
    for fs in range(46, 26, -2):
        fr = {'n': font('lg-regular.woff2', fs), 'pk': font('lg-bold.woff2', fs),
              'hl': font('lg-regular.woff2', fs), 'it': font('lg-italic.woff2', fs)}
        bloques = [layout(d, t, fr, maxw) for t in pars]
        lh = fs * 1.38
        alto = sum(len(b) * lh for b in bloques) + (len(bloques) - 1) * fs * 0.9
        if alto <= disponible:
            break
    for b in bloques:
        y = render(d, M, y, b, fr, lh, INK, pk=PINK) + fs * 0.9
    d.line((M, H - M - 30, W - M, H - M - 30), fill=INK, width=2)
    fm = font('lg-medium.woff2', 22)
    d.text((M, H - M), 'la guayaba ilustrada', font=fm, fill=INK, anchor='ls')
    d.text((W - M, H - M), 'noticias de marketing, diseño y branding', font=fm, fill=INK, anchor='rs')
    can.save(out, 'JPEG', quality=92, optimize=True)


def slide3(data, out, n=3):
    can = Image.new('RGB', (W, H), PINK)
    d = ImageDraw.Draw(can)
    header(d, INK, n, dark_counter=True)
    maxw = W - 2 * M
    TR = -0.035
    fonts, ls, size = fitted(d, '¿Quieres saber _más_ de esta nota?', maxw, 3, 'lg-black.woff2', 124, 70, track=TR)
    fb = {'n': font('lg-regular.woff2', 42), 'pk': font('lg-bold.woff2', 42), 'hl': font('lg-regular.woff2', 42),
          'it': font('lg-italic.woff2', 42)}
    rl = layout(d, 'Léela completa en nuestra página web. Ahí te contamos todo y lo que significa para tu marca.', fb, maxw)
    block = len(ls) * size * 0.98 + 40 + len(rl) * 56 + 70 + 110
    y = (M + 64 + (H - M - 140)) / 2 - block / 2
    y = render(d, M, y, ls, fonts, size * 0.98, INK, it_color=WHITE, track=TR)
    y += 40
    y = render(d, M, y, rl, fb, 56, INK)
    # botón
    by = y + 70
    k = 1.0 + 0.07 * golpe()
    bw, bh = 520 * k, 110 * k
    cx, cy = M + 260, by + 55
    d.rounded_rectangle((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), radius=bh / 2, fill=INK)
    d.text((cx, cy + 2), 'LINK EN BIO  →', font=font('lg-black.woff2', int(40 * k)), fill=PINK, anchor='mm')
    # firma
    dt(d, (M, H - M - 70 - 42), 'LG.I', font('lg-bold.woff2', 84), INK, -0.05)
    d.text((M + 196, H - M - 88), 'La Guayaba', font=font('lg-regular.woff2', 30), fill=INK, anchor='lm')
    d.text((M + 196, H - M - 52), 'Ilustrada', font=font('lg-regular.woff2', 30), fill=INK, anchor='lm')
    d.text((W - M, H - M - 70), 'Síguenos para más\nnoticias creativas', font=font('lg-medium.woff2', 28), fill=INK,
           anchor='rm', align='right')
    can.save(out, 'JPEG', quality=92, optimize=True)


def make(data, outdir):
    global TOTAL
    os.makedirs(outdir, exist_ok=True)
    con_info = len(info_de(data)) >= 1
    TOTAL = 4 if con_info else 3
    for f in ('3.jpg', '4.jpg'):
        if os.path.exists(os.path.join(outdir, f)):
            os.remove(os.path.join(outdir, f))
    slide1(data, os.path.join(outdir, '1.jpg'))
    slide2(data, os.path.join(outdir, '2.jpg'))
    if con_info:
        slide_info(data, os.path.join(outdir, '3.jpg'), 3)
    slide3(data, os.path.join(outdir, f'{TOTAL}.jpg'), TOTAL)
    print(outdir)


if __name__ == '__main__':
    make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2])
