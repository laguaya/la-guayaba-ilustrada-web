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


_CFG = {}


def _eleven_config(clave):
    """Voz y modelo de ElevenLabs. La voz se busca por nombre ("Sergio noticias") si no hay ELEVENLABS_VOICE_ID;
    el modelo es el más nuevo disponible (Eleven v4) si no hay ELEVENLABS_MODEL."""
    import requests
    if _CFG:
        return _CFG['voz'], _CFG['modelo']
    h = {'xi-api-key': clave}
    voz = os.environ.get('ELEVENLABS_VOICE_ID')
    if not voz:
        nombre = os.environ.get('ELEVENLABS_VOICE_NAME', 'Sergio noticias').lower()
        try:
            r = requests.get('https://api.elevenlabs.io/v2/voices', headers=h, params={'search': nombre, 'page_size': 50}, timeout=30)
            vs = r.json().get('voices', []) if r.status_code == 200 else []
            if r.status_code != 200:
                print('ElevenLabs voces:', r.status_code, r.text[:200], file=sys.stderr)
                ELEVEN_ERROR[0] = f'voces {r.status_code}: {r.text[:150]}'
            voz = next((v['voice_id'] for v in vs if v.get('name', '').lower() == nombre), None) or \
                next((v['voice_id'] for v in vs if nombre in v.get('name', '').lower()), None)
        except Exception as e:
            print('ElevenLabs voces:', e, file=sys.stderr)
    modelo = os.environ.get('ELEVENLABS_MODEL')
    if not modelo:
        modelo = 'eleven_multilingual_v2'
        try:
            r = requests.get('https://api.elevenlabs.io/v1/models', headers=h, timeout=30)
            ids = [m.get('model_id', '') for m in r.json()] if r.status_code == 200 else []
            for preferido in ('eleven_v4', 'eleven_v3', 'eleven_multilingual_v2'):
                cand = [i for i in ids if i.startswith(preferido)]
                if cand:
                    modelo = sorted(cand, key=len)[0]
                    break
        except Exception as e:
            print('ElevenLabs modelos:', e, file=sys.stderr)
    print('ElevenLabs: voz', voz, 'modelo', modelo, file=sys.stderr)
    _CFG.update(voz=voz, modelo=modelo)
    return voz, modelo


def elevenlabs(texto, salida):
    """Voz de ElevenLabs con tiempos por letra (para los subtítulos). Regresa (palabras, duración) o None."""
    import base64, requests
    clave = os.environ.get('ELEVENLABS_API_KEY')
    if not clave:
        return None
    voz, modelo = _eleven_config(clave)
    if not voz:
        return None
    try:
        r = requests.post(f'https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps',
                          params={'output_format': 'mp3_44100_128'},
                          headers={'xi-api-key': clave, 'Content-Type': 'application/json'},
                          json={'text': texto, 'model_id': modelo,
                                'voice_settings': {'stability': float(os.environ.get('ELEVENLABS_STABILITY', '0.5')),
                                                   'similarity_boost': float(os.environ.get('ELEVENLABS_SIMILARITY', '0.75')),
                                                   'speed': float(os.environ.get('ELEVENLABS_SPEED', '1.0')),
                                                   'use_speaker_boost': True}}, timeout=180)
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


def _n(w):
    return re.sub(r'[^0-9a-záéíóúüñ]', '', w.lower())


def alinear(audio, texto):
    """Tiempos de cada palabra de `texto` en una grabación ya hecha (por ejemplo, una voz que Sergio generó en
    ElevenLabs). Usa faster-whisper para escuchar el audio y empata lo que oye con el guion; las palabras que no
    reconoce se reparten entre sus vecinas. Regresa (palabras, duración)."""
    import difflib
    texto = limpiar(texto)
    toks = texto.split()
    dur = duracion(audio)
    rec = []
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(os.environ.get('WHISPER_MODEL', 'small'), device='cpu', compute_type='int8')
        import numpy as np                          # se decodifica con ffmpeg (evita choques de versión de PyAV)
        pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', audio, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                             capture_output=True, timeout=300).stdout
        muestra = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        segs, _ = m.transcribe(muestra, language='es', word_timestamps=True, vad_filter=False)
        rec = [(w.start, w.end, w.word.strip()) for sg in segs for w in (sg.words or [])]
    except Exception as e:
        print('Alinear voz:', e, file=sys.stderr)
    if not rec:                                   # sin whisper: reparto proporcional a lo largo del audio
        pal, d = _estimado(texto)
        k = dur / max(d, 0.1)
        return [(a * k, b * k, w) for a, b, w in pal], dur
    a = [_n(t) for t in toks]
    b = [_n(w) for _, _, w in rec]
    tiempos = [None] * len(toks)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                tiempos[i1 + k] = rec[j1 + k][:2]
        elif tag == 'replace':                    # lo dijo distinto (nombres, números): reparte el tramo oído
            t0, t1 = rec[j1][0], rec[j2 - 1][1]
            paso = (t1 - t0) / (i2 - i1)
            for k in range(i2 - i1):
                tiempos[i1 + k] = (t0 + k * paso, t0 + (k + 1) * paso)
    # huecos (palabras que whisper no oyó): entre el fin de la anterior y el inicio de la siguiente
    i = 0
    while i < len(toks):
        if tiempos[i] is not None:
            i += 1; continue
        j = i
        while j < len(toks) and tiempos[j] is None:
            j += 1
        t0 = tiempos[i - 1][1] if i > 0 else 0.0
        t1 = tiempos[j][0] if j < len(toks) else dur
        paso = max(0.05, (t1 - t0) / (j - i))
        for k in range(i, j):
            tiempos[k] = (t0 + (k - i) * paso, t0 + (k - i + 1) * paso)
        i = j
    return [(s, e, w) for (s, e), w in zip(tiempos, toks)], dur


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
