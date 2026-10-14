"""Plantilla de Instagram (1080x1350) de La Guayaba Ilustrada.

Uso:
  python scripts/instagram.py <imagen> "<categoría>" "<encabezado>" "<resumen>" <salida.jpg>
"""
import os, sys
from PIL import Image, ImageDraw, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portada import font

W, H = 1080, 1350
PINK, INK, WHITE, WASH = '#FF3674', '#000000', '#FFFFFF', '#FFEDF2'
M = 54            # margen exterior
PH = 640          # alto de la foto


PUNCT = ',.'


def tw(d, text, f, track):
    w = 0
    for ch in text:
        if ch == '*':
            continue
        if ch in PUNCT:
            w -= f.size * 0.07
        w += d.textlength(ch, font=f) + track + (f.size * 0.06 if ch == ' ' else 0)
    return w - track


def draw(d, xy, text, f, fill, track, hi=WHITE):
    """Dibuja texto; lo que va entre *asteriscos* sale resaltado en blanco."""
    x, y = xy
    on = False
    for ch in text:
        if ch == '*':
            on = not on
            continue
        if ch in PUNCT:
            x -= f.size * 0.07
        d.text((x, y), ch, font=f, fill=hi if on else fill)
        x += d.textlength(ch, font=f) + track + (f.size * 0.06 if ch == ' ' else 0)
    return on


def wrap(d, text, f, maxw, track):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if tw(d, t, f, track) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded(im, r):
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *im.size), radius=r, fill=255)
    out = Image.new('RGBA', im.size); out.paste(im, (0, 0), mask)
    return out


def make(img, cat, title, summary, out):
    can = Image.new('RGB', (W, H), PINK)
    d = ImageDraw.Draw(can)

    # foto de la nota
    pw = W - 2 * M
    ph = ImageOps.fit(Image.open(img).convert('RGB'), (pw, PH), Image.LANCZOS, centering=(0.5, 0.45))
    can.paste(rounded(ph, 38), (M, M), rounded(ph, 38))

    # etiqueta de categoría sobre la foto
    fc = font('lg-bold.woff2', 30)
    tw = d.textlength(cat.upper(), font=fc)
    x0, y0 = M + 28, M + 28
    d.rounded_rectangle((x0, y0, x0 + tw + 48, y0 + 58), radius=29, fill=INK)
    d.text((x0 + 24, y0 + 31), cat.upper(), font=fc, fill=WHITE, anchor='lm')

    # logo sobre la foto
    fl = font('lg-black.woff2', 40)
    lw = d.textlength('LG.I', font=fl)
    d.rounded_rectangle((W - M - 28 - lw - 40, y0, W - M - 28, y0 + 58), radius=29, fill=PINK)
    d.text((W - M - 28 - 20, y0 + 31), 'LG.I', font=fl, fill=INK, anchor='rm')

    # zona de texto
    top = M + PH + 46
    cta_h = 104
    bottom = H - M - cta_h - 34
    maxw = W - 2 * M

    # resumen (máximo 3 líneas)
    fr = font('lg-medium.woff2', 32)
    rl = wrap(d, summary, fr, maxw, 0)[:3]
    rlh = 41
    r_h = len(rl) * rlh

    # encabezado: el más grande que quepa
    for size in range(104, 46, -2):
        ft = font('lg-black.woff2', size)
        tr = -size * 0.02
        tl = wrap(d, title.upper(), ft, maxw, tr)
        lh = size * 0.98
        if len(tl) <= 4 and top + len(tl) * lh + 26 + r_h <= bottom:
            break
    block = len(tl) * lh + 26 + r_h
    y = top + max(0, (bottom - top - block) / 2)
    on = False
    for ln in tl:
        draw(d, (M, y), ('*' if on else '') + ln, ft, INK, tr)
        on = (ln.count('*') + (1 if on else 0)) % 2 == 1
        y += lh
    y += 26
    for ln in rl:
        draw(d, (M, y), ln, fr, INK, 0)
        y += rlh

    # llamado a la acción
    cy = H - M - cta_h
    d.rounded_rectangle((M, cy, W - M, cy + cta_h), radius=cta_h // 2, fill=INK)
    f1 = font('lg-bold.woff2', 30)
    f2 = font('lg-regular.woff2', 24)
    d.text((M + 52, cy + 38), '¿Quieres saber más?', font=f1, fill=WHITE, anchor='lm')
    d.text((M + 52, cy + 72), 'Lee la nota completa en nuestra página · link en bio', font=f2, fill=WASH, anchor='lm')
    # flecha
    ax, ay, r = W - M - 52, cy + cta_h // 2, 30
    d.ellipse((ax - r, ay - r, ax + r, ay + r), fill=PINK)
    d.line((ax - 11, ay, ax + 11, ay), fill=INK, width=5)
    d.line((ax + 1, ay - 10, ax + 12, ay), fill=INK, width=5)
    d.line((ax + 1, ay + 10, ax + 12, ay), fill=INK, width=5)

    can.save(out, 'JPEG', quality=92, optimize=True)
    print(out)


if __name__ == '__main__':
    make(*sys.argv[1:6])
