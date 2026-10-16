import os, re, sys, requests
def video_embebible(kind, vid):
    """True si el video se puede reproducir dentro de nuestra página (algunos solo dejan verse en su sitio)."""
    site = os.environ.get('SITE', 'https://guayabailustrada.com.mx') + '/'
    try:
        if kind == 'vm':
            r = requests.get(f'https://player.vimeo.com/video/{vid}', headers={'Referer': site, 'User-Agent': 'Mozilla/5.0'}, timeout=20)
            t = r.text.lower()
            return r.status_code == 200 and 'privacy settings' not in t and 'configuración de privacidad' not in t \
                and 'cannot be played here' not in t and '"view":7' not in t
        r = requests.get('https://www.youtube.com/oembed', params={'url': f'https://www.youtube.com/watch?v={vid}', 'format': 'json'}, timeout=20)
        if r.status_code != 200:
            return False
        e = requests.get(f'https://www.youtube.com/embed/{vid}', headers={'Referer': site, 'User-Agent': 'Mozilla/5.0'}, timeout=20).text
        return 'playabilityStatus' not in e or '"status":"OK"' in e or 'UNPLAYABLE' not in e
    except Exception as ex:
        print('Revisión de video:', ex, file=sys.stderr)
        return True   # si no se pudo revisar, no lo quitamos


