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


if __name__ == '__main__':
    {'b': estilo_b, 'c': estilo_c}[sys.argv[1]](*sys.argv[2:7])
