"""Formatos diarios de Guías LGI, cada uno con su propio diseño:
  antes_despues  (martes)    comparador con cortinilla, fondo carbón
  emprende       (miércoles) ticket de negocio sobre rosa
  leccion        (jueves)    periódico con sello de "LECCIÓN"
  checklist      (viernes)   libreta con casillas que se palomean
  marca_mx       (sábado)    archivo sepia con línea del tiempo
  prompt         (extra)     chat de IA que se escribe solo
  cobrar         (extra)     barras de precios que crecen
  rediseno       (extra)     mesa de diseño tipo Figma con cursor
  recursos       (extra)     tarjetas de libros, podcasts y canales
Uso: escenas(data, durs) -> lista de Esc para guias_estilos.render.
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import guias as G
from guias_estilos import (W, H, FPS, M, cl, eo, back, txt, pill, avion, boton, cubrir, zoom, degradado, Esc, cuadros,
                           polaroid_viva, ruta, PINK, INK, WHITE, PAPEL, LINEA, NEGRO, GRIS, font)

CREMA = '#F4EEE2'


# ---------- piezas comunes ----------
def media(e, w, h, dur, foco=0.45):
    """f(t) -> imagen RGB w x h: video (si hay) o foto con acercamiento lento."""
    if e.get('_video'):
        cs = cuadros(e['_video'], w, h, dur, e.get('desde', 0))
        return lambda t: Image.open(cs[min(len(cs) - 1, int(t * FPS))]).convert('RGB')
    if e.get('foto') and ruta(e['foto']):
        img = cubrir(e['foto'], w, h, foco)
        return lambda t: zoom(img, t, dur, 1.0, 1.1)
    return None


def redondear(im, r):
    mk = Image.new('L', im.size, 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = im.convert('RGBA'); out.putalpha(mk); return out


def tarjeta_media(e, w, h, dur, r=36, foco=0.45):
    f = media(e, w, h, dur, foco)
    if not f: return None
    return lambda t: redondear(f(t), r)


def encabezado(nombre, bg=PINK, fg=INK, txt_color=WHITE):
    im = Image.new('RGBA', (W, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    p = pill(nombre, 30, bg=bg, fg=fg); im.alpha_composite(p, (M, 90))
    d.text((M + p.width + 22, 90 + p.height // 2), 'GUÍAS LGI', font=font('lg-black.woff2', 30), fill=txt_color, anchor='lm')
    return lambda t: im


def fondo_plano(color):
    base = Image.new('RGB', (W, H), color)
    return lambda t: base


def apilar(capas, y0, gap=34):
    ys = []
    for c in capas:
        ys.append(y0); y0 += c.height + gap
    return ys


def cierre_comun(e, dur, bg, fg, sub_color, b1, b2, enc, fuente='lg-black.woff2', acento=PINK, sub_y=1740):
    tt = txt(e['titulo'], 100, W - 2 * M, fuente, fg, acento=acento, max_lines=5, min_size=60)
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', sub_color, lh=1.3)
    ys = G.centrar([tt, sb, b1, b2], gap=44, y_min=280, y_max=1650)
    return Esc(dur, fondo_plano(bg), [(tt, M, ys[0], 0.1, 'izq'), (sb, M, ys[1], 0.6, 'sube'), (b1, M, ys[2], 1.0, 'rebote'),
                                      (b2, M, ys[3], 1.3, 'rebote')], enc, sub_y=sub_y)


def icono_comentario(color, s=60):
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((3, 6, s - 3, s - 16), 14, fill=color); d.polygon([(14, s - 18), (14, s - 2), (30, s - 18)], fill=color)
    return im


# ---------- 1. ANTES Y DESPUÉS ----------
CARBON = '#161616'


def _contener(ref, w, h, fondo=WHITE, margen=0.16):
    im = Image.open(ruta(ref)).convert('RGBA')
    s = min(w * (1 - 2 * margen) / im.width, h * (1 - 2 * margen) / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    c = Image.new('RGBA', (w, h), fondo); c.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return c


def ad_compara(e, dur, enc):
    w, h = W - 2 * M, 760
    a = _contener(e['antes'], w, h, e.get('fondo_antes', WHITE)); b = _contener(e['despues'], w, h, e.get('fondo_despues', '#F5EBDC'))
    la, lb = pill('ANTES · ' + e.get('antes_txt', ''), 30, bg=INK, fg=WHITE), pill('DESPUÉS · ' + e.get('despues_txt', ''), 30)

    def comp(t):
        x = int(w * (1 - 0.5 * eo(cl((t - 0.4) / 1.4)) + (0.18 * math.sin((t - 2.2) * 1.2) if t > 2.2 else 0)))
        x = max(40, min(w - 40, x))
        im = a.copy(); im.paste(b.crop((x, 0, w, h)), (x, 0))
        d = ImageDraw.Draw(im)
        d.rectangle((x - 4, 0, x + 4, h), fill=PINK)
        d.ellipse((x - 44, h // 2 - 44, x + 44, h // 2 + 44), fill=PINK)
        d.text((x, h // 2), '‹ ›', font=font('lg-black.woff2', 44), fill=INK, anchor='mm')
        im.alpha_composite(la, (24, 24)); im.alpha_composite(lb, (w - lb.width - 24, h - lb.height - 24))
        return redondear(im, 36)
    tt = txt(e['titulo'], 84, W - 2 * M, max_lines=3, min_size=56)
    cu = txt(e.get('cuerpo', ''), 44, W - 2 * M, 'lg-regular.woff2', GRIS, lh=1.3, max_lines=5)
    return Esc(dur, fondo_plano(CARBON), [(comp, M, 250, 0.0, 'sube'), (tt, M, 1070, 0.5, 'izq'), (cu, M, 1090 + tt.height, 0.9, 'sube')],
               enc, sub_y=880)


def ad_punto(e, dur, enc):
    card = tarjeta_media(e, W - 2 * M, 760, dur)
    tt = txt(e['titulo'], 84, W - 2 * M, max_lines=3, min_size=56)
    cu = txt(e.get('cuerpo', ''), 44, W - 2 * M, 'lg-regular.woff2', GRIS, lh=1.3, max_lines=5)
    pz = ([(card, M, 250, 0.0, 'sube')] if card else []) + [(tt, M, 1070, 0.4, 'izq'), (cu, M, 1090 + tt.height, 0.8, 'sube')]
    return Esc(dur, fondo_plano(CARBON), pz, enc, sub_y=880)


def ad_colores(e, dur, enc):
    cols = e['colores']; n = len(cols); gap = 24; bw = (W - 2 * M - gap * (n - 1)) // n
    pz = []
    for k, (nombre, hexa) in enumerate(cols):
        def barra(t, k=k, nombre=nombre, hexa=hexa):
            h = int(700 * eo(cl((t - 0.2 - k * 0.25) / 0.9))) + 1
            im = Image.new('RGBA', (bw, 760), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            d.rounded_rectangle((0, 760 - h, bw - 1, 759), 30, fill=hexa)
            if h > 200:
                tc = INK if sum(Image.new('RGB', (1, 1), hexa).getpixel((0, 0))) > 380 else WHITE
                for j, ln in enumerate(G.wrap(d, nombre, font('lg-black.woff2', 34), bw - 40)):
                    d.text((24, 760 - h + 30 + j * 40), ln, font=font('lg-black.woff2', 34), fill=tc)
            return im
        pz.append((barra, M + k * (bw + gap), 250, 0.0, 'fijo'))
    tt = txt(e['titulo'], 84, W - 2 * M, max_lines=3, min_size=56)
    cu = txt(e.get('cuerpo', ''), 44, W - 2 * M, 'lg-regular.woff2', GRIS, lh=1.3, max_lines=5)
    return Esc(dur, fondo_plano(CARBON), pz + [(tt, M, 1070, 0.5, 'izq'), (cu, M, 1090 + tt.height, 0.9, 'sube')], enc, sub_y=880)


def ad_portada(e, dur, enc):
    f = media(e, W, H, dur, 0.4)
    grad = degradado(W, H, 700, 1350, color=(22, 22, 22), a1=255)

    def fondo(t):
        b = (f(t) if f else Image.new('RGB', (W, H), CARBON)).convert('RGBA'); b.alpha_composite(grad); return b
    tt = txt(e['titulo'], 112, W - 2 * M, max_lines=4, min_size=70)
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', GRIS, lh=1.25)
    return Esc(dur, fondo, [(tt, M, 1150, 0.2, 'izq'), (sb, M, 1170 + tt.height, 0.7, 'sube')], enc, sub_y=900)


def antes_despues(data, durs):
    enc = encabezado('ANTES Y DESPUÉS'); out = []
    for e, d in zip(data['escenas'], durs):
        t = e['tipo']
        if t == 'portada': out.append(ad_portada(e, d, enc))
        elif t == 'compara': out.append(ad_compara(e, d, enc))
        elif t == 'colores': out.append(ad_colores(e, d, enc))
        elif t == 'punto': out.append(ad_punto(e, d, enc))
        else: out.append(cierre_comun(e, d, CARBON, WHITE, GRIS, boton(icono_comentario(INK), 'COMENTA LA MARCA', 44, PINK, INK, W - 2 * M),
                                      boton(G.marcador(WHITE), 'GUÁRDALO', 44, (45, 45, 45), WHITE, W - 2 * M), enc))
    return out


# ---------- 2. EMPRENDE CON ----------
def ticket(titulo, filas, w, nota=None, numerado=False):
    """Recibo blanco con renglones; devuelve (fondo, [(capa_fila, y)])."""
    f_t, f_r, f_v = font('lg-black.woff2', 42), font('lg-medium.woff2', 50), font('lg-black.woff2', 52)
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    capas = []
    for k, fila in enumerate(filas):
        izq, der = (fila if isinstance(fila, (list, tuple)) else (fila, ''))
        pre = f'{k + 1:02d}  ' if numerado else ''
        maxw = w - 120 - (int(d0.textlength(der, font=f_v)) + 40 if der else 0)
        ls = G.wrap(d0, pre + izq, f_r, maxw)
        hh = len(ls) * 62 + 30
        c = Image.new('RGBA', (w - 80, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
        for j, ln in enumerate(ls):
            d.text((0, j * 62), ln, font=f_r, fill=INK)
        if der:
            tw = d.textlength(der, font=f_v); lw = d.textlength(ls[-1], font=f_r)
            y = (len(ls) - 1) * 62 + 38
            for x in range(int(lw + 14), int(w - 80 - tw - 14), 16): d.ellipse((x, y, x + 5, y + 5), fill=(150, 150, 150))
            d.text((w - 80 - tw, (len(ls) - 1) * 62 - 2), der, font=f_v, fill=PINK if not numerado else INK)
        capas.append(c)
    alto = 130 + sum(c.height + 14 for c in capas) + (80 if nota else 30) + 40
    base = Image.new('RGBA', (w, alto), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
    d.rectangle((0, 0, w - 1, alto - 40), fill=WHITE)
    for x in range(0, w, 40): d.polygon([(x, alto - 41), (x + 20, alto - 4), (x + 40, alto - 41)], fill=WHITE)
    d.text((40, 50), titulo, font=f_t, fill=INK)
    for x in range(40, w - 40, 22): d.line((x, 110, x + 11, 110), fill=INK, width=3)
    ys, y = [], 140
    for c in capas:
        ys.append(y); y += c.height + 14
    if nota:
        d.text((40, y + 14), nota, font=font('lg-regular.woff2', 30), fill=(120, 120, 120))
    sombra = Image.new('RGBA', (w + 40, alto + 40), (0, 0, 0, 0)); sm = Image.new('L', sombra.size, 0)
    ImageDraw.Draw(sm).rectangle((20, 34, w + 20, alto + 6), fill=90); sombra.putalpha(sm.filter(ImageFilter.GaussianBlur(14)))
    sombra.alpha_composite(base, (20, 20))
    return sombra, [(c, 60, yy + 20) for c, yy in zip(capas, ys)]


def em_ticket(e, dur, enc, numerado=False):
    w = W - 2 * M
    base, filas = ticket(e['titulo'], e['filas'], w, e.get('nota'), numerado)
    y0 = max(300, (1700 - base.height) // 2) if not e.get('foto') else 800
    pz = []
    if e.get('foto') and ruta(e['foto']):
        pv = polaroid_viva(e['foto'], 700, 460, -4, dur, 2); pz.append((pv, (W - pv(0).width) // 2, 220, 0.0, 'flota'))
    pz.append((base, M - 20, y0, 0.15, 'sube'))
    paso = max(0.5, (dur - 1.8) / max(1, len(filas)))
    for k, (c, x, y) in enumerate(filas): pz.append((c, M - 20 + x, y0 + y, 0.7 + k * paso, 'izq'))
    return Esc(dur, fondo_plano(PINK), pz, enc, sub_y=1745)


def em_nombres(e, dur, enc):
    tt = txt(e['titulo'], 96, W - 2 * M, 'lg-black.woff2', INK, acento=WHITE, max_lines=3)
    pz = [(tt, M, 300, 0.0, 'izq')]
    rnd = random.Random(3); y = 330 + tt.height + 40
    for k, n in enumerate(e['nombres']):
        p = pill(n, 64, bg=WHITE if k % 2 == 0 else INK, fg=INK if k % 2 == 0 else WHITE, padx=44, pady=26)
        p = p.rotate(rnd.uniform(-5, 5), resample=Image.BICUBIC, expand=True)
        pz.append((p, M + [0, 160, 60][k % 3], y, 0.6 + k * 0.45, 'rebote')); y += p.height + 20
    cu = txt(e.get('cuerpo', ''), 46, W - 2 * M, 'lg-bold.woff2', INK, lh=1.3, max_lines=4)
    pz.append((cu, M, y + 30, 0.8 + len(e['nombres']) * 0.45, 'sube'))
    return Esc(dur, fondo_plano(PINK), pz, enc, sub_y=1745)


def em_portada(e, dur, enc):
    pz = []
    if e.get('foto') and ruta(e['foto']):
        pv = polaroid_viva(e['foto'], 800, 640, -3, dur, 1); pz.append((pv, (W - pv(0).width) // 2, 210, 0.0, 'flota'))
    et = pill(e.get('etiqueta', ''), 34, bg=WHITE, fg=INK); pz.append((et, M, 1060, 0.3, 'rebote'))
    tt = txt(e['titulo'], 112, W - 2 * M, 'lg-black.woff2', INK, acento=WHITE, max_lines=4, min_size=70)
    pz.append((tt, M, 1140, 0.5, 'izq'))
    sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-bold.woff2', INK, lh=1.25); pz.append((sb, M, 1160 + tt.height, 0.9, 'sube'))
    return Esc(dur, fondo_plano(PINK), pz, enc, sub_y=1760)


def emprende(data, durs):
    enc = encabezado('EMPRENDE CON', bg=INK, fg=WHITE, txt_color=INK); out = []
    for e, d in zip(data['escenas'], durs):
        t = e['tipo']
        if t == 'portada': out.append(em_portada(e, d, enc))
        elif t == 'ticket': out.append(em_ticket(e, d, enc))
        elif t == 'pasos': out.append(em_ticket(e, d, enc, numerado=True))
        elif t == 'nombres': out.append(em_nombres(e, d, enc))
        else: out.append(cierre_comun(e, d, INK, WHITE, '#CFCFCF', boton(icono_comentario(INK), 'COMENTA TU IDEA', 44, PINK, INK, W - 2 * M),
                                      boton(G.marcador(INK), 'GUÁRDALO', 44, WHITE, INK, W - 2 * M), enc))
    return out


# ---------- 3. LA LECCIÓN DE ----------
PERIODICO = '#ECE6D9'


def periodico():
    im = Image.new('RGB', (W, H), PERIODICO); d = ImageDraw.Draw(im)
    rnd = random.Random(7)
    for _ in range(9000):
        x, y = rnd.randrange(W), rnd.randrange(H); v = rnd.randrange(200, 225)
        d.point((x, y), fill=(v, v - 6, v - 16))
    d.text((W // 2, 150), 'La lección de...', font=font('serif-italic.woff2', 76), fill=INK, anchor='mm')
    d.line((M, 215, W - M, 215), fill=INK, width=4); d.line((M, 225, W - M, 225), fill=INK, width=1)
    d.text((M, 250), 'GUÍAS LGI', font=font('lg-black.woff2', 24), fill=INK)
    d.text((W - M, 250), 'CASOS QUE ENSEÑAN', font=font('lg-black.woff2', 24), fill=INK, anchor='ra')
    d.line((M, 292, W - M, 292), fill=INK, width=1)
    return im


def duotono(ref, w, h, dur):
    im = cubrir(ref, w, h)
    g = ImageOps.colorize(ImageOps.autocontrast(im.convert('L')), black='#1A1414', white=PERIODICO, mid='#C9667F')
    return lambda t: redondear(zoom(g, t, dur, 1.0, 1.08), 6)


def sello(texto_, color=PINK):
    f = font('lg-black.woff2', 70); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    tw = int(d0.textlength(texto_, font=f))
    im = Image.new('RGBA', (tw + 80, 140), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, im.width - 5, im.height - 5), 16, outline=color, width=8)
    d.text((im.width // 2, im.height // 2), texto_, font=f, fill=color, anchor='mm')
    return im.rotate(-8, resample=Image.BICUBIC, expand=True)


def le_escena(e, dur, base, portada=False):
    pz = []
    y = 330
    if e.get('kicker'):
        k = txt(e['kicker'], 32, W - 2 * M, 'lg-black.woff2', PINK, max_lines=1); pz.append((k, M, y, 0.0, 'izq')); y += k.height + 10
    sin_foto = not (e.get('foto') and ruta(e['foto']))
    tt = G.texto(e['titulo'], 100 if portada else (116 if sin_foto else 84), W - 2 * M, 'serif.woff2', INK, lh=1.08, max_lines=5, min_size=56)
    if sin_foto: y = 520
    pz.append((tt, M, y, 0.25, 'sube')); y += tt.height + 20
    if e.get('foto') and ruta(e['foto']):
        hh = 1640 - y - (180 if e.get('cuerpo') else 0)
        hh = max(360, min(700, hh))
        pz.append((duotono(e['foto'], W - 2 * M, hh, dur), M, y, 0.55, 'sube'))
        if e.get('pie'):
            pz.append((txt(e['pie'], 26, W - 2 * M, 'lg-regular.woff2', (90, 80, 70), max_lines=1), M, y + hh + 8, 0.8, 'sube'))
        y += hh + 54
    if e.get('cuerpo'):
        cu = G.texto(e['cuerpo'], 58 if sin_foto else 46, W - 2 * M, 'lg-regular.woff2', INK, lh=1.35, max_lines=7, min_size=32)
        pz.append((cu, M, y, 0.9, 'sube'))
    if e.get('sello'):
        s = sello(e['sello']); pz.append((s, W - M - s.width + 20, 1380, 1.2, 'rebote'))
    return Esc(dur, lambda t: base, pz, None, sub_y=1745)


def leccion(data, durs):
    base = periodico(); out = []
    for e, d in zip(data['escenas'], durs):
        if e['tipo'] == 'cierre':
            sc = cierre_comun(e, d, PERIODICO, INK, (80, 70, 60), boton(icono_comentario(INK), 'CUÉNTALO EN COMENTARIOS', 40, PINK, INK, W - 2 * M),
                              boton(G.marcador(PERIODICO), 'GUÁRDALO', 44, INK, PERIODICO, W - 2 * M), None, fuente='serif.woff2')
            sc.fondo = lambda t: base; out.append(sc)
        else:
            out.append(le_escena(e, d, base, e['tipo'] == 'portada'))
    return out


# ---------- 4. CHECKLIST ----------
def libreta():
    im = Image.new('RGB', (W, H), '#FBFAF6'); d = ImageDraw.Draw(im)
    for y in range(330, H, 72): d.line((0, y, W, y), fill='#DCE3EC', width=2)
    d.line((150, 0, 150, H), fill=PINK, width=3)
    return im


def telefono(w=520, h=900):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 70, fill=INK)
    d.rounded_rectangle((18, 18, w - 19, h - 19), 56, fill=WHITE)
    d.rounded_rectangle((w // 2 - 60, 34, w // 2 + 60, 62), 14, fill=INK)
    d.ellipse((50, 110, 190, 250), fill=PINK); d.text((120, 180), 'LGI', font=font('lg-black.woff2', 40), fill=INK, anchor='mm')
    for k, x in enumerate((230, 320, 410)):
        d.text((x, 160), ['48', '1.2k', '310'][k], font=font('lg-black.woff2', 30), fill=INK, anchor='mm')
        d.rounded_rectangle((x - 34, 192, x + 34, 204), 6, fill='#DDDDDD')
    for k, ww in enumerate((300, 380, 240)): d.rounded_rectangle((50, 290 + k * 34, 50 + ww, 308 + k * 34), 9, fill='#E5E5E5' if k else '#BDBDBD')
    for k in range(5): d.ellipse((50 + k * 88, 420, 120 + k * 88, 490), outline=PINK, width=5)
    for r in range(3):
        for c in range(3):
            x0 = 30 + c * ((w - 60) // 3); y0 = 530 + r * 112
            d.rectangle((x0 + 3, y0, x0 + (w - 60) // 3 - 3, y0 + 106), fill=['#F7C6D3', '#EDEDED', '#FFD9E3'][(r + c) % 3])
    return im


def casilla(texto_, w, t_check):
    f = font('lg-medium.woff2', 58); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    ls = G.wrap(d0, texto_, f, w - 140); hh = max(120, len(ls) * 70 + 30)

    def cap(t):
        im = Image.new('RGBA', (w, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 8, 80, 88), 16, outline=INK, width=6)
        p = cl((t - t_check) / 0.35)
        if p > 0:
            d.rounded_rectangle((0, 8, 80, 88), 16, fill=PINK, outline=INK, width=6)
            a, b, c = (16, 50), (36, 70), (66, 26)
            if p < 0.5: d.line([a, (a[0] + (b[0] - a[0]) * p * 2, a[1] + (b[1] - a[1]) * p * 2)], fill=INK, width=10)
            else: d.line([a, b, (b[0] + (c[0] - b[0]) * (p - .5) * 2, b[1] + (c[1] - b[1]) * (p - .5) * 2)], fill=INK, width=10, joint='curve')
        for j, ln in enumerate(ls): d.text((120, 6 + j * 70), ln, font=f, fill=INK)
        return im
    return cap, hh


def ck_items(e, dur, enc):
    pz = []
    tt = txt(e['titulo'], 100, W - 2 * M - 70, 'lg-black.woff2', INK, acento=PINK, max_lines=2)
    paso = max(0.7, (dur - 1.2) / max(1, len(e['items'])))
    cs = [casilla(it, W - 190 - M, 0.5 + k * paso + 0.4) for k, it in enumerate(e['items'])]
    alto = tt.height + 60 + sum(hh + 50 for _, hh in cs)
    y = max(330, (1680 - alto) // 2); pz.append((tt, 190, y, 0.0, 'izq')); y += tt.height + 60
    for k, (cap, hh) in enumerate(cs):
        pz.append((cap, 190, y, 0.3 + k * paso, 'izq')); y += hh + 50
    return Esc(dur, lambda t, b=libreta(): b, pz, enc, sub_y=1745)


def ck_portada(e, dur, enc):
    tel = telefono()
    tt = txt(e['titulo'], 100, W - 2 * M, 'lg-black.woff2', INK, max_lines=4, min_size=64)
    return Esc(dur, lambda t, b=libreta(): b, [(tel.rotate(-6, resample=Image.BICUBIC, expand=True), 300, 250, 0.0, 'flota'),
                                              (tt, M, 1190, 0.4, 'izq')], enc, sub_y=1730)


def checklist(data, durs):
    enc = encabezado('CHECKLIST', txt_color=INK); out = []
    for e, d in zip(data['escenas'], durs):
        if e['tipo'] == 'portada': out.append(ck_portada(e, d, enc))
        elif e['tipo'] == 'items': out.append(ck_items(e, d, enc))
        else:
            sc = cierre_comun(e, d, '#FBFAF6', INK, (90, 90, 90), boton(avion(INK), 'MÁNDASELO', 46, PINK, INK, W - 2 * M),
                              boton(G.marcador(WHITE), 'GUÁRDALO', 46, INK, WHITE, W - 2 * M), enc)
            sc.fondo = lambda t, b=libreta(): b; out.append(sc)
    return out


# ---------- 5. MARCA MEXICANA ----------
CAFE = '#231A14'
CREMA_V = '#F1E4CC'


def grano(t):
    rnd = random.Random(int(t * FPS) % 6)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for _ in range(500):
        x, y = rnd.randrange(W), rnd.randrange(H); d.point((x, y), fill=(255, 240, 210, rnd.randrange(30, 90)))
    for _ in range(2):
        x = rnd.randrange(W); d.line((x, 0, x, H), fill=(255, 240, 210, 18), width=1)
    return im


_GRANOS = {}


def con_grano(base_f):
    def f(t):
        k = int(t * FPS) % 6
        if k not in _GRANOS: _GRANOS[k] = grano(k / FPS)
        im = base_f(t).convert('RGBA'); im.alpha_composite(_GRANOS[k]); return im
    return f


def sepia(img, p):
    """p=1 sepia total, p=0 color."""
    s = ImageOps.colorize(img.convert('L'), black='#2A1D12', white='#F6E7C8')
    return Image.blend(img.convert('RGB'), s, p)


def mx_portada(e, dur):
    img = cubrir(e['foto'], W, H, 0.4) if e.get('foto') and ruta(e['foto']) else Image.new('RGB', (W, H), CAFE)
    grad = degradado(W, H, 650, 1350, color=(35, 26, 20), a1=255)

    def f(t):
        b = sepia(zoom(img, t, dur, 1.0, 1.1), 1 - eo(cl((t - 1.0) / 1.5))).convert('RGBA'); b.alpha_composite(grad); return b
    et = pill(e.get('etiqueta', 'MARCA MEXICANA'), 32, bg=PINK, fg=INK)
    tt = txt(e['titulo'], 108, W - 2 * M, 'serif.woff2', CREMA_V, acento=PINK, lh=1.05, max_lines=4, min_size=64)
    sb = txt(e.get('sub', ''), 44, W - 2 * M, 'lg-medium.woff2', '#D9C9AE', lh=1.25)
    return Esc(dur, con_grano(f), [(et, M, 1080, 0.3, 'rebote'), (tt, M, 1170, 0.5, 'izq'), (sb, M, 1190 + tt.height, 0.9, 'sube')],
               None, sub_y=900)


def mx_ano(e, dur, k, total):
    base = Image.new('RGB', (W, H), CAFE); d = ImageDraw.Draw(base)
    d.line((110, 230, 110, H - 200), fill=(90, 70, 55), width=6)
    pz = []

    def linea(t):
        im = Image.new('RGBA', (40, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(im)
        y1 = 230 + (H - 430) * ((k + eo(cl(t / 1.2))) / total)
        dd.line((20, 230, 20, y1), fill=PINK, width=8); dd.ellipse((4, y1 - 16, 36, y1 + 16), fill=PINK)
        return im
    pz.append((linea, 90, 0, 0.0, 'fijo'))
    ano = txt(e['ano'], 170, W - 260, 'serif-italic.woff2', PINK, max_lines=1); pz.append((ano, 180, 230, 0.1, 'izq'))
    y = 230 + ano.height
    if e.get('foto') and ruta(e['foto']):
        img = cubrir(e['foto'], W - 260 - M, 760)

        def foto(t):
            im = sepia(zoom(img, t, dur, 1.0, 1.1), 0.75).convert('RGBA')
            m = Image.new('RGBA', (im.width + 30, im.height + 30), CREMA_V); m.paste(im, (15, 15)); return m
        pz.append((foto, 180, y + 10, 0.4, 'sube')); y += 820
    cu = txt(e['cuerpo'], 60, W - 260 - M, 'lg-medium.woff2', CREMA_V, acento=PINK, lh=1.3, max_lines=6, min_size=36)
    pz.append((cu, 180, y + 20, 0.8, 'sube'))
    return Esc(dur, con_grano(lambda t: base), pz, None, sub_y=1745)


def marca_mx(data, durs):
    out = []; esc = data['escenas']; anos = [e for e in esc if e['tipo'] == 'ano']; k = 0
    for e, d in zip(esc, durs):
        if e['tipo'] == 'portada': out.append(mx_portada(e, d))
        elif e['tipo'] == 'ano': out.append(mx_ano(e, d, k, len(anos))); k += 1
        else:
            sc = cierre_comun(e, d, CAFE, CREMA_V, '#D9C9AE', boton(icono_comentario(INK), 'COMENTA LA MARCA', 44, PINK, INK, W - 2 * M),
                              boton(G.marcador(CAFE), 'GUÁRDALO', 44, CREMA_V, CAFE, W - 2 * M), None, fuente='serif.woff2')
            sc.fondo = con_grano(lambda t: Image.new('RGB', (W, H), CAFE)); out.append(sc)
    return out


# ---------- 6. PROMPT DE LA SEMANA ----------
OSCURO = '#101014'


def burbuja(texto_, w, bg, fg, size=42, parcial=None, etiqueta=None, fuente='lg-medium.woff2'):
    f = font(fuente, size); d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    ls = []
    for par in texto_.split('\n'): ls += G.wrap(d0, par, f, w - 80) or ['']
    lh = int(size * 1.32); hh = len(ls) * lh + 70 + (50 if etiqueta else 0)

    def cap(t):
        im = Image.new('RGBA', (w, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, hh - 1), 40, fill=bg)
        y = 36
        if etiqueta: d.text((40, y), etiqueta, font=font('lg-black.woff2', 26), fill=PINK if bg != PINK else INK); y += 50
        n = len(texto_) if parcial is None else int(parcial(t))
        cuenta = 0
        for ln in ls:
            if cuenta >= n: break
            vis = ln[:max(0, n - cuenta)]; d.text((40, y), vis, font=f, fill=fg); cuenta += len(ln) + 1; y += lh
        return im
    return cap, hh


def pr_prompt(e, dur, enc):
    w = W - 2 * M
    lab = pill('COPIA ESTE PROMPT', 30, bg=WHITE, fg=INK)
    total = len(e['prompt']); vel = total / max(1.5, dur - 2.0)
    cap, hh = burbuja(e['prompt'], w, PINK, INK, 56, parcial=lambda t: max(0, (t - 0.6) * vel))
    y = max(300, (1680 - hh - lab.height - 30) // 2)
    return Esc(dur, fondo_plano(OSCURO), [(lab, M, y, 0.0, 'rebote'), (cap, M, y + lab.height + 30, 0.3, 'sube')], enc, sub_y=1745)


def pr_respuesta(e, dur, enc):
    w = W - 2 * M - 40
    pz = []; y = 380
    q, qh = burbuja(e.get('pregunta', ''), w - 120, '#2A2A31', WHITE, 46)
    if e.get('pregunta'):
        pz.append((q, W - M - (w - 120), y, 0.0, 'izq')); y += qh + 30
    filas = e['lineas']; paso = max(0.4, (dur - 1.5) / max(1, len(filas)))
    cap, hh = burbuja('\n'.join(filas), w, '#24242B', WHITE, 52, etiqueta=e.get('etiqueta', 'EJEMPLO DE RESPUESTA'),
                      parcial=lambda t: sum(len(x) + 1 for x in filas[:int(max(0, t - 0.6) / paso) + 1]))
    pz.append((cap, M, y, 0.4, 'sube'))
    return Esc(dur, fondo_plano(OSCURO), pz, enc, sub_y=1745)


def pr_tip(e, dur, enc):
    tt = txt(e['titulo'], 116, W - 2 * M, max_lines=4)
    cu = txt(e.get('cuerpo', ''), 60, W - 2 * M, 'lg-regular.woff2', '#CFCFD6', lh=1.35, max_lines=6)
    ys = G.centrar([tt, cu], gap=40, y_min=300, y_max=1650)
    return Esc(dur, fondo_plano(OSCURO), [(tt, M, ys[0], 0.0, 'izq'), (cu, M, ys[1], 0.5, 'sube')], enc, sub_y=1745)


def chispas(t):
    im = Image.new('RGBA', (W, 900), (0, 0, 0, 0)); d = ImageDraw.Draw(im); rnd = random.Random(5)
    for k in range(14):
        x, y, s = rnd.randrange(80, W - 80), rnd.randrange(60, 840), rnd.randrange(14, 46)
        a = 0.5 + 0.5 * math.sin(t * 2 + k); s2 = s * (0.6 + 0.4 * a)
        d.polygon([(x, y - s2), (x + s2 * .25, y - s2 * .25), (x + s2, y), (x + s2 * .25, y + s2 * .25), (x, y + s2),
                   (x - s2 * .25, y + s2 * .25), (x - s2, y), (x - s2 * .25, y - s2 * .25)], fill=PINK if k % 3 else WHITE)
    return im


def prompt(data, durs):
    enc = encabezado('PROMPT DE LA SEMANA'); out = []
    for e, d in zip(data['escenas'], durs):
        t = e['tipo']
        if t == 'portada':
            tt = txt(e['titulo'], 116, W - 2 * M, max_lines=4, min_size=70)
            sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', '#CFCFD6', lh=1.25)
            cap, _ = burbuja('Actúa como experto en...', 640, PINK, INK, 40, parcial=lambda t: t * 14)
            out.append(Esc(d, fondo_plano(OSCURO), [(chispas, 0, 200, 0.0, 'fijo'), (cap, W - M - 640, 520, 0.2, 'sube'),
                                                   (tt, M, 1050, 0.5, 'izq'), (sb, M, 1070 + tt.height, 0.9, 'sube')], enc, sub_y=850))
        elif t == 'prompt': out.append(pr_prompt(e, d, enc))
        elif t == 'respuesta': out.append(pr_respuesta(e, d, enc))
        elif t == 'tip': out.append(pr_tip(e, d, enc))
        else: out.append(cierre_comun(e, d, OSCURO, WHITE, '#CFCFD6', boton(icono_comentario(INK), 'COMENTA QUÉ TE SALIÓ', 42, PINK, INK, W - 2 * M),
                                      boton(G.marcador(WHITE), 'GUÁRDALO', 44, (45, 45, 52), WHITE, W - 2 * M), enc))
    return out


# ---------- 7. ¿CUÁNTO COBRAR? ----------
def pesos(n):
    return '$' + f'{n:,.0f}'


def cc_rangos(e, dur, enc):
    tope = e.get('tope', 25000); w = W - 2 * M
    tt = txt(e['titulo'], 96, w, 'lg-black.woff2', INK, max_lines=2)
    y0 = max(300, (1650 - tt.height - 40 - 290 * len(e['filas'])) // 2); pz = [(tt, M, y0, 0.0, 'izq')]
    y = y0 + tt.height + 40; paso = max(0.6, (dur - 1.5) / max(1, len(e['filas'])))
    for k, (lab, a, b, mas) in enumerate(e['filas']):
        def fila(t, lab=lab, a=a, b=b, mas=mas, k=k):
            im = Image.new('RGBA', (w, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            d.text((0, 0), lab, font=font('lg-bold.woff2', 52), fill=INK)
            d.rounded_rectangle((0, 80, w - 1, 128), 24, fill='#EDEDED')
            p = eo(cl((t - 0.5 - k * paso) / 0.9))
            x0 = int(w * a / tope); x1 = int(w * min(b, tope) / tope)
            x1 = x0 + int((x1 - x0) * p)
            d.rounded_rectangle((x0, 80, max(x0 + 48, x1), 128), 24, fill=PINK)
            if p > 0.6:
                fv = font('lg-black.woff2', 48)
                d.text((x0, 150), pesos(a), font=fv, fill=INK)
                tb = pesos(b) + ('+' if mas else ''); d.text((w, 150), tb, font=fv, fill=INK, anchor='ra')
            return im
        pz.append((fila, M, y, 0.3 + k * paso, 'sube')); y += 290
    if e.get('nota'):
        pz.append((txt(e['nota'], 28, w, 'lg-regular.woff2', (110, 110, 110), max_lines=2), M, y + 10, 1.0, 'sube'))
    return Esc(dur, fondo_plano(WHITE), pz, enc, sub_y=1745)


def cc_chips(e, dur, enc):
    tt = txt(e['titulo'], 110, W - 2 * M, 'lg-black.woff2', INK, max_lines=3); pz = [(tt, M, 520, 0.0, 'izq')]
    x, y = M, 560 + tt.height + 40
    for k, c in enumerate(e['chips']):
        f = font('lg-bold.woff2', 58); tw = int(ImageDraw.Draw(Image.new('RGB', (4, 4))).textlength(c, font=f))
        im = Image.new('RGBA', (tw + 90, 130), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((3, 3, im.width - 4, 126), 64, outline=INK, width=5, fill=PINK if k % 2 == 0 else WHITE)
        d.text((45, 65), c, font=f, fill=INK, anchor='lm')
        if x + im.width > W - M: x, y = M, y + 156
        pz.append((im, x, y, 0.5 + k * 0.4, 'rebote')); x += im.width + 22
    return Esc(dur, fondo_plano(WHITE), pz, enc, sub_y=1745)


def cc_tip(e, dur, enc):
    w = W - 2 * M
    tt = txt(e['titulo'], 110, w - 100, 'lg-black.woff2', WHITE, max_lines=5)
    caja = Image.new('RGBA', (w, tt.height + 220), (0, 0, 0, 0)); d = ImageDraw.Draw(caja)
    d.rounded_rectangle((0, 0, w - 1, caja.height - 1), 44, fill=INK)
    d.text((50, 30), '“', font=font('serif.woff2', 200), fill=PINK)
    caja.alpha_composite(tt, (50, 170))
    cu = txt(e.get('cuerpo', ''), 58, w, 'lg-medium.woff2', INK, lh=1.3, max_lines=5)
    ys = G.centrar([caja, cu], gap=40, y_min=300, y_max=1650)
    return Esc(dur, fondo_plano(WHITE), [(caja, M, ys[0], 0.0, 'rebote'), (cu, M, ys[1], 0.6, 'sube')], enc, sub_y=1745)


def cobrar(data, durs):
    enc = encabezado('¿CUÁNTO COBRAR?', txt_color=INK); out = []
    for e, d in zip(data['escenas'], durs):
        t = e['tipo']
        if t == 'portada':
            def signo(t):
                im = Image.new('RGBA', (W, 1100), (0, 0, 0, 0)); dd = ImageDraw.Draw(im)
                dd.text((W // 2, 520), '$', font=font('lg-black.woff2', 1000), fill=PINK, anchor='mm')
                return im.rotate(math.sin(t * 1.3) * 6, resample=Image.BICUBIC)
            tt = txt(e['titulo'], 116, W - 2 * M, 'lg-black.woff2', INK, max_lines=4, min_size=70)
            sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', (80, 80, 80), lh=1.25)
            out.append(Esc(d, fondo_plano(WHITE), [(signo, 0, 160, 0.0, 'rebote'), (tt, M, 1150, 0.4, 'izq'),
                                                  (sb, M, 1170 + tt.height, 0.8, 'sube')], enc, sub_y=1000))
        elif t == 'rangos': out.append(cc_rangos(e, d, enc))
        elif t == 'chips': out.append(cc_chips(e, d, enc))
        elif t == 'tip': out.append(cc_tip(e, d, enc))
        else:
            sc = cierre_comun(e, d, WHITE, INK, (80, 80, 80), boton(avion(INK), 'MÁNDASELO A UN DISEÑADOR', 40, PINK, INK, W - 2 * M),
                              boton(G.marcador(WHITE), 'GUÁRDALO', 44, INK, WHITE, W - 2 * M), enc)
            out.append(sc)
    return out


# ---------- 8. REDISEÑO EXPRESS ----------
LIENZO = '#E8E8EC'
ROJO, CREMA_T, CARB = '#D7261E', '#F4E3C1', '#1A1A1A'


def lienzo():
    im = Image.new('RGB', (W, H), LIENZO); d = ImageDraw.Draw(im)
    for x in range(20, W, 40):
        for y in range(20, H, 40): d.ellipse((x - 2, y - 2, x + 2, y + 2), fill='#C9C9D0')
    return im


def marco(nombre, w, h):
    im = Image.new('RGBA', (w, h + 50), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((4, 0), nombre, font=font('lg-medium.woff2', 28), fill=(110, 110, 120))
    d.rectangle((0, 46, w - 1, h + 49), fill=WHITE, outline='#B9B9C4', width=2)
    return im


def cursor(pos_f):
    def f(t):
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x, y = pos_f(t)
        d.polygon([(x, y), (x, y + 56), (x + 15, y + 42), (x + 28, y + 66), (x + 38, y + 60), (x + 25, y + 37), (x + 44, y + 36)],
                  fill=INK, outline=WHITE)
        p = pill('LGI', 24, bg=PINK, fg=INK, padx=16, pady=8); im.alpha_composite(p, (int(x + 40), int(y + 62)))
        return im
    return f


def mover(pts, dur):
    def f(t):
        u = cl(t / max(0.1, dur - 0.5)) * (len(pts) - 1); i = min(int(u), len(pts) - 2); p = eo(u - i)
        return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * p, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * p
    return f


def logo_lumbre(s=520, nombre='LA LUMBRE', sub='TAQUERÍA · CUERNAVACA'):
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((0, 0, s - 1, s - 1), fill=CARB); d.ellipse((s * .05, s * .05, s * .95, s * .95), fill=CREMA_T)
    cx = s / 2
    d.polygon([(cx, s * .14), (cx + s * .16, s * .36), (cx + s * .10, s * .30), (cx + s * .14, s * .52), (cx, s * .44),
               (cx - s * .14, s * .52), (cx - s * .10, s * .30), (cx - s * .16, s * .36)], fill=ROJO)
    d.ellipse((cx - s * .14, s * .34, cx + s * .14, s * .56), fill=ROJO)
    d.ellipse((cx - s * .06, s * .42, cx + s * .06, s * .54), fill=CREMA_T)
    d.rounded_rectangle((s * .08, s * .58, s * .92, s * .74), 14, fill=CARB)
    d.text((cx, s * .66), nombre, font=font('lg-black.woff2', int(s * .11)), fill=CREMA_T, anchor='mm')
    d.text((cx, s * .82), sub, font=font('lg-bold.woff2', int(s * .045)), fill=CARB, anchor='mm')
    return im


def boceto(s=520):
    """El logo dibujado a lápiz: trazos temblorosos que aparecen poco a poco."""
    rnd = random.Random(11); trazos = []
    def circulo(cx, cy, r, n=60):
        return [(cx + r * math.cos(2 * math.pi * k / n) + rnd.uniform(-4, 4), cy + r * math.sin(2 * math.pi * k / n) + rnd.uniform(-4, 4)) for k in range(n + 2)]
    cx = s / 2
    trazos.append(circulo(cx, cx, s * .46)); trazos.append(circulo(cx, cx, s * .42))
    trazos.append([(cx, s * .14), (cx + s * .16, s * .36), (cx + s * .1, s * .3), (cx + s * .14, s * .52), (cx, s * .44),
                   (cx - s * .14, s * .52), (cx - s * .1, s * .3), (cx - s * .16, s * .36), (cx, s * .14)])
    trazos.append([(s * .1, s * .6), (s * .9, s * .6), (s * .9, s * .73), (s * .1, s * .73), (s * .1, s * .6)])
    for k in range(6): trazos.append([(s * (.2 + k * .1), s * .63), (s * (.25 + k * .1), s * .70)])

    def f(t):
        im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        p = cl(t / 2.2) * len(trazos)
        for k, tr in enumerate(trazos):
            if k > p: break
            n = len(tr) if k < int(p) else max(2, int(len(tr) * (p - k)))
            d.line(tr[:n], fill=(60, 60, 70), width=4, joint='curve')
        return im
    return f


def rd_frame(e, dur, contenido, nombre):
    base = lienzo(); w, h = W - 2 * M, 900
    mk = marco(nombre, w, h)
    pz = [(mk, M, 300, 0.0, 'sube')]
    for c, x, y, te, ef in contenido: pz.append((c, M + x, 346 + y, te, ef))
    tt = txt(e['titulo'], 72, W - 2 * M, 'lg-black.woff2', INK, max_lines=2)
    cu = txt(e.get('cuerpo', ''), 42, W - 2 * M, 'lg-regular.woff2', (70, 70, 80), lh=1.3, max_lines=4)
    pz += [(tt, M, 1290, 0.4, 'izq'), (cu, M, 1300 + tt.height, 0.8, 'sube')]
    pts = e.get('_cursor') or [(W * .7, 1100), (W * .45, 700), (W * .6, 520)]
    pz.append((cursor(mover(pts, dur)), 0, 0, 0.0, 'fijo'))
    return Esc(dur, lambda t: base, pz, None, sub_y=1745)


def rediseno(data, durs):
    out = []; w, h = W - 2 * M, 900
    for e, d in zip(data['escenas'], durs):
        t = e['tipo']
        if t == 'portada':
            base = lienzo()
            lg = logo_lumbre(420); bs = boceto(420)
            et = pill('REDISEÑO EXPRESS', 32)
            tt = txt(e['titulo'], 108, W - 2 * M, 'lg-black.woff2', INK, max_lines=4, min_size=70)
            sb = txt(e.get('sub', ''), 42, W - 2 * M, 'lg-medium.woff2', (90, 90, 100), lh=1.25)
            fr1, fr2 = marco('Boceto', 440, 440), marco('Logo final', 440, 440)
            out.append(Esc(d, lambda t, b=base: b, [(fr1, M, 260, 0.0, 'sube'), (bs, M + 10, 316, 0.2, 'fijo'), (fr2, W - M - 440, 360, 0.3, 'sube'),
                                                   (lg, W - M - 430, 416, 1.2, 'rebote'), (et, M, 1000, 0.5, 'rebote'),
                                                   (tt, M, 1090, 0.7, 'izq'), (sb, M, 1110 + tt.height, 1.0, 'sube'),
                                                   (cursor(mover([(W * .8, 1500), (W * .3, 600), (W * .75, 700)], d)), 0, 0, 0, 'fijo')],
                           None, sub_y=1760))
        elif t == 'brief':
            filas = [txt(f'*{k}:* {v}', 58, w - 100, 'lg-medium.woff2', INK, lh=1.3, max_lines=3) for k, v in e['datos']]
            cont, y = [], 70
            for k, f_ in enumerate(filas): cont.append((f_, 50, y, 0.4 + k * 0.5, 'izq')); y += f_.height + 40
            out.append(rd_frame(e, d, cont, 'Frame 1 · Brief'))
        elif t == 'boceto':
            out.append(rd_frame(e, d, [(boceto(600), (w - 600) // 2, 150, 0.2, 'fijo')], 'Frame 2 · Boceto'))
        elif t == 'paleta':
            cont = []
            for k, (n, hx) in enumerate(e['colores']):
                sw = Image.new('RGBA', (230, 380), (0, 0, 0, 0)); dd = ImageDraw.Draw(sw)
                dd.rounded_rectangle((0, 0, 229, 300), 24, fill=hx, outline='#CCCCCC', width=2)
                dd.text((6, 316), n, font=font('lg-bold.woff2', 30), fill=INK); dd.text((6, 352), hx, font=font('lg-regular.woff2', 24), fill=(110, 110, 110))
                cont.append((sw, 50 + k * 260, 60, 0.3 + k * 0.35, 'rebote'))
            aa = txt('Aa  LA LUMBRE', 96, w - 100, 'lg-black.woff2', INK, max_lines=1)
            cont.append((aa, 50, 520, 1.5, 'izq'))
            out.append(rd_frame(e, d, cont, 'Frame 3 · Paleta y letra'))
        elif t == 'logo':
            out.append(rd_frame(e, d, [(logo_lumbre(640), (w - 640) // 2, 120, 0.3, 'rebote')], 'Frame 4 · Logo final'))
        elif t == 'aplicaciones':
            lg = logo_lumbre(220)
            vaso = Image.new('RGBA', (250, 330), (0, 0, 0, 0)); dv = ImageDraw.Draw(vaso)
            dv.polygon([(0, 0), (250, 0), (215, 330), (35, 330)], fill=CREMA_T, outline=CARB); dv.rectangle((0, 0, 250, 26), fill=ROJO)
            vaso.alpha_composite(lg.resize((170, 170)), (40, 90))
            bolsa = Image.new('RGBA', (280, 380), (0, 0, 0, 0)); db = ImageDraw.Draw(bolsa)
            db.rectangle((0, 60, 279, 379), fill='#C9A27A'); db.arc((80, 0, 200, 120), 180, 360, fill=CARB, width=10)
            bolsa.alpha_composite(lg.resize((200, 200)), (40, 120))
            letrero = Image.new('RGBA', (300, 300), (0, 0, 0, 0)); dl = ImageDraw.Draw(letrero)
            dl.rounded_rectangle((0, 0, 299, 299), 30, fill=CARB); letrero.alpha_composite(lg.resize((240, 240)), (30, 30))
            cont = [(vaso, 40, 300, 0.3, 'rebote'), (bolsa, 330, 220, 0.7, 'rebote'), (letrero, w - 340, 330, 1.1, 'rebote')]
            out.append(rd_frame(e, d, cont, 'Frame 5 · Aplicaciones'))
        else:
            sc = cierre_comun(e, d, LIENZO, INK, (80, 80, 90), boton(avion(INK), 'ESCRÍBEME "MARCA"', 44, PINK, INK, W - 2 * M),
                              boton(G.marcador(WHITE), 'GUÁRDALO', 44, INK, WHITE, W - 2 * M), None)
            sc.fondo = lambda t, b=lienzo(): b; out.append(sc)
    return out


# ---------- 9. RECURSOS ----------
NAVY = '#13172A'


def icono_tipo(tipo, s=180):
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    col = {'LIBRO': PINK, 'PODCAST': CREMA, 'YOUTUBE': WHITE}[tipo]
    d.rounded_rectangle((0, 0, s - 1, s - 1), 30, fill=col)
    c = s / 2
    if tipo == 'LIBRO':
        d.rounded_rectangle((c - 44, c - 50, c + 44, c + 50), 8, fill=INK); d.rectangle((c - 34, c - 40, c + 34, c + 40), fill=PINK)
        d.line((c - 22, c - 18, c + 22, c - 18), fill=INK, width=6); d.line((c - 22, c, c + 22, c), fill=INK, width=6)
    elif tipo == 'PODCAST':
        d.rounded_rectangle((c - 22, c - 52, c + 22, c + 14), 22, fill=INK); d.arc((c - 40, c - 34, c + 40, c + 34), 0, 180, fill=INK, width=8)
        d.line((c, c + 34, c, c + 52), fill=INK, width=8); d.line((c - 22, c + 52, c + 22, c + 52), fill=INK, width=8)
    else:
        d.rounded_rectangle((c - 56, c - 38, c + 56, c + 38), 20, fill=INK); d.polygon([(c - 14, c - 20), (c - 14, c + 20), (c + 22, c)], fill=WHITE)
    return im


def tarjeta_recurso(r, w):
    ic = icono_tipo(r['tipo'])
    tt = txt(r['nombre'], 62, w - 270, 'lg-black.woff2', WHITE, max_lines=2, min_size=40)
    au = txt(f"{r['tipo']} · {r['autor']}", 34, w - 270, 'lg-bold.woff2', PINK, max_lines=1)
    po = txt(r['para'], 42, w - 270, 'lg-regular.woff2', '#C7CBDB', lh=1.25, max_lines=3)
    hh = max(ic.height + 60, tt.height + au.height + po.height + 80)
    im = Image.new('RGBA', (w, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, hh - 1), 34, fill='#1E2340')
    im.alpha_composite(ic, (30, 30)); im.alpha_composite(au, (245, 32)); im.alpha_composite(tt, (245, 34 + au.height))
    im.alpha_composite(po, (245, 44 + au.height + tt.height))
    return im


def librero(t):
    im = Image.new('RGBA', (W, 520), (0, 0, 0, 0)); d = ImageDraw.Draw(im); rnd = random.Random(9); x = M
    cols = [PINK, CREMA, WHITE, '#2E3557', PINK, '#F7B6C8', CREMA, '#3A4270']
    k = 0
    while x < W - M - 40:
        bw = rnd.randrange(46, 90); bh = rnd.randrange(280, 440); col = cols[k % len(cols)]
        lift = max(0, math.sin(t * 2 - k * 0.6)) * 24 if k % 3 == 0 else 0
        d.rounded_rectangle((x, 480 - bh - lift, x + bw, 480 - lift), 8, fill=col)
        d.line((x + 10, 480 - bh + 40 - lift, x + bw - 10, 480 - bh + 40 - lift), fill=INK, width=4)
        x += bw + 8; k += 1
    d.rectangle((M - 20, 480, W - M + 20, 500), fill='#C7CBDB')
    return im


def recursos(data, durs):
    enc = encabezado('PARA APRENDER'); out = []
    for e, d in zip(data['escenas'], durs):
        t = e['tipo']
        if t == 'portada':
            tt = txt(e['titulo'], 110, W - 2 * M, max_lines=4, min_size=70)
            sb = txt(e.get('sub', ''), 46, W - 2 * M, 'lg-medium.woff2', '#C7CBDB', lh=1.25)
            out.append(Esc(d, fondo_plano(NAVY), [(librero, 0, 330, 0.0, 'sube'), (tt, M, 1000, 0.4, 'izq'),
                                                 (sb, M, 1020 + tt.height, 0.8, 'sube')], enc, sub_y=1760))
        elif t == 'tarjetas':
            tt = txt(e['titulo'], 100, W - 2 * M, max_lines=2)
            cs = [tarjeta_recurso(r, W - 2 * M) for r in e['items']]
            y = max(300, (1690 - tt.height - 40 - sum(c.height + 34 for c in cs)) // 2); pz = [(tt, M, y, 0.0, 'izq')]
            y += tt.height + 40; paso = max(0.6, (d - 1.2) / max(1, len(e['items'])))
            for k, c in enumerate(cs):
                pz.append((c, M, y, 0.4 + k * paso, 'izq')); y += c.height + 34
            out.append(Esc(d, fondo_plano(NAVY), pz, enc, sub_y=1760))
        else:
            out.append(cierre_comun(e, d, NAVY, WHITE, '#C7CBDB', boton(icono_comentario(INK), 'RECOMIENDA UNO MÁS', 44, PINK, INK, W - 2 * M),
                                    boton(G.marcador(NAVY), 'GUÁRDALO', 44, WHITE, NAVY, W - 2 * M), enc))
    return out


ESTILOS = {'antes_despues': antes_despues, 'emprende': emprende, 'leccion': leccion, 'checklist': checklist, 'marca_mx': marca_mx,
           'prompt': prompt, 'cobrar': cobrar, 'rediseno': rediseno, 'recursos': recursos}


def escenas(data, durs):
    return ESTILOS[data['estilo']](data, durs)
