"""Reel vertical (1080x1920, 30 fps, 15 a 40 s) de una nota, con branding de Newsbrand.

Uso: python scripts/reel.py datos.json salida.mp4
datos: img, img2, fotos (lista opcional), etiqueta, portada, titulo, marca, guion (texto de la voz),
       src (URL de la nota, para sacar clips del video de la campaña) o video (ruta local a un MP4).

Estructura:
  1) Gancho (0 a ~3 s): foto o clip de la campaña con el titular grande y el marcatextos rosa.
  2) Cuerpo: clips reales del video de la campaña y fotos de la nota, con subtítulos tipo karaoke
     sincronizados con la voz en off (la palabra que se dice va marcada en rosa).
  3) Cierre rosa (3 s): "¿Quieres saber más de esta nota?" + link en la bio.
Audio: voz con IA (scripts/voz.py) + música de fondo bajita.
"""
import functools, glob, json, math, os, re, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portada
import carrusel as C

W, H, FPS = 1080, 1920, 30
M = 72
PINK, INK, WHITE, WASH = '#FF3674', '#0B0B0B', '#FFFFFF', '#FFF2F6'
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.path.join(R, 'assets', 'audio', 'reel.m4a')
GANCHO, CIERRE, INICIO_VOZ, SEG = 3.2, 3.0, 0.35, 2.6


@functools.lru_cache(maxsize=None)
def font(name, size):
    return portada.font(name, size)


C.font = font


def cl(x, a=0.0, b=1.0): return max(a, min(b, x))
def lin(t, a, b): return cl((t - a) / (b - a))
def eo(x): x = cl(x); return 1 - (1 - x) ** 3
def eio(x): x = cl(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def layer(w, h):
    im = Image.new('RGBA', (int(w), int(h)), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)


def paste(base, im, x, y, op=1.0):
    if op <= 0 or im is None:
        return
    if op < 1:
        im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * op)))
    base.alpha_composite(im, (int(x), int(y)))


def pill(text, f, bg, fg, padx=34, pady=18):
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    w = int(d0.textlength(text, font=f)); a, de = f.getmetrics()
    im, d = layer(w + 2 * padx, a + de + 2 * pady)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), im.height // 2, fill=bg)
    d.text((padx, pady + a), text, font=f, fill=fg, anchor='ls')
    return im


def text_block(text, maxw, max_lines, base, big, small, color, it_color=None, track=-0.035, lh=1.04):
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    fonts, ls, size = C.fitted(d0, text, maxw, max_lines, base, big, small, track=track)
    im, d = layer(maxw + 40, int(len(ls) * size * lh + size * .4) + 20)
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


# ---------------------------------------------------------------- fondos (fotos y clips)
def vertical(im, foco=(0.5, 0.45), zoom=1.0):
    """Pone cualquier imagen en 1080x1920. Si llenar la pantalla la ampliaría demasiado (se vería borrosa),
    la deja completa al centro sobre un fondo desenfocado de ella misma."""
    import encuadre
    im = im.convert('RGB')
    llenar = max(W / im.width, H / im.height)
    if llenar <= 1.75:
        return encuadre.recorte(im, (W, H), foco, zoom=zoom, destino=(0.5, 0.42))
    fondo = im.resize((54, 96)).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
    fondo = Image.blend(fondo, Image.new('RGB', (W, H), INK), 0.35)
    bw = W
    bh = int(im.height * bw / im.width)
    if bh > H * 0.62:
        bh = int(H * 0.62); bw = int(im.width * bh / im.height)
    banda = encuadre.recorte(im, (bw, bh), foco, zoom=zoom)
    fondo.paste(banda, ((W - bw) // 2, int(H * 0.40 - bh / 2)))
    return fondo


def clips_de_video(ruta, tmp, n=6):
    """Corta tramos de SEG segundos del video de la campaña que no traigan letras encima."""
    import fuentes, encuadre
    try:
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta],
                                   capture_output=True, text=True, timeout=60).stdout.strip() or 0)
    except Exception:
        return []
    if dur < SEG * 2:
        return []
    out, k = [], 0
    pruebas = 14
    for i in range(pruebas):
        if len(out) >= n:
            break
        t0 = dur * (0.06 + 0.84 * i / (pruebas - 1))
        if t0 + SEG > dur - 0.3:
            continue
        mid = f'{tmp}/mid{i}.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t0 + SEG / 2:.2f}', '-i', ruta, '-frames:v', '1', mid],
                       capture_output=True, timeout=60)
        if not os.path.exists(mid):
            continue
        im = Image.open(mid).convert('RGB')
        g = im.convert('L').resize((64, 36))
        brillo = sum(g.getdata()) / (64 * 36)
        if brillo < 30 or fuentes.es_captura_o_grafico(im) or fuentes.palabras(im) >= 2:
            continue
        carpeta = f'{tmp}/clip{k}'; os.makedirs(carpeta)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t0:.2f}', '-t', f'{SEG + 0.1:.2f}', '-i', ruta,
                        '-vf', f'fps={FPS}', '-q:v', '3', f'{carpeta}/%04d.jpg'], capture_output=True, timeout=120)
        cuadros = sorted(glob.glob(f'{carpeta}/*.jpg'))
        if len(cuadros) >= SEG * FPS * 0.8:
            out.append({'tipo': 'clip', 'cuadros': cuadros, 'foco': encuadre.foco(im)})
            k += 1
    return out


def bajar_video(data, tmp):
    if data.get('video') and os.path.exists(data['video']):
        return data['video']
    if not data.get('src'):
        return None
    try:
        import fuentes, requests
        for u in fuentes.mp4s_de_pagina(data['src']):
            r = requests.get(u, headers=fuentes.UA, timeout=90, stream=True)
            if r.status_code != 200:
                continue
            ruta = f'{tmp}/campana.mp4'; tam = 0
            with open(ruta, 'wb') as f:
                for ch in r.iter_content(1 << 16):
                    tam += len(ch)
                    if tam > 150 * 1024 * 1024:
                        break
                    f.write(ch)
            return ruta
    except Exception as e:
        print('Video de campaña:', e, file=sys.stderr)
    return None


def fondos(data, tmp):
    import encuadre
    fotos = []
    for p in [data.get('img'), data.get('img2')] + list(data.get('fotos') or []):
        if p and os.path.exists(p) and p not in fotos:
            fotos.append(p)
    fotos = [{'tipo': 'foto', 'im': Image.open(p).convert('RGB'), 'foco': encuadre.foco(p)} for p in fotos]
    vid = bajar_video(data, tmp)
    clips = clips_de_video(vid, tmp) if vid else []
    # se intercalan: clip, foto, clip, foto... (el gancho abre con la mejor foto o el primer clip)
    orden = []
    while clips or fotos:
        if clips: orden.append(clips.pop(0))
        if fotos: orden.append(fotos.pop(0))
    return orden


def cuadro_fondo(f, t):
    """Fondo vertical del elemento f en el segundo t de su tramo (0..SEG)."""
    if f['tipo'] == 'clip':
        cs = f['cuadros']
        im = Image.open(cs[min(len(cs) - 1, int(t * FPS))])
        return vertical(im, f['foco'])
    return vertical(f['im'], f['foco'], zoom=1.0 + 0.07 * cl(t / SEG))


# ---------------------------------------------------------------- subtítulos karaoke
def grupos(palabras):
    """Junta las palabras de la voz en bloques cortos (máx. 3 palabras o 20 letras) para los subtítulos."""
    out, cur = [], []
    for i, p in enumerate(palabras):
        if cur and p[0] - cur[-1][1] > 0.22:          # pausa de la voz = fin de frase
            out.append(cur); cur = []
        cur.append(p)
        txt = ' '.join(x[2] for x in cur)
        if len(cur) >= 3 or len(txt) >= 20 or p[2][-1:] in '.,;:?!':
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def subtitulo(grupo, t):
    """Capa con el bloque de subtítulo; la palabra que suena va sobre una franja rosa."""
    f = font('lg-black.woff2', 78)
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    sp = d0.textlength(' ', font=f)
    ws = [w for _, _, w in grupo]
    anchos = [d0.textlength(w, font=f) for w in ws]
    total = sum(anchos) + sp * (len(ws) - 1)
    a, de = f.getmetrics()
    im, d = layer(total + 80, a + de + 50)
    x = 40
    for (ini, fin, w), aw in zip(grupo, anchos):
        activa = ini <= t < max(fin, ini + 0.12) or (t >= fin and w is ws[-1] and t < fin + 0.4)
        if activa:
            d.rounded_rectangle((x - 12, 14, x + aw + 12, 14 + a + de + 8), radius=10, fill=PINK)
            d.text((x, 18 + a), w, font=f, fill=INK, anchor='ls')
        else:
            d.text((x, 18 + a), w, font=f, fill=WHITE, anchor='ls', stroke_width=5, stroke_fill=INK)
        x += aw + sp
    return im


# ---------------------------------------------------------------- escenas
def preparar(data):
    g = Image.new('L', (1, H))
    for y in range(H):
        t = max(0.0, (y - H * .45) / (H * .45)); g.putpixel((0, y), int(255 * min(1.0, t) ** .9 * .85))
    abajo = Image.new('RGBA', (W, H), (11, 11, 11, 0)); abajo.putalpha(g.resize((W, H)))
    top = Image.linear_gradient('L').rotate(180).resize((W, 380)).point(lambda v: int(v * .6))
    arriba = Image.new('RGBA', (W, 380), (11, 11, 11, 0)); arriba.putalpha(top)
    L = {
        'abajo': abajo, 'arriba': arriba,
        'brand': pill('NEWSBRAND · LA GUAYABA ILUSTRADA', font('lg-bold.woff2', 26), (255, 255, 255, 46), WHITE, 26, 14),
        'tag': pill((data.get('etiqueta') or 'NOTICIAS').upper(), font('lg-black.woff2', 34), PINK, INK, 30, 16),
        'marca': pill((data.get('marca') or '').upper(), font('lg-black.woff2', 30), PINK, INK, 24, 13) if data.get('marca') else None,
        'cta': text_block('¿Quieres saber _más_ de esta nota?', W - 2 * M, 3, 'lg-black.woff2', 128, 80, INK, it_color=WHITE),
        'cta2': body_block('Léela completa en guayabailustrada.com.mx', W - 2 * M, 44, INK, 2),
        'bio': pill('LINK EN LA BIO  →', font('lg-black.woff2', 46), INK, PINK, 54, 30),
        'firma': text_block('LG.I', 400, 1, 'lg-bold.woff2', 110, 100, INK, track=-0.05),
        'sigue': pill('@lgi.newsbrand', font('lg-bold.woff2', 36), WHITE, INK, 30, 16),
    }
    d0 = ImageDraw.Draw(Image.new('RGB', (4, 4)))
    fonts, ls, size = C.fitted(d0, data['portada'], W - 2 * M, 4, 'lg-black.woff2', 112, 64)
    L['gancho'] = (fonts, ls, size)
    return L


def gancho(base, t, L):
    """Titular grande que sube suave renglón por renglón y luego el marcatextos pinta las franjas."""
    fonts, ls, size = L['gancho']
    lh = size * 1.08
    y0 = 1500 - len(ls) * lh
    paste(base, L['tag'], M, y0 - 100 + (1 - eo(lin(t, .1, .5))) * 30, eo(lin(t, .1, .5)))
    run = [0]

    def marca():
        k = run[0]; run[0] += 1
        return eio(lin(t, 0.95 + k * 0.4, 1.45 + k * 0.4))
    for i, ln in enumerate(ls):
        p = eo(lin(t, .2 + i * .15, .6 + i * .15))
        capa = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        C.render(ImageDraw.Draw(capa), M, y0 + i * lh + (1 - p) * 30, [ln], fonts, lh, WHITE,
                 hl_bg=PINK, hl_fg=INK, pad=12, marca=marca)
        if p < 1:
            capa.putalpha(capa.getchannel('A').point(lambda v: int(v * p)))
        base.alpha_composite(capa)


def cierre(t, L):
    im = Image.new('RGBA', (W, H), PINK)
    cta = L['cta']; a = eo(lin(t, .15, .7)); y = 560
    paste(im, cta, M - 20, y + (1 - a) * 60, a)
    y += cta.height + 30
    b = eo(lin(t, .45, 1.0)); paste(im, L['cta2'], M - 10, y + (1 - b) * 40, b)
    y += L['cta2'].height + 70
    c = eo(lin(t, .7, 1.1)); pulso = 1 - 0.04 * max(0.0, math.sin(max(0, t - 1.2) * math.pi / 0.9)) ** 8
    bio = L['bio']
    k = c * pulso
    if k != 1:
        bio = bio.resize((max(1, int(bio.width * k)), max(1, int(bio.height * k))), Image.BILINEAR)
    paste(im, bio, M + (L['bio'].width - bio.width) / 2, y + (L['bio'].height - bio.height) / 2, min(1, c))
    paste(im, L['firma'], M - 20, 1480, eo(lin(t, 1.0, 1.5)))
    paste(im, L['sigue'], W - M - L['sigue'].width, 1510, eo(lin(t, 1.1, 1.6)))
    return im


def guion_de(data):
    g = (data.get('guion') or '').strip()
    if g:
        return g
    partes = [re.sub(r'[*_\[\]]', '', data.get('portada', '')).strip().rstrip('.') + '.']
    if data.get('resumen'):
        partes.append(re.sub(r'[\[\]]', '', data['resumen']))
    info = data.get('info') or []
    if info:
        partes.append(re.sub(r'[\[\]]', '', info[0]))
    partes.append('La nota completa está en el link de la bio.')
    return ' '.join(partes)


def make(data, out):
    import voz
    tmp = tempfile.mkdtemp()
    try:
        (palabras, dvoz), mp3 = voz.sintetizar(guion_de(data), f'{tmp}/voz.mp3')
        palabras = [(a + INICIO_VOZ, b + INICIO_VOZ, w) for a, b, w in palabras]
        total = max(15.0, min(40.0, INICIO_VOZ + dvoz + 0.5 + CIERRE))
        fin_cuerpo = total - CIERRE
        L = preparar(data)
        F = fondos(data, tmp)
        if not F:
            raise RuntimeError('No hay fotos ni video para el Reel')
        G = [g for g in grupos(palabras)]
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-']
        pr = subprocess.Popen(cmd + ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                                     '-r', str(FPS), f'{tmp}/video.mp4'], stdin=subprocess.PIPE)
        for i in range(int(total * FPS)):
            t = i / FPS
            if t >= fin_cuerpo:
                im = cierre(t - fin_cuerpo, L)
                if t - fin_cuerpo < 0.3:                   # transición: el cierre sube desde abajo
                    k = eio((t - fin_cuerpo) / 0.3)
                    prev = Image.new('RGBA', (W, H), INK)
                    prev.alpha_composite(im, (0, int(H * (1 - k))))
                    im = prev
            else:
                n = int(t // SEG)
                f = F[n % len(F)]
                im = cuadro_fondo(f, t - n * SEG).convert('RGBA')
                im.alpha_composite(L['abajo']); im.alpha_composite(L['arriba'], (0, 0))
                paste(im, L['brand'], M, 150)
                if t < GANCHO:
                    gancho(im, t, L)
                else:
                    if L['marca']:
                        paste(im, L['marca'], M, 230, eo(lin(t, GANCHO, GANCHO + .4)))
                    g = next((g for g in G if g[0][0] - 0.05 <= t <= g[-1][1] + 0.25), None)
                    if g:
                        s = subtitulo(g, t)
                        paste(im, s, (W - s.width) / 2, 1380)
            buf = __import__('io').BytesIO()
            im.convert('RGB').save(buf, 'JPEG', quality=90)
            pr.stdin.write(buf.getvalue())
        pr.stdin.close(); pr.wait()
        if pr.returncode:
            raise RuntimeError('ffmpeg falló armando el video del Reel')
        # audio: voz + música bajita (y si no hubo voz, solo música)
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{tmp}/video.mp4']
        filtros, entradas = [], 1
        if mp3:
            cmd += ['-i', mp3]; filtros.append(f'[{entradas}:a]adelay={int(INICIO_VOZ * 1000)}|{int(INICIO_VOZ * 1000)},volume=1.0[v]'); entradas += 1
        if os.path.exists(MUSIC):
            cmd += ['-stream_loop', '-1', '-i', MUSIC]
            vol = 0.14 if mp3 else 0.9
            filtros.append(f'[{entradas}:a]volume={vol},afade=t=out:st={total - 1.5:.2f}:d=1.5[m]'); entradas += 1
        if filtros:
            mez = ''.join(x for x in ('[v]' if mp3 else '', '[m]' if os.path.exists(MUSIC) else ''))
            n_in = mez.count('[')
            if n_in > 1:
                filtros.append(f'{mez}amix=inputs={n_in}:duration=longest:normalize=0[a]')
            else:
                filtros.append(f'{mez}anull[a]')
            cmd += ['-filter_complex', ';'.join(filtros), '-map', '0:v', '-map', '[a]', '-c:a', 'aac', '-b:a', '160k']
        cmd += ['-c:v', 'copy', '-t', f'{total:.2f}', '-movflags', '+faststart', out]
        subprocess.run(cmd, check=True)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2])
