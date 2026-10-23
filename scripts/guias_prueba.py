"""Arma las Guías de drafts/guias_prueba/*.json en assets/prueba/<id>/ (video con voz y, si es calendario, carrusel).
No manda nada a Telegram: es solo para revisar antes de aprobar."""
import sys, os, json, glob
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import guias_estilos as E
solo = sys.argv[1:]
for p in sorted(glob.glob(os.path.join(R, 'drafts', 'guias_prueba', '*.json'))):
    d = json.load(open(p))
    if solo and d['id'] not in solo: continue
    out = os.path.join(R, 'assets', 'prueba', d['id']); os.makedirs(out, exist_ok=True)
    try:
        if d.get('estilo') == 'calendario':
            E.carrusel(d, os.path.join(out, 'carrusel'))
        E.make(d, os.path.join(out, 'reel.mp4'))
        print('listo', d['id'])
    except Exception:
        import traceback
        open(os.path.join(R, 'assets', 'prueba', 'log.txt'), 'a').write(d['id'] + '\n' + traceback.format_exc() + '\n')
        traceback.print_exc()
