"""Genera la portada de una nota con el estilo de La Guayaba Ilustrada.

Uso: python scripts/portada.py <id> "<categoría>" "<título>"
Crea assets/work/nota-<id>.webp (1600x1067).
"""
import io, os, sys, random
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1600, 1067
PAL = {
    'Noticias': ('#FF9D00', '#000000', '#FFE3B8'),
    'Tendencias': ('#FF3674', '#000000', '#FFD0DE'),
    'Inspiración': ('#FFA4BE', '#000000', '#FFE6EE'),
}


def font(name, size):
    t = TTFont(os.path.join(R, 'assets', name))
    t.flavor = None
    b = io.BytesIO(); t.save(b); b.seek(0)
    return ImageFont.truetype(b, size)


PUNCT = ',.'


def line_w(d, text, f, track):
    w = 0
    for ch in text:
        if ch in PUNCT:
            w -= f.size * 0.07
        w += d.textlength(ch, font=f) + track
    return w - track


def draw_line(d, xy, text, f, fill, track):
    x, y = xy
    for ch in text:
        if ch in PUNCT:
            x -= f.size * 0.07
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + track


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if line_w(d, test, f, -f.size * 0.012) <= maxw:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def main(nid, cat, title):
    bg, ink, soft = PAL.get(cat, PAL['Tendencias'])
    im = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(im)
    rnd = random.Random(nid)
    # formas suaves de fondo
    for _ in range(3):
        r = rnd.randint(260, 520)
        x, y = rnd.randint(-150, W), rnd.randint(-150, H)
        d.ellipse((x - r, y - r, x + r, y + r), fill=soft)
    pad = 110
    # etiqueta de categoría
    fc = font('lg-bold.woff2', 40)
    tw = d.textlength(cat.upper(), font=fc)
    d.rounded_rectangle((pad, pad, pad + tw + 64, pad + 74), radius=37, fill=ink)
    d.text((pad + 32, pad + 39), cat.upper(), font=fc, fill=bg, anchor='lm')
    # título que quepa en el área
    for size in range(124, 60, -4):
        ft = font('lg-black.woff2', size)
        lines = wrap(d, title, ft, W - pad * 2)
        lh = size * 1.02
        if len(lines) * lh <= H - pad * 2 - 200:
            break
    y = H - pad - 90 - len(lines) * lh
    for ln in lines:
        draw_line(d, (pad, y), ln, ft, ink, -size * 0.012)
        y += lh
    # firma
    fs = font('lg-bold.woff2', 34)
    d.text((pad, H - pad + 6), 'La Guayaba Ilustrada', font=fs, fill=ink, anchor='ls')
    d.text((W - pad, H - pad + 6), 'LG.I', font=font('lg-black.woff2', 46), fill=ink, anchor='rs')
    out = os.path.join(R, 'assets', 'work', f'nota-{nid}.webp')
    im.save(out, 'WEBP', quality=88)
    print(out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
