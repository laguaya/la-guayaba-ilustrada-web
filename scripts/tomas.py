"""Tomas (cortes de cámara) del video de una campaña.

cortes(ruta)            -> (lista de tomas [(inicio, fin), ...], duración)
hoja(ruta, id)          -> guarda drafts/tomas/<id>.jpg (hoja de contactos con el segundo de cada toma)
                           y drafts/tomas/<id>.json ({"dur": s, "tomas": [[ini, fin], ...]})
El redactor mira la hoja para decir qué toma va con cada frase de la voz del Reel ("desde"/"hasta").
"""
import json, math, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(R, 'drafts', 'tomas')


def duracion(ruta):
    try:
        return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta],
                                    capture_output=True, text=True, timeout=60).stdout.strip())
    except Exception:
        return 0.0


def recorte(ruta):
    """Caja sin franjas negras (videos verticales metidos en cuadro horizontal) para ffmpeg: 'crop=w:h:x:y,'."""
    p = subprocess.run(['ffmpeg', '-hide_banner', '-t', '12', '-i', ruta, '-an', '-vf', 'cropdetect=24:2:0',
                        '-f', 'null', '-'], capture_output=True, text=True, timeout=300)
    c = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', p.stderr)
    return 'crop={}:{}:{}:{},'.format(*c[-1]) if c else ''


def cortes(ruta, umbral=0.25, minimo=0.7, maximo=3.5):
    """Detecta los cambios de toma. Junta tomas de menos de `minimo` segundos con la anterior y parte
    las tomas largas en tramos de `maximo` segundos (así cada frase puede usar una parte distinta)."""
    dur = duracion(ruta)
    p = subprocess.run(['ffmpeg', '-hide_banner', '-i', ruta, '-an', '-vf',
                        f"{recorte(ruta)}scale=320:-2,select='gt(scene,{umbral})',showinfo", '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=600)
    marcas = [float(x) for x in re.findall(r'pts_time:([\d.]+)', p.stderr)]
    inicios = [0.0]
    for m in marcas:
        if m - inicios[-1] >= minimo and dur - m >= minimo:
            inicios.append(m)
    tomas = []
    for a, b in zip(inicios, inicios[1:] + [dur]):
        n = max(1, math.ceil((b - a) / maximo))
        for k in range(n):
            tomas.append((round(a + (b - a) * k / n, 2), round(a + (b - a) * (k + 1) / n, 2)))
    return tomas, dur


def _cuadro(ruta, t, tmp, k, crop=''):
    out = f'{tmp}/c{k}.jpg'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', ruta, '-frames:v', '1',
                    '-vf', crop + 'scale=480:-2', out], capture_output=True, timeout=60)
    return Image.open(out).convert('RGB') if os.path.exists(out) else None


def hoja(ruta, nid, salida=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import portada
    tomas, dur = cortes(ruta)
    if not tomas:
        return None
    if len(tomas) > 48:                                     # demasiadas: se juntan de dos en dos
        tomas = [(tomas[i][0], tomas[min(i + 1, len(tomas) - 1)][1]) for i in range(0, len(tomas), 2)]
    os.makedirs(salida or CARPETA, exist_ok=True)
    base = os.path.join(salida or CARPETA, nid)
    cols, tw = 4, 300
    f = portada.font('lg-bold.woff2', 22)
    with tempfile.TemporaryDirectory() as tmp:
        cuadros, crop = [], recorte(ruta)
        for k, (a, b) in enumerate(tomas):
            im = _cuadro(ruta, a + (b - a) / 2, tmp, k, crop)          # cuadro de en medio de la toma
            cuadros.append(im)
        ref = next((c for c in cuadros if c), None)
        if ref is None:
            return None
        th = int(tw * ref.height / ref.width) if ref.width >= ref.height else int(tw * 16 / 9)
        th = min(th, 420)
        filas = (len(tomas) + cols - 1) // cols
        lienzo = Image.new('RGB', (cols * (tw + 10) + 10, filas * (th + 44) + 10), '#111')
        d = ImageDraw.Draw(lienzo)
        for k, ((a, b), im) in enumerate(zip(tomas, cuadros)):
            x, y = 10 + (k % cols) * (tw + 10), 10 + (k // cols) * (th + 44)
            if im:
                r = min(tw / im.width, th / im.height)
                im = im.resize((int(im.width * r), int(im.height * r)))
                lienzo.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
            d.text((x + 4, y + th + 8), f'#{k + 1}  {a:.1f}–{b:.1f} s', font=f, fill='#FFC6DD')
        lienzo.save(base + '.jpg', quality=78)
    json.dump({'dur': round(dur, 2), 'tomas': [list(t) for t in tomas]}, open(base + '.json', 'w'))
    return base + '.jpg'


def de_url(url, nid):
    """Baja el MP4 de la campaña y arma su hoja de tomas en drafts/tomas/."""
    import requests
    with tempfile.TemporaryDirectory() as tmp:
        ruta = f'{tmp}/v.mp4'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=90, stream=True)
        if r.status_code != 200:
            return None
        tam = 0
        with open(ruta, 'wb') as f:
            for ch in r.iter_content(1 << 16):
                tam += len(ch)
                if tam > 150 * 1024 * 1024:
                    break
                f.write(ch)
        return hoja(ruta, nid)


if __name__ == '__main__':
    print(de_url(sys.argv[1], sys.argv[2]) if sys.argv[1].startswith('http') else hoja(sys.argv[1], sys.argv[2]))
