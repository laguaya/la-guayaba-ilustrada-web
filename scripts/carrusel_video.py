"""Carrusel animado: cada lámina como video corto (1080x1350, 30 fps) con el mismo diseño del carrusel fijo.

Uso: python scripts/carrusel_video.py datos.json carpeta_salida
Genera 1.mp4 ... N.mp4 (y también los .jpg fijos de siempre, que sirven de miniatura y de respaldo).
Movimiento: el texto entra palabra por palabra, las franjas rosas se pintan, las líneas se trazan
y las fotos hacen un zoom lento.
"""
import functools, io, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portada
import carrusel as C

FPS = 30
DUR = {'1': 6.0, '2': 7.0, 'info': 9.0, 'fin': 5.0}


@functools.lru_cache(maxsize=None)
def _font(name, size):
    return portada.font(name, size)


C.font = _font


def _contar(fn, data, n):
    """Cuántas palabras animadas tiene la lámina."""
    C.A = {'t': 1e9, 'i': 0, 'step': 0.05, 'start': 0, 'dur': 0.35}
    fn(data, io.BytesIO(), n) if n else fn(data, io.BytesIO())
    k = C.A['i']; C.A = None
    return k


def _video(fn, data, n, dur, ruta, start=0.35, ventana=2.4, kb=0.0):
    palabras = max(1, _contar(fn, data, n))
    step = min(0.075, ventana / palabras)
    fin_anim = start + palabras * step + 0.6
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
           '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
           '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', ruta]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ultimo = None
    for f in range(int(dur * FPS)):
        t = f / FPS
        if kb == 0 and t > fin_anim and ultimo:
            pr.stdin.write(ultimo); continue
        C.A = {'t': t, 'i': 0, 'step': step, 'start': start, 'dur': 0.4, 'kb': kb, 'total': dur}
        buf = io.BytesIO()
        fn(data, buf, n) if n else fn(data, buf)
        ultimo = buf.getvalue()
        pr.stdin.write(ultimo)
    C.A = None
    pr.stdin.close(); pr.wait()
    if pr.returncode:
        raise RuntimeError('ffmpeg falló en ' + ruta)
    return ruta


def make(data, outdir):
    C.make(data, outdir)                       # láminas fijas (miniaturas y respaldo)
    total = C.TOTAL
    out = [_video(C.slide1, data, 0, DUR['1'], os.path.join(outdir, '1.mp4'), start=0.3, ventana=1.4, kb=0.10),
           _video(C.slide2, data, 0, DUR['2'], os.path.join(outdir, '2.mp4'), start=0.3, ventana=2.6, kb=0.08)]
    if total == 4:
        out.append(_video(C.slide_info, data, 3, DUR['info'], os.path.join(outdir, '3.mp4'), start=0.4, ventana=4.2))
    out.append(_video(C.slide3, data, total, DUR['fin'], os.path.join(outdir, f'{total}.mp4'), start=0.25, ventana=1.2))
    return out


if __name__ == '__main__':
    print(make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2]))
