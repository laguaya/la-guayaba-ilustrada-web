"""Carrusel animado: cada lámina como video corto (1080x1350, 30 fps) con el mismo diseño del carrusel fijo.

Uso: python scripts/carrusel_video.py datos.json carpeta_salida
Genera 1.mp4 ... N.mp4 (y también los .jpg fijos, que sirven de miniatura y de respaldo).
Cada lámina mueve UNA sola cosa, de golpe, se queda quieta y vuelve a moverse:
  1) la foto  2) el titular  3) la palabra "saber"  4) el botón "link en bio".
"""
import functools, io, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portada
import carrusel as C

FPS, DUR = 30, 6.0          # 3 golpes por lámina; el video se repite sin brincos


@functools.lru_cache(maxsize=None)
def _font(name, size):
    return portada.font(name, size)


C.font = _font


def _video(fn, data, n, ruta):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
           '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
           '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', ruta]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    quieto = None
    for f in range(int(DUR * FPS)):
        C.A = {'t': f / FPS}
        g = C.golpe()
        if g == 0 and quieto:
            pr.stdin.write(quieto); continue
        buf = io.BytesIO()
        fn(data, buf, n) if n else fn(data, buf)
        if g == 0:
            quieto = buf.getvalue()
        pr.stdin.write(buf.getvalue())
    C.A = None
    pr.stdin.close(); pr.wait()
    if pr.returncode:
        raise RuntimeError('ffmpeg falló en ' + ruta)
    return ruta


def make(data, outdir):
    C.make(data, outdir)
    total = C.TOTAL
    out = [_video(C.slide1, data, 0, os.path.join(outdir, '1.mp4')),
           _video(C.slide2, data, 0, os.path.join(outdir, '2.mp4'))]
    if total == 4:
        out.append(_video(C.slide_info, data, 3, os.path.join(outdir, '3.mp4')))
    out.append(_video(C.slide3, data, total, os.path.join(outdir, f'{total}.mp4')))
    return out


if __name__ == '__main__':
    print(make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2]))
