"""Publicación de Reels en TikTok (Content Posting API, Direct Post con archivo).

Conexión (una sola vez): Sergio escribe "tiktok" al bot -> recibe un link -> autoriza en TikTok -> la página
guayabailustrada.com.mx/tiktok/ le muestra un mensaje "tiktok <código>" -> lo manda al bot -> canjear().
Los permisos (tokens) se guardan CIFRADOS en drafts/.tiktok.enc con una llave que sale del Client secret
(secreto de GitHub), así que en el repo no hay nada legible.
"""
import base64, hashlib, json, os, time, urllib.parse
import requests

API = 'https://open.tiktokapis.com/v2'
REDIRECT = 'https://guayabailustrada.com.mx/tiktok/'
ARCHIVO = 'drafts/.tiktok.enc'
SCOPES = 'user.info.basic,video.upload,video.publish'


def configurado():
    return bool(os.environ.get('TIKTOK_CLIENT_KEY') and os.environ.get('TIKTOK_CLIENT_SECRET'))


def _fernet():
    from cryptography.fernet import Fernet
    k = hashlib.sha256(('lgi-tiktok:' + os.environ['TIKTOK_CLIENT_SECRET'].strip()).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(k))


def _guardar(d):
    open(ARCHIVO, 'wb').write(_fernet().encrypt(json.dumps(d).encode()))


def _cargar():
    if not os.path.exists(ARCHIVO):
        return None
    try:
        return json.loads(_fernet().decrypt(open(ARCHIVO, 'rb').read()))
    except Exception:
        return None


def conectado():
    return configurado() and bool(_cargar())


def link_autorizacion():
    q = {'client_key': os.environ['TIKTOK_CLIENT_KEY'].strip(), 'scope': SCOPES, 'response_type': 'code',
         'redirect_uri': REDIRECT, 'state': hashlib.sha1(str(time.time()).encode()).hexdigest()[:16]}
    return 'https://www.tiktok.com/v2/auth/authorize/?' + urllib.parse.urlencode(q)


def _token_req(data):
    data.update(client_key=os.environ['TIKTOK_CLIENT_KEY'].strip(), client_secret=os.environ['TIKTOK_CLIENT_SECRET'].strip())
    r = requests.post(f'{API}/oauth/token/', data=data, timeout=60,
                      headers={'Content-Type': 'application/x-www-form-urlencoded'}).json()
    if not r.get('access_token'):
        raise RuntimeError(r.get('error_description') or r.get('error') or r)
    r['vence'] = time.time() + int(r.get('expires_in', 86400)) - 300
    return r


def canjear(code):
    """Cambia el código de autorización por los permisos y regresa el nombre de la cuenta."""
    code = urllib.parse.unquote(code.strip())
    t = _token_req({'code': code, 'grant_type': 'authorization_code', 'redirect_uri': REDIRECT})
    _guardar(t)
    try:
        u = requests.get(f'{API}/user/info/', params={'fields': 'display_name,username'},
                         headers={'Authorization': 'Bearer ' + t['access_token']}, timeout=30).json()
        return (u.get('data') or {}).get('user', {}).get('username') or (u.get('data') or {}).get('user', {}).get('display_name') or ''
    except Exception:
        return ''


def _access():
    t = _cargar()
    if not t:
        raise RuntimeError('TikTok no está conectado (escribe "tiktok" al bot)')
    if time.time() > float(t.get('vence') or 0):
        n = _token_req({'grant_type': 'refresh_token', 'refresh_token': t['refresh_token']})
        t.update(n)
        _guardar(t)
    return t['access_token']


def _post(ruta, body, tok):
    r = requests.post(f'{API}{ruta}', json=body, timeout=60,
                      headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json; charset=UTF-8'}).json()
    err = (r.get('error') or {})
    if err.get('code') not in (None, 'ok'):
        raise RuntimeError(f"{err.get('code')}: {err.get('message')}")
    return r.get('data') or {}


def iniciar(video, caption):
    """Sube el video. Regresa (publish_id, privacidad). Solo se llama UNA vez por Reel (nunca se repite)."""
    tok = _access()
    info = _post('/post/publish/creator_info/query/', {}, tok)
    opciones = info.get('privacy_level_options') or ['SELF_ONLY']
    tam = os.path.getsize(video)
    fuente = {'source': 'FILE_UPLOAD', 'video_size': tam, 'chunk_size': tam, 'total_chunk_count': 1}
    d = None
    for priv in (['PUBLIC_TO_EVERYONE'] if 'PUBLIC_TO_EVERYONE' in opciones else []) + ['SELF_ONLY']:
        body = {'post_info': {'title': caption[:2200], 'privacy_level': priv, 'disable_duet': False,
                              'disable_comment': False, 'disable_stitch': False, 'video_cover_timestamp_ms': 1500},
                'source_info': fuente}
        try:
            d = _post('/post/publish/video/init/', body, tok)
            break
        except RuntimeError as e:
            if 'unaudited' not in str(e):
                raise
    if d is None:
        # app todavía sin aprobar y cuenta pública: TikTok solo deja mandarlo como BORRADOR a la bandeja de la app
        d = _post('/post/publish/inbox/video/init/', {'source_info': fuente}, tok)
        priv = 'BORRADOR'
    with open(video, 'rb') as f:
        r = requests.put(d['upload_url'], data=f.read(), timeout=600,
                         headers={'Content-Type': 'video/mp4', 'Content-Length': str(tam),
                                  'Content-Range': f'bytes 0-{tam - 1}/{tam}'})
    if r.status_code >= 300:
        raise RuntimeError(f'subida {r.status_code}: {r.text[:200]}')
    return d['publish_id'], priv


def estado(publish_id):
    d = _post('/post/publish/status/fetch/', {'publish_id': publish_id}, _access())
    return d.get('status'), d.get('fail_reason')


def iniciar_fotos(urls, titulo, descripcion):
    """Publicación de fotos (carrusel). TikTok las baja de la web (prefijo de URL verificado en la app)."""
    tok = _access()
    info = _post('/post/publish/creator_info/query/', {}, tok)
    opciones = info.get('privacy_level_options') or ['SELF_ONLY']
    fuente = {'source': 'PULL_FROM_URL', 'photo_cover_index': 0, 'photo_images': urls}
    for priv in (['PUBLIC_TO_EVERYONE'] if 'PUBLIC_TO_EVERYONE' in opciones else []) + ['SELF_ONLY']:
        body = {'post_info': {'title': titulo[:90], 'description': descripcion[:4000], 'privacy_level': priv,
                              'disable_comment': False, 'auto_add_music': True},
                'source_info': fuente, 'post_mode': 'DIRECT_POST', 'media_type': 'PHOTO'}
        try:
            return _post('/post/publish/content/init/', body, tok)['publish_id'], priv
        except RuntimeError as e:
            if 'unaudited' not in str(e):
                raise
    body = {'post_info': {'title': titulo[:90], 'description': descripcion[:4000]},
            'source_info': fuente, 'post_mode': 'MEDIA_UPLOAD', 'media_type': 'PHOTO'}
    return _post('/post/publish/content/init/', body, tok)['publish_id'], 'BORRADOR'
