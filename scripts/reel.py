"""Reel vertical (1080x1920, 30 fps, 15 a 75 s) de una nota, con branding de Newsbrand.

Uso: python scripts/reel.py datos.json salida.mp4
datos: img, img2, fotos (lista opcional), etiqueta, portada, titulo, marca, escenas o guion (texto de la voz),
       src (URL de la nota, para sacar clips del video de la campaña) o video (ruta local a un MP4).

Estructura:
  1) Gancho (0 a ~3 s): la primera toma con el titular grande y el marcatextos rosa.
  2) Cuerpo: una ESCENA por cada frase de la voz ("escenas" en los datos). SIEMPRE se ve video o foto:
       video  -> la toma del video de la campaña que corresponde ("desde"/"hasta" en segundos; si no viene,
                 la siguiente toma sin usar). Una frase larga encadena varias tomas; el video no se repite.
       foto   -> foto de lo que se menciona (URL, ruta o 'img'/'img2'), con una deriva muy lenta.
     Cortes suaves al ritmo de la voz (fundido de 0.16 s, sin zoom). Subtítulos tipo karaoke.
  3) Cierre (3 s): la última toma del video con el CTA para seguir la cuenta encima.
Solo se arma si la nota tiene video de la campaña.
Audio: voz con IA (scripts/voz.py) + música de fondo bajita.
"""
import functools, glob, json, math, os, re, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portada
import carrusel as C

W, H, FPS = 1080, 1920, 30
M = 72
INK, WHITE = '#0B0B0B', '#FFFFFF'
# Paleta propia del Reel (distinta del carrusel rosa y del animado naranja): morado uva + rosa claro
UVA, ROSA = '#6E1F5E', '#FFC6DD'
PINK = ROSA
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
    if im.height > im.width:                         # video vertical: a pantalla completa
        return encuadre.recorte(im, (W, H), foco, zoom=zoom, destino=(0.5, 0.42))
    fondo = im.resize((54, 96)).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
    fondo = Image.blend(fondo, Image.new('RGB', (W, H), UVA), 0.55)
    bw = W
    bh = int(im.height * bw / im.width)
    if bh > H * 0.62:
        bh = int(H * 0.62); bw = int(im.width * bh / im.height)
    banda = encuadre.recorte(im, (bw, bh), foco, zoom=zoom)
    fondo.paste(banda, ((W - bw) // 2, int(H * 0.40 - bh / 2)))
    return fondo


def bajar_video(data, tmp):
    if data.get('video') and os.path.exists(data['video']):
        return data['video']
    try:
        import fuentes, requests
        urls = [data['mp4']] if data.get('mp4') else (fuentes.mp4s_de_pagina(data['src']) if data.get('src') else [])
        for u in urls:
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


TRANS = 0.16   # cambio de escena: fundido muy corto, sin zoom (corte suave al ritmo de la voz)
CORTE = [None]   # caja sin franjas negras del video (si el video vertical viene dentro de un cuadro horizontal)
ESCALA = 'scale=min(1920\\,iw):-2'


def sin_bordes(cuadros):
    """Detecta franjas negras fijas (arriba/abajo o a los lados) en el video y regresa la caja útil."""
    caja = None
    for c in cuadros:
        im = Image.open(c).convert('L')
        b = im.point(lambda v: 255 if v > 22 else 0).getbbox()
        if not b:
            continue
        caja = b if caja is None else (min(caja[0], b[0]), min(caja[1], b[1]), max(caja[2], b[2]), max(caja[3], b[3]))
    if not caja:
        return None
    w, h = Image.open(cuadros[0]).size
    if (caja[2] - caja[0]) < w * 0.96 or (caja[3] - caja[1]) < h * 0.96:
        return caja
    return None


def abrir(ruta):
    im = Image.open(ruta)
    return im.crop(CORTE[0]) if CORTE[0] else im


def fps_de(vid):
    """Cuadros por segundo del video de la campaña (24, 25 o 30). Si se arma a otra velocidad, ffmpeg repite
    cuadros cada tanto y el movimiento se ve a brincos."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                            '-of', 'csv=p=0', vid], capture_output=True, text=True, timeout=60).stdout.strip()
        a, b = (r.split('/') + ['1'])[:2]
        f = float(a) / float(b)
        return min((24, 25, 30), key=lambda x: abs(x - f)) if 20 < f < 61 else 30
    except Exception:
        return 30


def muestras(vid, tmp, vdur, n=9):
    carpeta = f'{tmp}/muestras'; os.makedirs(carpeta, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', vid, '-vf', f'fps={n / max(1.0, vdur):.4f},{ESCALA}',
                    '-q:v', '3', f'{carpeta}/%03d.jpg'], capture_output=True, timeout=600)
    return sorted(glob.glob(f'{carpeta}/*.jpg'))


def clip(vid, tmp, k, desde, segundos):
    """Cuadros de un tramo del video de la campaña (solo el tramo que se va a usar)."""
    carpeta = f'{tmp}/clip{k}'; os.makedirs(carpeta, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{desde:.2f}', '-i', vid, '-t', f'{segundos + 0.1:.2f}',
                    '-vf', f'fps={FPS},{ESCALA}', '-q:v', '2', f'{carpeta}/%05d.jpg'], capture_output=True, timeout=600)
    return sorted(glob.glob(f'{carpeta}/*.jpg'))


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
            d.rounded_rectangle((x - 12, 14, x + aw + 12, 14 + a + de + 8), radius=10, fill=ROSA)
            d.text((x, 18 + a), w, font=f, fill=UVA, anchor='ls')
        else:
            d.text((x, 18 + a), w, font=f, fill=WHITE, anchor='ls', stroke_width=5, stroke_fill=UVA)
        x += aw + sp
    return im


# ---------------------------------------------------------------- escenas
def preparar(data):
    g = Image.new('L', (1, H))
    for y in range(H):
        t = max(0.0, (y - H * .45) / (H * .45)); g.putpixel((0, y), int(255 * min(1.0, t) ** .9 * .85))
    abajo = Image.new('RGBA', (W, H), (60, 14, 50, 0)); abajo.putalpha(g.resize((W, H)))
    top = Image.linear_gradient('L').rotate(180).resize((W, 380)).point(lambda v: int(v * .6))
    arriba = Image.new('RGBA', (W, 380), (60, 14, 50, 0)); arriba.putalpha(top)
    L = {
        'abajo': abajo, 'arriba': arriba,
        'brand': pill('NEWSBRAND · LA GUAYABA ILUSTRADA', font('lg-bold.woff2', 26), (255, 255, 255, 46), WHITE, 26, 14),
        'tag': pill((data.get('etiqueta') or 'NOTICIAS').upper(), font('lg-black.woff2', 34), ROSA, UVA, 30, 16),
        'marca': pill((data.get('marca') or '').upper(), font('lg-black.woff2', 30), ROSA, UVA, 24, 13) if data.get('marca') else None,
        'cta': text_block('Síguenos para no perderte la próxima', W - 2 * M, 2, 'lg-black.woff2', 76, 56, WHITE),
        'bio': pill('@lgi.newsbrand', font('lg-black.woff2', 40), ROSA, UVA, 40, 22),
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
                 hl_bg=ROSA, hl_fg=UVA, pad=12, marca=marca)
        if p < 1:
            capa.putalpha(capa.getchannel('A').point(lambda v: int(v * p)))
        base.alpha_composite(capa)


def cierre(base, t, L):
    """CTA sobre el video (nunca fondo de color): aparece con un fundido suave."""
    a = eio(lin(t, 0.1, 0.9))
    y = 1330
    paste(base, L['cta'], M - 10, y, a)
    b = eio(lin(t, 0.5, 1.3))
    paste(base, L['bio'], M, y + L['cta'].height + 24, b)


def guion_de(data):
    es = data.get('escenas')
    if isinstance(es, list) and es and all(isinstance(e, dict) and e.get('voz') for e in es):
        return ' '.join(e['voz'].strip() for e in es)
    g = (data.get('guion') or '').strip()
    if g:
        return g
    partes = [re.sub(r'[*_\[\]]', '', data.get('portada', '')).strip().rstrip('.') + '.']
    if data.get('resumen'):
        partes.append(re.sub(r'[\[\]]', '', data['resumen']))
    info = data.get('info') or []
    if info:
        partes.append(re.sub(r'[\[\]]', '', info[0]))
    partes.append('Síguenos para más noticias de marcas todos los días.')
    return ' '.join(partes)


# ---------------------------------------------------------------- escenas: lo que se ve con cada frase
def escenas_de(data):
    """Lista de escenas [{'voz': frase, 'ver': 'video'|'foto'|'dato'|'frase', ...}].
    Si la nota no trae escenas, cada frase del guion es una escena con su propia toma del video."""
    es = data.get('escenas')
    if isinstance(es, list) and es and all(isinstance(e, dict) and e.get('voz') for e in es):
        return [dict(e) for e in es]
    out = []
    for f in re.split(r'(?<=[.!?…])\s+', guion_de(data)):
        if not f.strip():
            continue
        if out and len(out[-1]['voz'].split()) < 7:
            out[-1]['voz'] += ' ' + f
        else:
            out.append({'voz': f, 'ver': 'video'})
    return out


def _norm(w):
    return re.sub(r'[^0-9a-záéíóúüñ]', '', w.lower())


def tiempos(escenas, palabras, limpiar):
    """Segundo en que la voz empieza cada escena."""
    guion = []
    for i, e in enumerate(escenas):
        for w in limpiar(e['voz']).split():
            if _norm(w):
                guion.append((_norm(w), i))
    ini, j = [None] * len(escenas), 0
    for a, _, w in palabras:
        n = _norm(w)
        if not n or not guion:
            continue
        k = next((k for k in range(j, min(j + 6, len(guion))) if guion[k][0] == n), None)
        if k is None:
            k = min(j, len(guion) - 1)
        j = k + 1
        i = guion[k][1]
        if ini[i] is None:
            ini[i] = a
    ini[0] = 0.0
    for i in range(1, len(ini)):                      # escenas sin palabras reconocidas: justo después de la anterior
        if ini[i] is None or ini[i] < ini[i - 1]:
            ini[i] = ini[i - 1] + 0.5
    return ini


def bajar_foto(ref, tmp, k):
    """Foto de una escena: ruta local, 'img'/'img2' (fotos de la nota) o URL."""
    if not ref:
        return None
    if os.path.exists(str(ref)):
        try:
            return Image.open(ref).convert('RGB')
        except Exception:
            return None
    if str(ref).startswith('http'):
        try:
            import fuentes, requests, io
            r = requests.get(ref, headers=fuentes.UA, timeout=40)
            if r.status_code == 200 and len(r.content) > 5000:
                im = Image.open(io.BytesIO(r.content)).convert('RGB')
                if min(im.size) >= 300:
                    return im
        except Exception as e:
            print('Foto de escena:', e, file=sys.stderr)
    return None


def plan(escenas, ini, fin_cuerpo, total, vid, tomas, vdur, data, tmp):
    """Convierte las escenas en tramos de imagen: [{'a','b','tipo': 'video'|'foto', ...}].
    Siempre hay video o foto en pantalla. Las tomas no se repiten mientras haya material nuevo:
    una frase larga encadena varias tomas; si se acaba el video, siguen las fotos; solo al final,
    si no queda nada, se vuelve a una toma con otro encuadre (más cerrado) y en cámara lenta."""
    import encuadre
    pedidas = {data.get(e['foto']) if e.get('foto') in ('img', 'img2') else e.get('foto')
               for e in escenas if e.get('foto')}
    fotos_nota = [p for p in (data.get('img'), data.get('img2')) if p and os.path.exists(p)]
    fotos_nota += [p for p in (data.get('fotos') or []) if p and os.path.exists(p) and p not in fotos_nota]
    fotos_nota = [p for p in fotos_nota if p not in pedidas]   # las fotos que pide una escena no se usan de relleno
    fi = [0]
    usos = [0] * len(tomas)
    tramos, usados, k = [], [], [0]
    foco_video = [(0.5, 0.45)]                          # un solo encuadre para todo el video: las tomas no "brincan" de lugar
    if vid:
        m = muestras(vid, tmp, vdur, n=5)
        if m:
            foco_video[0] = encuadre.foco(abrir(m[len(m) // 2]).convert('RGB'))

    def foto_libre():
        while fi[0] < len(fotos_nota):
            p = fotos_nota[fi[0]]; fi[0] += 1
            im = bajar_foto(p, tmp, 0)
            if im:
                return im
        return None

    def libre(t0, t1):
        return all(t1 <= a + 0.05 or t0 >= b - 0.05 for a, b in usados)

    def poner_foto(a, b, im):
        tramos.append(dict(a=a, b=b, tipo='foto', im=im, foco=encuadre.foco(im)))

    def poner_video(a, d, desde, hasta=None, zoom=1.0, vel_min=0.88):
        """Pone un tramo de video desde `desde`; regresa los segundos que cubrió.
        Deja 1 cuadro de margen en cada orilla de la toma para que nunca se cuele un cuadro de la toma vecina."""
        margen = 1.0 / FPS
        desde = desde + margen
        fin = vdur - margen
        if hasta is not None and hasta > desde + 0.3:
            fin = min(fin, hasta - margen)             # nunca se pasa de la toma elegida
        hay = fin - desde
        vel = 1.0 if hay >= d else max(vel_min, hay / d)   # a lo mucho un 12 % más lento: no se notan brincos
        largo = min(d, hay / vel)
        if largo < 0.5:
            return 0.0
        extra = max(0.0, min(TRANS + 0.05, fin - desde - largo * vel))   # cola para el fundido de salida
        cuadros = clip(vid, tmp, k[0], desde, largo * vel + extra); k[0] += 1
        if len(cuadros) < 3:
            return 0.0
        tramos.append(dict(a=a, b=a + largo, tipo='video', cuadros=cuadros, vel=vel, foco=foco_video[0], zoom=zoom))
        usados.append((desde, desde + largo * vel))
        for i, (t0, t1) in enumerate(tomas):
            if t0 < desde + largo * vel and t1 > desde:
                usos[i] += 1
        return largo

    def toma_libre():
        return next(((t0, t1) for t0, t1 in tomas if libre(t0, min(t1, t0 + 1.0))), None)

    def rellenar(a, b, e=None, primera=True):
        """Cubre de a a b con video nuevo, luego fotos y, si ya no hay nada, otro encuadre de una toma."""
        while b - a > 0.05:
            d = b - a
            cubierto = 0.0
            if primera and e and e.get('desde') is not None and float(e['desde']) < vdur - 0.4:
                h = e.get('hasta')
                cubierto = poner_video(a, d, float(e['desde']), float(h) if h is not None else None)
            else:
                tl = toma_libre() if vid else None
                if tl:
                    cubierto = poner_video(a, d, tl[0], tl[1])
                    if not cubierto:
                        usados.append(tl)
                        continue
                else:
                    im = foto_libre()
                    if im:
                        poner_foto(a, min(b, a + max(2.5, min(d, 4.5))), im)
                        cubierto = tramos[-1]['b'] - a
                    elif tomas:
                        i = min(range(len(tomas)), key=lambda j: (usos[j], -(tomas[j][1] - tomas[j][0])))
                        cubierto = poner_video(a, d, tomas[i][0], tomas[i][1])
                        usos[i] += 1
            primera = False
            if cubierto <= 0:
                estirar(b)
                break
            a += cubierto
            if b - a < 0.35 and tramos:                 # sobra casi nada: se alarga la toma actual
                estirar(b)
                break

    def estirar(b):
        """Alarga el último tramo hasta b. Si es video, lo hace un poco más lento (con cuadros mezclados) en vez de congelarlo."""
        if not tramos:
            return
        L = tramos[-1]
        if L['tipo'] == 'video' and b > L['b']:
            L['vel'] *= (L['b'] - L['a']) / (b - L['a'])
        L['b'] = max(L['b'], b)

    for i, e in enumerate(escenas):
        a = 0.0 if i == 0 else max(0.0, ini[i] - 0.12)
        b = fin_cuerpo if i == len(escenas) - 1 else max(a + 0.3, ini[i + 1] - 0.12)
        if (e.get('ver') or '').lower() == 'foto' or e.get('foto'):
            ref = e.get('foto')
            im = bajar_foto(data.get(ref) if ref in ('img', 'img2') else ref, tmp, i)
            if im:
                poner_foto(a, b, im)
                continue
        rellenar(a, b, e)
    # cierre: la última toma del video (normalmente el producto o el logo) detrás del CTA
    if vid and tomas:
        t0, t1 = toma_libre() or tomas[-1]
        if not poner_video(fin_cuerpo, total - fin_cuerpo, t0, t1, vel_min=0.5):
            rellenar(fin_cuerpo, total, primera=False)
    else:
        rellenar(fin_cuerpo, total, primera=False)
    estirar(total)
    return tramos


def imagen_tramo(tr, tl):
    """Imagen del tramo en su segundo local tl (siempre video o foto)."""
    if tr['tipo'] == 'video':
        cs = tr['cuadros']
        pos = tl * tr['vel'] * FPS + 1e-6
        i0 = min(len(cs) - 1, int(pos))
        im = vertical(abrir(cs[i0]), tr['foco'], zoom=tr.get('zoom', 1.0))
        f = pos - int(pos)
        if tr['vel'] < 1 and f > 0.08 and i0 + 1 < len(cs):     # cámara lenta: mezcla los dos cuadros vecinos (sin tirones)
            im = Image.blend(im, vertical(abrir(cs[i0 + 1]), tr['foco'], zoom=tr.get('zoom', 1.0)), f)
        return im.convert('RGBA')
    if 'base' not in tr:
        tr['base'] = vertical(tr['im'], tr['foco'])
    d = max(0.5, tr['b'] - tr['a'])
    z = 1.0 + 0.04 * cl(tl / d)                        # acercamiento muy lento y continuo (sub-pixel: sin temblor)
    w, h = W / z, H / z
    x0, y0 = (W - w) / 2, (H - h) * 0.45
    return tr['base'].resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + w, y0 + h)).convert('RGBA')


def make(data, out):
    import voz, tomas as TM
    tmp = tempfile.mkdtemp()
    try:
        escenas = escenas_de(data)
        (palabras, dvoz), mp3 = voz.sintetizar(guion_de(data), f'{tmp}/voz.mp3')
        palabras = [(a + INICIO_VOZ, b + INICIO_VOZ, w) for a, b, w in palabras]
        total = max(15.0, min(75.0, INICIO_VOZ + dvoz + 0.5 + CIERRE))   # hasta ~1 minuto de voz; nunca se corta
        fin_cuerpo = total - CIERRE
        L = preparar(data)
        vid = bajar_video(data, tmp)
        if not vid:
            raise RuntimeError('La nota no tiene video de la campaña para el Reel')
        global FPS
        FPS = fps_de(vid)                                   # se arma a los cuadros por segundo del video original: sin cuadros repetidos
        tms, vdur = TM.cortes(vid)
        if vdur < 2:
            raise RuntimeError('No pude sacar el video de la campaña')
        CORTE[0] = sin_bordes(muestras(vid, tmp, vdur))   # un video vertical metido en cuadro horizontal sale a pantalla completa
        ini = tiempos(escenas, palabras, voz.limpiar)
        tramos = plan(escenas, ini, fin_cuerpo, total, vid, tms, vdur, data, tmp)
        print('Reel:', [(round(x['a'], 1), round(x['b'], 1), x['tipo']) for x in tramos], file=sys.stderr)
        G = [g for g in grupos(palabras)]
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-']
        pr = subprocess.Popen(cmd + ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                                     '-r', str(FPS), f'{tmp}/video.mp4'], stdin=subprocess.PIPE)
        ti = 0
        for i in range(int(total * FPS)):
            t = i / FPS
            while ti < len(tramos) - 1 and t >= tramos[ti]['b']:
                ti += 1
            tr = tramos[ti]
            tl = max(0.0, t - tr['a'])
            im = imagen_tramo(tr, tl)
            if ti > 0 and tl < TRANS:                       # corte suave: fundido muy corto, sin zoom
                pv = tramos[ti - 1]
                prev = imagen_tramo(pv, t - pv['a'])       # la toma anterior sigue corriendo durante el fundido
                a = tl / TRANS
                im = Image.blend(prev, im, a * a * (3 - 2 * a))
            im.alpha_composite(L['abajo']); im.alpha_composite(L['arriba'], (0, 0))
            paste(im, L['brand'], M, 150)
            if t < GANCHO:
                gancho(im, t, L)
            else:
                if L['marca']:
                    paste(im, L['marca'], M, 230, eo(lin(t, GANCHO, GANCHO + .4)))
                if t >= fin_cuerpo:
                    cierre(im, t - fin_cuerpo, L)
                else:
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
