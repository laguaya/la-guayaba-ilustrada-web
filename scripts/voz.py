"""Voz en off con IA para los Reels (Microsoft Edge TTS, voces neuronales de México).

sintetizar(texto, salida_mp3) -> (palabras, duracion)
  palabras = [(inicio_s, fin_s, 'palabra'), ...]  (sirve para los subtítulos tipo karaoke)
Si no hay internet o falla el servicio, regresa (tiempos estimados, duración) y salida_mp3 = None.
"""
import asyncio, os, re, subprocess, sys

VOZ = os.environ.get('REEL_VOZ', 'es-MX-JorgeNeural')
RITMO = os.environ.get('REEL_RITMO', '+10%')


def limpiar(texto):
    """Quita las marcas de formato (*, _, [ ]) que usamos en el carrusel."""
    return re.sub(r'\s+', ' ', re.sub(r'[*_\[\]]', '', texto)).strip()


def _estimado(texto, vel=2.7):
    t, out = 0.0, []
    for w in texto.split():
        d = max(0.18, len(w) * 0.06)
        out.append((t, t + d, w))
        t += d + (0.25 if w[-1] in '.,;:?!' else 0.05)
    return out, t


def duracion(ruta):
    try:
        return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta],
                                    capture_output=True, text=True, timeout=60).stdout.strip())
    except Exception:
        return 0.0


def sintetizar(texto, salida, voz=None, ritmo=None):
    texto = limpiar(texto)
    try:
        import edge_tts
    except Exception:
        print('Voz: falta edge-tts', file=sys.stderr)
        return _estimado(texto), None

    async def corre():
        com = edge_tts.Communicate(texto, voz or VOZ, rate=ritmo or RITMO, boundary='WordBoundary')
        palabras = []
        with open(salida, 'wb') as f:
            async for ch in com.stream():
                if ch['type'] == 'audio':
                    f.write(ch['data'])
                elif ch['type'] == 'WordBoundary':
                    ini = ch['offset'] / 1e7
                    palabras.append((ini, ini + ch['duration'] / 1e7, ch['text']))
        return palabras

    for intento in range(3):
        try:
            palabras = asyncio.run(corre())
            dur = duracion(salida)
            if palabras and dur > 1:
                return (palabras, dur), salida
        except Exception as e:
            print('Voz:', e, file=sys.stderr)
    return _estimado(texto), None
