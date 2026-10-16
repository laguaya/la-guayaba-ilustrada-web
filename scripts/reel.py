"""Reel vertical (1080x1920, 12 s, 30 fps) de una nota con el branding de Newsbrand.

Uso: python scripts/reel.py datos.json salida.mp4
Usa los mismos datos que el carrusel: img, img2, etiqueta, portada, titulo, resumen, marca.
Escena 1: foto 1 a pantalla completa con zoom lento y el titular.
Escena 2: titular de la nota, foto 2 y resumen.
Escena 3: cierre rosa con "Lee la nota completa · link en la bio".
"""
import functools, json, math, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageOps, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portada
import carrusel as C

W, H, FPS, DUR = 1080, 1920, 30, 12.0
M = 72
PINK, INK, WHITE, WASH = '#FF3674', '#0B0B0B', '#FFFFFF', '#FFF2F6'
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.path.join(R, 'assets', 'audio', 'reel.m4a')


@functools.lru_cache(maxsize=None)
def font(name, size):
    return portada.font(name, size)


C.font = font  # el carrusel también usa la versión en caché


def cl(x, a=0.0, b=1.0): return max(a, min(b, x))
def lin(t, a, b): return cl((t - a) / (b - a))
def eo(x): x = cl(x); return 1 - (1 - x) ** 3
def eio(x): x = cl(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def layer(w, h):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)


def text_block(text, maxw, max_lines, base, big, small, color, it_color=None, hl=True, track=-0.035, lh=1.04):
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    fonts, ls, size = C.fitted(d0, text, maxw, max_lines, base, big, small, track=track)
    hgt = int(len(ls) * size * lh + size * .4)
    im, d = layer(maxw + 40, hgt + 20)
    C.render(d, 20, 6, ls, fonts, size * lh, color, hl_bg=PINK, hl_fg=INK, it_color=it_color, track=track, pad=12)
    return im


def body_block(text, maxw, size, color, lines=6):
    fr = {'n': font('lg-regular.woff2', size), 'pk': font('lg-bold.woff2', size),
          'hl': font('lg-regular.woff2', size), 'it': font('lg-italic.woff2', size)}
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    rl = C.layout(d0, text, fr, maxw)[:lines]
    im, d = layer(maxw + 20, int(len(rl) * size * 1.35 + size))
    C.render(d, 10, 4, rl, fr, size * 1.35, color, pk=PINK)
    return im


def pill(text, f, bg, fg, padx=34, pady=18):
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    w = int(d0.textlength(text, font=f)); a, de = f.getmetrics()
    im, d = layer(w + 2 * padx, a + de + 2 * pady)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=bg)
    d.text((padx, pady + a), text, font=f, fill=fg, anchor='ls')
    return im


def paste(base, im, x, y, op=1.0):
    if op <= 0: return
    if op < 1:
        im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * op)))
    base.alpha_composite(im, (int(x), int(y)))


def kenburns(photo, w, h, z, fy=.4):
    """Recorte con zoom z (>=1) centrado; foto ya ajustada a w*1.15 x h*1.15."""
    pw, ph = photo.size
    cw, ch = pw / z, ph / z
    x0 = (pw - cw) / 2; y0 = (ph - ch) * fy
    return photo.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)


def build(data):
    P1 = ImageOps.fit(Image.open(data['img']).convert('RGB'), (int(W * 1.15), int(H * 1.15)), Image.LANCZOS, centering=(.5, .38))
    img2 = data.get('img2') or data['img']
    CARD_W, CARD_H = W - 2 * M, 860
    P2 = ImageOps.fit(Image.open(img2).convert('RGB'), (int(CARD_W * 1.12), int(CARD_H * 1.12)), Image.LANCZOS, centering=(.5, .45))
    # degradado oscuro de la escena 1
    g = Image.new('L', (1, H))
    for y in range(H):
        t = max(0.0, (y - H * .30) / (H * .45)); g.putpixel((0, y), int(255 * min(1.0, t) ** .85 * .9))
    SH1 = Image.new('RGBA', (W, H), (11, 11, 11, 0)); SH1.putalpha(g.resize((W, H)))
    top = Image.linear_gradient('L').rotate(180).resize((W, 360)).point(lambda v: int(v * .65))
    SH1T = Image.new('RGBA', (W, 360), (11, 11, 11, 0)); SH1T.putalpha(top)
    L = {
        'brand_w': pill('NEWSBRAND · LA GUAYABA ILUSTRADA', font('lg-bold.woff2', 26), (255, 255, 255, 40), WHITE, 26, 14),
        'brand_k': pill('NEWSBRAND · LA GUAYABA ILUSTRADA', font('lg-bold.woff2', 26), INK, WHITE, 26, 14),
        'tag': pill(data.get('etiqueta', 'NOTICIAS').upper(), font('lg-black.woff2', 34), PINK, INK, 30, 16),
        'portada': text_block(data['portada'], W - 2 * M - 110, 5, 'lg-black.woff2', 118, 66, WHITE),
        'titulo': text_block(data['titulo'], W - 2 * M, 3, 'lg-black.woff2', 96, 58, INK, it_color=PINK),
        'resumen': body_block(data.get('resumen', ''), W - 2 * M - 90, 40, INK, 5),
        'marca': pill((data.get('marca') or '').upper(), font('lg-black.woff2', 32), PINK, INK, 24, 14) if data.get('marca') else None,
        'cta': text_block('¿Quieres saber _más_ de esta nota?', W - 2 * M, 3, 'lg-black.woff2', 128, 80, INK, it_color=WHITE),
        'cta2': body_block('Léela completa en guayabailustrada.com.mx', W - 2 * M, 44, INK, 2),
        'bio': pill('LINK EN LA BIO  →', font('lg-black.woff2', 46), INK, PINK, 54, 30),
        'firma': text_block('LG.I', 400, 1, 'lg-bold.woff2', 110, 100, INK, track=-0.05),
        'sigue': pill('@lgi.newsbrand', font('lg-bold.woff2', 36), WHITE, INK, 30, 16),
    }
    # tarjeta de foto con esquinas redondeadas
    MASK = Image.new('L', (CARD_W, CARD_H), 0); ImageDraw.Draw(MASK).rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), 34, fill=255)
    WASHBG = Image.new('RGBA', (W, H), WASH)
    glow = Image.new('L', (W, H), 0); ImageDraw.Draw(glow).ellipse((-300, -700, W + 300, 700), fill=150)
    WASHBG.paste(Image.new('RGBA', (W, H), '#FFC2D4'), (0, 0), glow.filter(ImageFilter.GaussianBlur(180)))
    return P1, P2, SH1, SH1T, L, MASK, WASHBG, CARD_W, CARD_H


def scene1(t, A):
    P1, P2, SH1, SH1T, L, *_ = A
    im = kenburns(P1, W, H, 1.0 + .13 * eio(t / 4.4)).convert('RGBA')
    im.alpha_composite(SH1); im.alpha_composite(SH1T)
    paste(im, L['brand_w'], M, 150, eo(lin(t, .1, .5)))
    ph = L['portada']; y = 1430 - ph.height
    a = eo(lin(t, .55, 1.15))
    paste(im, L['tag'], M, y - 90 + (1 - eo(lin(t, .35, .8))) * 40, eo(lin(t, .35, .8)))
    paste(im, ph, M - 20, y + (1 - a) * 80, a)
    return im


def scene2(t, A):
    P1, P2, SH1, SH1T, L, MASK, WASHBG, CW, CH = A
    im = WASHBG.copy()
    paste(im, L['brand_k'], M, 150, 1)
    ti = L['titulo']; a = eo(lin(t, .15, .75))
    paste(im, ti, M - 20, 250 + (1 - a) * 60, a)
    cy = 250 + ti.height + 40
    k = eo(lin(t, .35, 1.0))
    card = kenburns(P2, CW, CH, 1.0 + .1 * (t / 4.6)).convert('RGBA'); card.putalpha(MASK)
    sc = .92 + .08 * k
    if sc != 1:
        card = card.resize((int(CW * sc), int(CH * sc)), Image.BILINEAR)
    paste(im, card, (W - card.width) / 2, cy + (CH - card.height) / 2 + (1 - k) * 60, k)
    if L['marca']:
        b = eo(lin(t, 1.0, 1.4)); paste(im, L['marca'], M + 24, cy + CH - L['marca'].height - 24, b)
    r = eo(lin(t, 1.3, 1.9))
    paste(im, L['resumen'], M - 10, cy + CH + 40 + (1 - r) * 40, r)
    return im


def scene3(t, A):
    L = A[4]
    im = Image.new('RGBA', (W, H), PINK)
    cta = L['cta']; a = eo(lin(t, .2, .8))
    y = 520
    paste(im, cta, M - 20, y + (1 - a) * 70, a)
    y += cta.height + 30
    b = eo(lin(t, .55, 1.1)); paste(im, L['cta2'], M - 10, y + (1 - b) * 40, b)
    y += L['cta2'].height + 70
    c = eo(lin(t, .85, 1.3)); pulse = 1 + .03 * math.sin(max(0, t - 1.3) * 6)
    bio = L['bio']
    if c * pulse != 1:
        bio = bio.resize((max(1, int(bio.width * c * pulse)), max(1, int(bio.height * c * pulse))), Image.BILINEAR)
    paste(im, bio, M + (L['bio'].width - bio.width) / 2, y + (L['bio'].height - bio.height) / 2, min(1, c))
    paste(im, L['firma'], M - 20, 1440, eo(lin(t, 1.1, 1.6)))
    paste(im, L['sigue'], W - M - L['sigue'].width, 1470, eo(lin(t, 1.3, 1.8)))
    return im


def frame(t, A):
    T1, T2 = 4.2, 8.6          # cambios de escena (empuje hacia arriba de 0.35 s)
    d = .35
    if t < T1 - d:
        return scene1(t, A)
    if t < T1:
        k = eio((t - (T1 - d)) / d); a = scene1(t, A); b = scene2(.5, A)
        im = Image.new('RGBA', (W, H)); im.paste(a, (0, -int(k * H))); im.paste(b, (0, H - int(k * H))); return im
    if t < T2 - d:
        return scene2(t - T1, A)
    if t < T2:
        k = eio((t - (T2 - d)) / d); a = scene2(t - T1, A); b = scene3(.4, A)
        im = Image.new('RGBA', (W, H)); im.paste(a, (0, -int(k * H))); im.paste(b, (0, H - int(k * H))); return im
    return scene3(t - T2, A)


def make(data, out):
    A = build(data)
    tmp = tempfile.mkdtemp()
    n = int(DUR * FPS)
    for i in range(n):
        frame(i / FPS, A).convert('RGB').save(f'{tmp}/{i:04d}.jpg', quality=90)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/%04d.jpg']
    if os.path.exists(MUSIC):
        cmd += ['-i', MUSIC, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', str(FPS),
            '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    import shutil; shutil.rmtree(tmp, ignore_errors=True)
    return out


if __name__ == '__main__':
    make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2])
