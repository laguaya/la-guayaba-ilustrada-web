"""Variantes de la plantilla de Instagram (1080x1350).

Uso: python scripts/ig_estilos.py <b|c> <imagen> "<categoría>" "<encabezado>" "<resumen>" <salida.jpg>
"""
import os, sys
from PIL import Image, ImageDraw, ImageOps, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portada import font
from instagram import draw, wrap, rounded, W, H, PINK, INK, WHITE

M = 60


def fit_title(d, title, maxw, max_lines, max_h, big=118, small=50):
    for size in range(big, small, -2):
        ft = font('lg-black.woff2', size)
        tr = -size * 0.025
        tl = wrap(d, title.upper(), ft, maxw, tr)
        lh = size * 0.95
        if len(tl) <= max_lines and len(tl) * lh <= max_h:
            return ft, tr, tl, lh
    return ft, tr, tl, lh


def draw_title(d, x, y, tl, ft, tr, lh, fill, hi):
    on = False
    for ln in tl:
        draw(d, (x, y), ('*' if on else '') + ln, ft, fill, tr, hi=hi)
        on = (ln.count('*') + (1 if on else 0)) % 2 == 1
        y += lh
    return y


def pill(d, x, y, text, f, bg, fg, h=58, padx=24, anchor_right=False):
    w = d.textlength(text, font=f) + padx * 2
    if anchor_right:
        x = x - w
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg)
    d.text((x + padx, y + h / 2 + 2), text, font=f, fill=fg, anchor='lm')
    return w


def estilo_b(img, cat, title, summary, out):
    """Foto a sangre completa con degradado y titular blanco, como portada de revista."""
    can = ImageOps.fit(Image.open(img).convert('RGB'), (W, H), Image.LANCZOS, centering=(0.5, 0.35))
    # degradado negro desde la mitad hacia abajo
    grad = Image.new('L', (1, H))
    for y in range(H):
        t = max(0, (y - H * 0.22) / (H * 0.40))
        grad.putpixel((0, y), int(255 * min(1, t) ** 0.9 * 0.93))
    grad = grad.resize((W, H))
    can.paste(Image.new('RGB', (W, H), '#000000'), (0, 0), grad)
    top_shade = Image.linear_gradient('L').rotate(180).resize((W, 260)).point(lambda v: int(v * 0.35))
    can.paste(Image.new('RGB', (W, 260), '#000000'), (0, 0), top_shade)
    d = ImageDraw.Draw(can)

    fb = font('lg-bold.woff2', 28)
    w = pill(d, M, M, 'LG.I', font('lg-black.woff2', 34), PINK, INK)
    pill(d, M + w + 12, M, cat.upper(), fb, WHITE, INK)
    d.text((W - M, M + 31), 'La Guayaba Ilustrada', font=font('lg-medium.woff2', 26), fill=WHITE, anchor='rm')

    maxw = W - 2 * M
    fr = font('lg-regular.woff2', 33)
    rl = wrap(d, summary, fr, maxw, 0)[:3]
    rlh = 43
    cta_y = H - M - 40
    r_top = cta_y - 46 - len(rl) * rlh
    ft, tr, tl, lh = fit_title(d, title, maxw, 5, r_top - 28 - H * 0.42)
    y = r_top - 28 - len(tl) * lh
    draw_title(d, M, y, tl, ft, tr, lh, WHITE, PINK)
    y = r_top
    for ln in rl:
        draw(d, (M, y), ln, fr, '#E9E9E9', 0)
        y += rlh
    # llamado a la acción
    d.line((M, cta_y - 18, W - M, cta_y - 18), fill=(255, 255, 255, 60), width=2)
    f1 = font('lg-bold.woff2', 30)
    d.text((M, cta_y + 20), '¿Quieres saber más? Lee la nota completa', font=f1, fill=PINK, anchor='lm')
    d.text((W - M, cta_y + 20), 'Link en bio  →', font=font('lg-bold.woff2', 30), fill=WHITE, anchor='rm')
    can.save(out, 'JPEG', quality=92, optimize=True)
    print(out)


def estilo_c(img, cat, title, summary, out):
    """Fondo negro, titular gigante arriba, foto al centro y barra rosa."""
    can = Image.new('RGB', (W, H), INK)
    d = ImageDraw.Draw(can)
    fb = font('lg-bold.woff2', 28)
    pill(d, M, M, cat.upper(), fb, PINK, INK)
    d.text((W - M, M + 31), 'LG.I', font=font('lg-black.woff2', 44), fill=WHITE, anchor='rm')

    maxw = W - 2 * M
    ft, tr, tl, lh = fit_title(d, title, maxw, 4, 400, big=112)
    y = M + 58 + 40
    y = draw_title(d, M, y, tl, ft, tr, lh, WHITE, PINK)

    cta_h = 100
    cta_y = H - M - cta_h
    fr = font('lg-regular.woff2', 31)
    rl = wrap(d, summary, fr, maxw, 0)[:2]
    rlh = 40
    r_y = cta_y - 34 - len(rl) * rlh
    ph_top = y + 30
    ph_h = r_y - 34 - ph_top
    ph = ImageOps.fit(Image.open(img).convert('RGB'), (W - 2 * M, int(ph_h)), Image.LANCZOS, centering=(0.5, 0.45))
    r = rounded(ph, 34)
    can.paste(r, (M, int(ph_top)), r)
    # sello rosa sobre la foto
    s = 150
    st = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.ellipse((0, 0, s - 1, s - 1), fill=PINK)
    sd.text((s / 2, s / 2 - 14), 'LEE', font=font('lg-black.woff2', 36), fill=INK, anchor='mm')
    sd.text((s / 2, s / 2 + 22), 'MÁS', font=font('lg-black.woff2', 36), fill=INK, anchor='mm')
    st = st.rotate(12, resample=Image.BICUBIC)
    can.paste(st, (W - M - s + 20, int(ph_top + ph_h - s + 30)), st)

    y = r_y
    for ln in rl:
        draw(d, (M, y), ln, fr, '#D9D9D9', 0)
        y += rlh
    d.rounded_rectangle((M, cta_y, W - M, cta_y + cta_h), radius=cta_h // 2, fill=PINK)
    d.text((M + 48, cta_y + cta_h / 2 + 2), 'Nota completa en nuestra web', font=font('lg-black.woff2', 34), fill=INK, anchor='lm')
    d.text((W - M - 48, cta_y + cta_h / 2 + 2), 'Link en bio →', font=font('lg-bold.woff2', 28), fill=INK, anchor='rm')
    can.save(out, 'JPEG', quality=92, optimize=True)
    print(out)


if __name__ == '__main__' and sys.argv[1] in ('b', 'c'):
    {'b': estilo_b, 'c': estilo_c}[sys.argv[1]](*sys.argv[2:7])


CAT_COLORS = {'Noticias': '#FF9D00', 'Tendencias': '#FF3674', 'Inspiración': '#FFA4BE'}


def tag(d, x, y, text, f, bg, fg, h=46, padx=16):
    w = d.textlength(text, font=f) + padx * 2
    d.rectangle((x, y, x + w, y + h), fill=bg)
    d.text((x + padx, y + h / 2 + 2), text, font=f, fill=fg, anchor='lm')
    return w


def estilo_d(img, cat, title, summary, out):
    """Foto arriba y bloque de color abajo, con etiquetas y sello (ref. RJ+ Cultura)."""
    col = CAT_COLORS.get(cat, PINK)
    PHH = 690
    can = Image.new('RGB', (W, H), col)
    can.paste(ImageOps.fit(Image.open(img).convert('RGB'), (W, PHH), Image.LANCZOS, centering=(0.5, 0.4)), (0, 0))
    d = ImageDraw.Draw(can)
    # sello LG.I en la unión
    s = 150
    d.rectangle((W - M - s, PHH - s // 2, W - M, PHH + s // 2), fill=INK)
    d.text((W - M - s / 2, PHH + 2), 'LG.I', font=font('lg-black.woff2', 46), fill=col, anchor='mm')
    # etiquetas
    ft_ = font('lg-bold.woff2', 24)
    w = tag(d, M, PHH - 46, cat.upper(), ft_, INK, col)
    tag(d, M + w, PHH - 46, 'LA GUAYABA ILUSTRADA', ft_, WHITE, INK)
    maxw = W - 2 * M - s - 20
    fr = font('lg-medium.woff2', 30)
    ft, tr, tl, lh = fit_title(d, title.replace('*', ''), maxw, 4, 330, big=88, small=46)
    y = PHH + 52
    y = draw_title(d, M, y, tl, ft, tr, lh, INK, INK)
    rl = wrap(d, summary, fr, W - 2 * M, 0)[:2]
    y += 12
    for ln in rl:
        draw(d, (M, y), ln, fr, INK, 0); y += 38
    # pie
    py = H - M - 30
    d.line((M, py - 26, W - M, py - 26), fill=INK, width=3)
    fb = font('lg-bold.woff2', 28)
    d.text((M, py + 4), 'NOTA COMPLETA EN NUESTRA WEB', font=fb, fill=INK, anchor='lm')
    d.text((W - M, py + 4), 'LINK EN BIO →', font=fb, fill=INK, anchor='rm')
    can.save(out, 'JPEG', quality=92, optimize=True)
    print(out)


def highlight_title(d, x, y, text, f, maxw, lh, ink, hl, pad=12):
    """Titular en minúsculas con marcatextos detrás de las palabras entre *asteriscos*."""
    words = []
    on = False
    for raw in text.split():
        st = raw.startswith('*'); en = raw.endswith('*')
        if st: on = True
        words.append((raw.strip('*'), on))
        if en: on = False
    sp = d.textlength(' ', font=f)
    lines, cur, cw = [], [], 0
    for wd, h in words:
        ww = d.textlength(wd, font=f)
        if cur and cw + sp + ww > maxw:
            lines.append(cur); cur, cw = [], 0
        cur.append((wd, h, ww)); cw += (sp if len(cur) > 1 else 0) + ww
    if cur: lines.append(cur)
    asc = f.size * 0.78
    for ln in lines:
        cx = x
        i = 0
        while i < len(ln):
            wd, h, ww = ln[i]
            if h:
                j = i; run = 0
                while j < len(ln) and ln[j][1]:
                    run += ln[j][2] + (sp if j > i else 0); j += 1
                d.rounded_rectangle((cx - pad, y + f.size * 0.08, cx + run + pad, y + f.size * 1.08), radius=12, fill=hl)
                for k in range(i, j):
                    d.text((cx, y), ln[k][0], font=f, fill=ink); cx += ln[k][2] + sp
                i = j
            else:
                d.text((cx, y), wd, font=f, fill=ink); cx += ww + sp; i += 1
        y += lh
    return y, len(lines)


def tab_mask(w, h, r=34, tw=0.42, th=64):
    """Máscara con forma de carpeta: esquina superior derecha recortada en escalón."""
    m = Image.new('L', (w, h), 0)
    md = ImageDraw.Draw(m)
    md.rounded_rectangle((0, th, w, h), radius=r, fill=255)
    md.rounded_rectangle((0, 0, int(w * (1 - tw)), h), radius=r, fill=255)
    return m


def estilo_e(img, cat, title, summary, out):
    """Fondo claro, titular con marcatextos y foto en forma de carpeta (ref. Zelma / Impact)."""
    BG = '#FFF4F7'
    can = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(can)
    # encabezado
    d.text((M, M + 20), 'LG.I', font=font('lg-black.woff2', 40), fill=INK, anchor='lm')
    d.text((M + 104, M + 20), 'la guayaba ilustrada', font=font('lg-medium.woff2', 26), fill=INK, anchor='lm')
    pill(d, W - M, M - 9, cat, font('lg-bold.woff2', 26), CAT_COLORS.get(cat, PINK), INK, anchor_right=True)
    # titular con marcatextos (tamaño que quepa en 4 líneas)
    t = title[0].upper() + title[1:].lower() if title.isupper() else title
    for size in range(96, 50, -2):
        f = font('lg-medium.woff2', size)
        tmp = Image.new('RGB', (10, 10)); td = ImageDraw.Draw(tmp)
        _, n = highlight_title(td, 0, 0, t, f, W - 2 * M - 30, size * 1.12, INK, PINK)
        if n <= 4:
            break
    ty = M + 90
    y, _ = highlight_title(d, M + 12, ty, t, f, W - 2 * M - 30, size * 1.12, INK, PINK)
    # foto en carpeta
    foot = 150
    ph_top = int(y + 34)
    ph_h = H - M - foot - ph_top
    ph = ImageOps.fit(Image.open(img).convert('RGB'), (W - 2 * M, ph_h), Image.LANCZOS, centering=(0.5, 0.45))
    can.paste(ph, (M, ph_top), tab_mask(W - 2 * M, ph_h))
    # pie
    fy = H - M - foot + 34
    fr = font('lg-regular.woff2', 27)
    rl = wrap(d, summary, fr, 600, 0)[:3]
    for i, ln in enumerate(rl):
        draw(d, (M, fy + i * 34), ln, fr, INK, 0)
    d.text((W - M, fy + 18), 'Lee la nota completa', font=font('lg-bold.woff2', 28), fill=INK, anchor='rm')
    d.text((W - M, fy + 58), 'en nuestra web · link en bio ↓', font=font('lg-regular.woff2', 24), fill=INK, anchor='rm')
    can.save(out, 'JPEG', quality=92, optimize=True)
    print(out)


if __name__ == '__main__' and sys.argv[1] in ('d', 'e'):
    {'d': estilo_d, 'e': estilo_e}[sys.argv[1]](*sys.argv[2:7])
