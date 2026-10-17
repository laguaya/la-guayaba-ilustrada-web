"""Voz en off con IA para los Reels.
Primero ElevenLabs (si están los secretos ELEVENLABS_API_KEY y ELEVENLABS_VOICE_ID); si falla o se acaban
los créditos, la voz gratuita de Microsoft Edge (voces neuronales de México).

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


def elevenlabs(texto, salida):
    """Voz de ElevenLabs con tiempos por letra (para los subtítulos). Regresa (palabras, duración) o None."""
    import base64, requests
    clave, voz = os.environ.get('ELEVENLABS_API_KEY'), os.environ.get('ELEVENLABS_VOICE_ID')
    if not (clave and voz):
        return None
    modelo = os.environ.get('ELEVENLABS_MODEL', 'eleven_multilingual_v2')
    try:
        r = requests.post(f'https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps',
                          params={'output_format': 'mp3_44100_128'},
                          headers={'xi-api-key': clave, 'Content-Type': 'application/json'},
                          json={'text': texto, 'model_id': modelo,
                                'voice_settings': {'stability': 0.45, 'similarity_boost': 0.8, 'style': 0.25,
                                                   'use_speaker_boost': True}}, timeout=120)
        if r.status_code != 200:
            print('ElevenLabs:', r.status_code, r.text[:300], file=sys.stderr)
            ELEVEN_ERROR[0] = f'{r.status_code}: {r.text[:200]}'
            return None
        j = r.json()
        open(salida, 'wb').write(base64.b64decode(j['audio_base64']))
        al = j.get('alignment') or j.get('normalized_alignment') or {}
        chars = al.get('characters') or []
        ini = al.get('character_start_times_seconds') or []
        fin = al.get('character_end_times_seconds') or []
        palabras, cur, t0, t1 = [], '', None, None
        for c, a, b in zip(chars, ini, fin):
            if c.isspace():
                if cur:
                    palabras.append((t0, t1, cur)); cur = ''
                continue
            if not cur:
                t0 = a
            cur += c; t1 = b
        if cur:
            palabras.append((t0, t1, cur))
        palabras = [(a, b, re.sub(r'[^\w¿?¡!.,;:%$áéíóúüñÁÉÍÓÚÜÑ\'-]', '', w)) for a, b, w in palabras]
        dur = duracion(salida)
        return (palabras, dur) if palabras and dur > 1 else None
    except Exception as e:
        print('ElevenLabs:', e, file=sys.stderr)
        ELEVEN_ERROR[0] = str(e)[:200]
        return None


ELEVEN_ERROR = ['']


def sintetizar(texto, salida, voz=None, ritmo=None):
    texto = limpiar(texto)
    res = elevenlabs(texto, salida)
    if res:
        return res, salida
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
