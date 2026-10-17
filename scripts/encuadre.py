"""Encuadre inteligente: encuentra lo importante de una foto (caras, producto, logotipo) y recorta
para que quede centrado y visible.

foco(ruta_o_imagen) -> (fx, fy) entre 0 y 1
recorte(im, (w, h), foco, zoom=1.0, destino=(0.5, 0.5)) -> imagen de w x h con el foco en 'destino'
"""
import numpy as np
from PIL import Image

try:
    import cv2
except Exception:                       # sin OpenCV: centro de la imagen
    cv2 = None

_CACHE = {}
_caras_cache = {}


def _caras(g):
    if cv2 is None:
        return []
    out = []
    for nombre in ('haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml'):
        try:
            cas = cv2.CascadeClassifier(cv2.data.haarcascades + nombre)
        except Exception:
            continue
        if cas.empty():
            continue
        m = min(g.shape[:2])
        for (x, y, w, h) in cas.detectMultiScale(g, 1.1, 6, minSize=(max(24, m // 14),) * 2):
            out.append((x, y, w, h))
    return out


def _mapa(rgb):
    """Qué tan llamativa es cada zona: colores poco comunes en la foto, sobre todo si son vivos
    (el producto, el empaque, el logo), con una ligera preferencia por el centro."""
    h, w = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.int32)
    b = 16
    q = (lab[..., 0] // (b * 2)) * 256 + (lab[..., 1] // b) * 16 + lab[..., 2] // b
    freq = np.bincount(q.ravel(), minlength=16 ** 3).astype(np.float64) / q.size
    rareza = -np.log(freq[q] + 1e-6)
    sat = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 1] / 255.0
    m = cv2.GaussianBlur((rareza * (0.5 + sat)).astype(np.float32), (0, 0), max(2, w / 80))
    yy, xx = np.mgrid[0:h, 0:w]
    m *= 1 - 0.35 * (((xx / w - .5) ** 2 + (yy / h - .5) ** 2) / .5)
    return m


def foco(src):
    key = src if isinstance(src, str) else id(src)
    if key in _CACHE:
        return _CACHE[key]
    im = Image.open(src) if isinstance(src, str) else src
    im = im.convert('RGB')
    if cv2 is None:
        _CACHE[key] = (0.5, 0.5); return _CACHE[key]
    k = 480 / max(im.size)
    small = np.array(im.resize((max(1, int(im.width * k)), max(1, int(im.height * k)))))
    h, w = small.shape[:2]
    caras = _caras(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))
    _caras_cache[key] = bool(caras)
    if caras:
        tot = sum(cw * ch for _, _, cw, ch in caras)
        fx = sum((x + cw / 2) * cw * ch for x, y, cw, ch in caras) / tot / w
        fy = sum((y + ch * 0.55) * cw * ch for x, y, cw, ch in caras) / tot / h   # un poco abajo de la cara
    else:
        m = _mapa(small)
        top = m >= np.quantile(m, 0.93)
        ys, xs = np.nonzero(top)
        wts = m[top]
        fx = float((xs * wts).sum() / wts.sum() / w)
        fy = float((ys * wts).sum() / wts.sum() / h)
    _CACHE[key] = (min(max(fx, 0.0), 1.0), min(max(fy, 0.0), 1.0))
    return _CACHE[key]


_MAPAS = {}


def _mapa_de(src):
    if src in _MAPAS:
        return _MAPAS[src]
    im = Image.open(src).convert('RGB') if isinstance(src, str) else src.convert('RGB')
    k = 480 / max(im.size)
    small = np.array(im.resize((max(1, int(im.width * k)), max(1, int(im.height * k)))))
    m = _mapa(small) if cv2 is not None else np.ones(small.shape[:2])
    if isinstance(src, str):
        _MAPAS[src] = m
    return m


def foco_ventana(src, aspecto):
    """Compatibilidad: el foco ya apunta al objeto principal (o a la cara, si hay)."""
    return foco(src)


def recorte(im, size, f=None, zoom=1.0, destino=(0.5, 0.5), zoom_max=1.0):
    """Escala para cubrir 'size' y mueve el recorte para que el foco quede en 'destino' (sin salirse de la foto).
    Si con el tamaño justo no se puede llevar el foco a 'destino', acerca la foto hasta zoom_max."""
    W, H = size
    f = f or (0.5, 0.5)
    base = max(W / im.width, H / im.height)
    if zoom_max > zoom:
        for eje, (fv, dv, lado, total) in enumerate(((f[0], destino[0], W, im.width), (f[1], destino[1], H, im.height))):
            sl = base * total / lado                       # cuánto sobra en este eje con zoom 1
            if fv > dv and fv < 1:
                need = (1 - dv) / (1 - fv) / sl
            elif fv < dv and fv > 0:
                need = dv / fv / sl
            else:
                need = 1.0
            zoom = max(zoom, min(zoom_max, need))
    s = base * zoom
    sw, sh = im.width * s, im.height * s
    x = max(0.0, min(f[0] * sw - destino[0] * W, sw - W))
    y = max(0.0, min(f[1] * sh - destino[1] * H, sh - H))
    box = (x / s, y / s, min(im.width, (x + W) / s), min(im.height, (y + H) / s))
    return im.resize((W, H), Image.LANCZOS, box=box)
