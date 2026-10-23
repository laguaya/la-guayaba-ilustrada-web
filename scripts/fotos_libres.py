"""Busca fotos de uso libre (Openverse: CC0, dominio público y CC BY; Wikimedia Commons) y las guarda en
assets/libres/<slug>/ con sus créditos en creditos.json. Uso: python scripts/fotos_libres.py '{"slug": "consulta en inglés", ...}' [n]
"""
import sys, os, json, re, requests
from io import BytesIO
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'LGI-Guias/1.0 (laguayabailustrada@gmail.com)'}


def openverse(q, n):
    r = requests.get('https://api.openverse.org/v1/images/', params={'q': q, 'license': 'cc0,pdm,by', 'page_size': n * 2,
                     'aspect_ratio': 'tall,square,wide', 'mature': 'false'}, headers=UA, timeout=30)
    for it in r.json().get('results', []):
        yield it['url'], {'fuente': it.get('foreign_landing_url'), 'autor': it.get('creator'), 'licencia': f"{it.get('license')} {it.get('license_version') or ''}".strip()}


def commons(q, n):
    logo = q.startswith('logo:')          # "logo:Burger King" busca también SVG (Commons los entrega como PNG)
    q = q[5:] if logo else q
    r = requests.get('https://commons.wikimedia.org/w/api.php', params={'action': 'query', 'format': 'json', 'generator': 'search',
                     'gsrsearch': q if logo else f'{q} filetype:bitmap', 'gsrnamespace': 6, 'gsrlimit': n * 2, 'prop': 'imageinfo',
                     'iiprop': 'url|extmetadata', 'iiurlwidth': 1600}, headers=UA, timeout=30)
    for p in (r.json().get('query', {}).get('pages', {}) or {}).values():
        ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {})
        lic = md.get('LicenseShortName', {}).get('value', '')
        if not logo and not re.search(r'CC0|Public domain|CC BY', lic, re.I): continue
        autor = re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', ''))[:80]
        yield ii.get('thumburl') or ii.get('url'), {'fuente': ii.get('descriptionurl'), 'autor': autor, 'licencia': lic}


def main():
    consultas = json.loads(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    for slug, q in consultas.items():
        dest = os.path.join(R, 'assets', 'libres', slug); os.makedirs(dest, exist_ok=True)
        cred, k = {}, 0
        for fuente in ((commons,) if q.startswith('logo:') else (openverse, commons)):
            try:
                for url, meta in fuente(q, n):
                    if k >= n * 2: break
                    try:
                        b = requests.get(url, headers=UA, timeout=40).content
                        im = Image.open(BytesIO(b)).convert('RGB')
                        if min(im.size) < (200 if q.startswith('logo:') else 700): continue
                        im.thumbnail((1600, 1600))
                        nom = f'{fuente.__name__[0]}{k}.jpg'; im.save(os.path.join(dest, nom), quality=86)
                        cred[nom] = meta; k += 1
                    except Exception as e:
                        print(slug, 'foto falló', e)
            except Exception as e:
                print(slug, fuente.__name__, 'falló', e)
        json.dump(cred, open(os.path.join(dest, 'creditos.json'), 'w'), ensure_ascii=False, indent=1)
        print(slug, k, 'fotos')





def commons_videos(q, n, dest):
    """Videos libres de Wikimedia Commons: baja la versión 720p, recorta a 12 s y la guarda en mp4."""
    import subprocess
    r = requests.get('https://commons.wikimedia.org/w/api.php', params={'action': 'query', 'format': 'json', 'generator': 'search',
                     'gsrsearch': f'{q} filetype:video', 'gsrnamespace': 6, 'gsrlimit': n * 3, 'prop': 'videoinfo',
                     'viprop': 'url|derivatives|extmetadata|size'}, headers=UA, timeout=30)
    cred, k = {}, 0
    for p in (r.json().get('query', {}).get('pages', {}) or {}).values():
        if k >= n: break
        vi = (p.get('videoinfo') or [{}])[0]; md = vi.get('extmetadata', {})
        lic = md.get('LicenseShortName', {}).get('value', '')
        if not re.search(r'CC0|Public domain|CC BY', lic, re.I) or (vi.get('width') or 0) < 640: continue
        ders = sorted(vi.get('derivatives') or [], key=lambda d: abs((d.get('height') or 0) - 720))
        url = (ders[0]['src'] if ders else vi.get('url'))
        try:
            src = os.path.join(dest, f'tmp{k}'); open(src, 'wb').write(requests.get(url, headers=UA, timeout=120).content)
            nom = f'v{k}.mp4'
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '1', '-i', src, '-t', '12', '-an', '-vf', 'scale=-2:720',
                            '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', os.path.join(dest, nom)], check=True)
            os.remove(src)
            autor = re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', ''))[:80]
            cred[nom] = {'fuente': vi.get('descriptionurl'), 'autor': autor, 'licencia': lic, 'titulo': p.get('title')}; k += 1
        except Exception as e:
            print('video falló', e)
    return cred


def main_videos():
    consultas = json.loads(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    for slug, q in consultas.items():
        dest = os.path.join(R, 'assets', 'libres_v', slug); os.makedirs(dest, exist_ok=True)
        cred = commons_videos(q, n, dest)
        json.dump(cred, open(os.path.join(dest, 'creditos.json'), 'w'), ensure_ascii=False, indent=1)
        print(slug, len(cred), 'videos')


if __name__ == '__main__':
    main_videos() if sys.argv[1] == 'videos' else main()
