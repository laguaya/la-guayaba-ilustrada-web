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
    r = requests.get('https://commons.wikimedia.org/w/api.php', params={'action': 'query', 'format': 'json', 'generator': 'search',
                     'gsrsearch': f'{q} filetype:bitmap', 'gsrnamespace': 6, 'gsrlimit': n * 2, 'prop': 'imageinfo',
                     'iiprop': 'url|extmetadata', 'iiurlwidth': 1600}, headers=UA, timeout=30)
    for p in (r.json().get('query', {}).get('pages', {}) or {}).values():
        ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {})
        lic = md.get('LicenseShortName', {}).get('value', '')
        if not re.search(r'CC0|Public domain|CC BY', lic, re.I): continue
        autor = re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', ''))[:80]
        yield ii.get('thumburl') or ii.get('url'), {'fuente': ii.get('descriptionurl'), 'autor': autor, 'licencia': lic}


def main():
    consultas = json.loads(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    for slug, q in consultas.items():
        dest = os.path.join(R, 'assets', 'libres', slug); os.makedirs(dest, exist_ok=True)
        cred, k = {}, 0
        for fuente in (openverse, commons):
            try:
                for url, meta in fuente(q, n):
                    if k >= n * 2: break
                    try:
                        b = requests.get(url, headers=UA, timeout=40).content
                        im = Image.open(BytesIO(b)).convert('RGB')
                        if min(im.size) < 700: continue
                        im.thumbnail((1600, 1600))
                        nom = f'{fuente.__name__[0]}{k}.jpg'; im.save(os.path.join(dest, nom), quality=86)
                        cred[nom] = meta; k += 1
                    except Exception as e:
                        print(slug, 'foto falló', e)
            except Exception as e:
                print(slug, fuente.__name__, 'falló', e)
        json.dump(cred, open(os.path.join(dest, 'creditos.json'), 'w'), ensure_ascii=False, indent=1)
        print(slug, k, 'fotos')


if __name__ == '__main__':
    main()
