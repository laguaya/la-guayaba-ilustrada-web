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


def fondo(nid, cat, out, size=(1080, 1350)):
    """Fondo de marca sin texto (para el carrusel cuando no hay foto)."""
    bg, ink, soft = PAL.get(cat, PAL['Tendencias'])
    w, h = size
    im = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(im)
    rnd = random.Random(nid)
    for _ in range(4):
        r = rnd.randint(int(w * 0.25), int(w * 0.5))
        x, y = rnd.randint(-150, w), rnd.randint(-150, int(h * 0.7))
        d.ellipse((x - r, y - r, x + r, y + r), fill=soft)
    im.save(out, 'JPEG', quality=90)
    return out


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
    # Todo el texto va centrado dentro de una zona segura (60% del ancho, 64% del alto)
    # para que no se corte en ningún recorte del sitio (4:3, 16:9 o casi cuadrado).
    safe_w = int(W * 0.60)
    safe_h = int(H * 0.64)
    for size in range(116, 48, -4):
        ft = font('lg-black.woff2', size)
        lines = wrap(d, title, ft, safe_w)
        lh = size * 1.04
        if len(lines) <= 4 and len(lines) * lh + 110 <= safe_h:
            break
    block = len(lines) * lh + 110
    y = (H - block) / 2
    fl = font('lg-black.woff2', 44)
    d.text((W / 2, y + 22), 'LG.I', font=fl, fill=ink, anchor='mm')
    y += 110
    for ln in lines:
        lw = line_w(d, ln, ft, -size * 0.012)
        draw_line(d, ((W - lw) / 2, y), ln, ft, ink, -size * 0.012)
        y += lh
    out = os.path.join(R, 'assets', 'work', f'nota-{nid}.webp')
    im.save(out, 'WEBP', quality=88)
    print(out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
