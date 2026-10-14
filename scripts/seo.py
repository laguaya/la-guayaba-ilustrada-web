"""SEO, GEO y AEO de La Guayaba Ilustrada.

Genera, a partir de posts.js e index.html:
  notas/<id>.html   una página real por nota (la leen Google y las IA sin JavaScript)
  precios.html      lista de precios en HTML plano
  sitemap.xml, robots.txt, feed.xml (RSS), llms.txt
  datos estructurados (JSON-LD) dentro de index.html y blog.html

Uso: python scripts/seo.py   (lo corre GitHub cada vez que cambia posts.js o index.html)
"""
import html, json, os, re, subprocess, glob
from datetime import datetime

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://guayabailustrada.com.mx'
NAME = 'La Guayaba Ilustrada'
PHONE = '+527209097907'
IG = 'https://instagram.com/guayabailustrada'
FB = 'https://www.facebook.com/guayabailustrada'
MES = {m: i + 1 for i, m in enumerate(['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'])}
e = lambda s: html.escape(str(s or ''), quote=True)
strip = lambda s: re.sub(r'<[^>]+>', '', str(s or ''))


def p(*a):
    return os.path.join(R, *a)


def node(js):
    return json.loads(subprocess.check_output(['node', '-e', js], cwd=R))


def iso(d):
    m = re.match(r'(\d{1,2})\s+([a-zé]{3})\w*\.?\s+(\d{4})', (d or '').lower())
    if not m:
        return datetime.now().strftime('%Y-%m-%dT09:00:00-06:00')
    return f'{int(m[3]):04d}-{MES.get(m[2], 1):02d}-{int(m[1]):02d}T09:00:00-06:00'


def money(n):
    return '${:,.0f}'.format(n)


def label(r):
    if r[2] is None:
        return r[5] if len(r) > 5 else 'A cotizar'
    return ('Desde ' if len(r) > 3 and r[3] else '') + money(r[2]) + (' ' + r[4] if len(r) > 4 and r[4] else '')


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + '</script>'


def block(src, tag, content):
    """Reemplaza lo que hay entre <!--seo:tag--> y <!--/seo:tag-->."""
    a, b = f'<!--seo:{tag}-->', f'<!--/seo:{tag}-->'
    new = a + content + b
    if a in src:
        return re.sub(re.escape(a) + '.*?' + re.escape(b), lambda _: new, src, flags=re.S)
    if '</head>' in src:
        return src.replace('</head>', new + '\n</head>', 1)
    return re.sub(r'(<link rel="canonical"[^>]*>)', lambda m: m.group(1) + '\n' + new, src, count=1)


def write(path, txt):
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if old != txt:
        open(path, 'w', encoding='utf-8').write(txt)


# ---------- datos ----------
POSTS = node("global.window={};require('./posts.js');process.stdout.write(JSON.stringify(window.POSTS||[]))")
SVC = node("const s=require('fs').readFileSync('index.html','utf8');const m=s.match(/const SVC=(\\[[\\s\\S]*?\\n\\]);/);process.stdout.write(JSON.stringify(eval(m[1])))")

ORG = {
    '@type': ['ProfessionalService', 'LocalBusiness'], '@id': SITE + '/#negocio', 'name': NAME,
    'alternateName': ['LG.I', 'Guayaba Ilustrada'], 'url': SITE + '/',
    'logo': SITE + '/assets/icon-512.png', 'image': SITE + '/assets/icon-512.png',
    'description': 'Agencia creativa en Cuernavaca, Morelos: branding, páginas web, diseño gráfico, video, fotografía, motion graphics, 3D y contenido con inteligencia artificial.',
    'telephone': PHONE, 'email': 'hola@guayabailustrada.com.mx', 'priceRange': '$$',
    'address': {'@type': 'PostalAddress', 'addressLocality': 'Cuernavaca', 'addressRegion': 'Morelos', 'addressCountry': 'MX'},
    'areaServed': [{'@type': 'City', 'name': 'Cuernavaca'}, {'@type': 'State', 'name': 'Morelos'}, {'@type': 'Country', 'name': 'México'}],
    'sameAs': [IG, FB],
    'founder': {'@type': 'Person', '@id': SITE + '/#sergio', 'name': 'Sergio Enrique Martínez Toledo', 'jobTitle': 'Director creativo',
                'alumniOf': 'Universidad Autónoma del Estado de Morelos'},
    'knowsAbout': ['Branding', 'Diseño web', 'Diseño gráfico', 'Producción de video', 'Fotografía de producto', 'Motion graphics',
                   'Modelado 3D', 'Inteligencia artificial generativa', 'Marketing de contenidos', 'Neuromarketing'],
    'hasOfferCatalog': {'@type': 'OfferCatalog', 'name': 'Servicios y precios', 'itemListElement': [
        {'@type': 'OfferCatalog', 'name': s['t'], 'description': s['d'], 'itemListElement': [
            {'@type': 'Offer', 'itemOffered': {'@type': 'Service', 'name': r[0], 'description': r[1], 'serviceType': s['t']},
             **({'priceSpecification': {'@type': 'PriceSpecification', 'price': r[2], 'priceCurrency': 'MXN',
                                        **({'minPrice': r[2]} if len(r) > 3 and r[3] else {})}} if r[2] is not None else {})}
            for r in s['pr']]} for s in SVC]},
}
WEBSITE = {'@type': 'WebSite', '@id': SITE + '/#web', 'url': SITE + '/', 'name': NAME, 'inLanguage': 'es-MX', 'publisher': {'@id': SITE + '/#negocio'}}


def faq_items():
    g = {s['k']: s for s in SVC}
    def rows(k, n=None):
        return ', '.join(f"{r[0].lower()} {label(r).lower()}" for r in g[k]['pr'][:n])
    return [
        ('¿Cuánto cuesta una página web en Cuernavaca?',
         f"En La Guayaba Ilustrada los precios de diseño web son: {rows('web')}. Todas las páginas incluyen botón de WhatsApp."),
        ('¿Cuánto cuesta un logotipo o una identidad de marca?', f"{rows('brand')}. El precio se confirma después del diagnóstico de tu marca."),
        ('¿Tienen planes mensuales para redes sociales?',
         'Sí. Plan Esencial $6,500 al mes, plan Profesional $12,500 al mes y plan Marca completa $22,000 al mes, sin conteo de piezas. '
         'El contrato mínimo es de 3 meses, hay 10% de descuento pagando 6 meses y se cancela con 30 días de aviso.'),
        ('¿Hacen fotos y videos con inteligencia artificial?', f"Sí: {rows('ia')}. También hacemos video 100% con IA y locución con IA."),
        ('¿Cuánto cuesta un video para redes o un comercial?', f"{rows('video', 4)}."),
        ('¿Los precios incluyen IVA?', 'No. Los precios son más IVA si necesitas factura.'),
        ('¿Garantizan ventas o clientes?',
         'No. Somos una agencia creativa: creamos tu identidad y tu contenido visual. Podemos configurar tu publicidad pagada como servicio adicional '
         '($2,500 al mes más el presupuesto que tú definas), pero no garantizamos ventas ni número de clientes.'),
        ('¿Cómo cotizo un proyecto?', 'Usa el cotizador de la página para armar tu proyecto y enviarlo por WhatsApp, o escríbenos directo al WhatsApp 720 909 7907.'),
    ]


def faq_ld():
    return {'@type': 'FAQPage', '@id': SITE + '/#faq', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq_items()]}


def faq_html():
    return '\n'.join(f'<details class="qa"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faq_items())


def article_ld(n, url):
    img = n['img'].split('?')[0]
    return {'@context': 'https://schema.org', '@graph': [
        {'@type': 'NewsArticle', '@id': url + '#nota', 'mainEntityOfPage': url, 'headline': strip(n['t'])[:110],
         'description': strip(n.get('x')), 'image': [SITE + '/' + img], 'datePublished': iso(n.get('d')), 'dateModified': iso(n.get('d')),
         'inLanguage': 'es-MX', 'articleSection': n.get('k', 'Noticias'),
         'author': {'@type': 'Organization', 'name': NAME, 'url': SITE + '/'}, 'publisher': {'@id': SITE + '/#negocio'},
         **({'isBasedOn': n['src']} if n.get('src') else {})},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': SITE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Noticias', 'item': SITE + '/blog'},
            {'@type': 'ListItem', 'position': 3, 'name': strip(n['t']), 'item': url}]},
        {'@type': ['ProfessionalService', 'LocalBusiness'], '@id': SITE + '/#negocio', 'name': NAME,
                                              'url': SITE + '/', 'logo': SITE + '/assets/icon-512.png', 'telephone': PHONE,
                                              'address': ORG['address'], 'sameAs': [IG, FB]}]}


def head_meta(title, desc, url, kind='website', image=None, extra=''):
    t = [f'<title>{e(title)}</title>', f'<meta name="description" content="{e(desc)}">', f'<link rel="canonical" href="{url}">',
         f'<meta property="og:type" content="{kind}">', f'<meta property="og:site_name" content="{NAME}">', '<meta property="og:locale" content="es_MX">',
         f'<meta property="og:title" content="{e(title)}">', f'<meta property="og:description" content="{e(desc)}">', f'<meta property="og:url" content="{url}">']
    if image:
        t += [f'<meta property="og:image" content="{image}">', '<meta name="twitter:card" content="summary_large_image">']
    else:
        t.append('<meta name="twitter:card" content="summary">')
    return '\n'.join(t) + extra


HEAD_RE = re.compile(r'<title>.*?<meta name="twitter:card" content="[^"]*">', re.S)


def from_template(tpl, meta, main_html, base=True, keep_scripts=True, note_id=None):
    s = HEAD_RE.sub(lambda _: meta, tpl, count=1)
    s = re.sub(r'<!--seo:ld-->.*?<!--/seo:ld-->\n?', '', s, flags=re.S)
    if base:
        s = s.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="/">', 1)
    s = s.replace('<main id="view"></main>', f'<main id="view">{main_html}</main>', 1)
    if note_id:
        s = s.replace('<script src="posts.js', f'<script>window.NOTE_ID={json.dumps(note_id)}</script>\n<script src="posts.js', 1)
    if not keep_scripts:
        s = re.sub(r'<script src="posts\.js[^\n]*\n', '', s)
        s = re.sub(r'<script>\nconst P=window\.POSTS.*?\nroute\(\);\n</script>\n', '', s, flags=re.S)
    return s


def static_article(n):
    body = ''.join(f'<p>{x}</p>' for x in n.get('b', []))
    g = ''.join(f'<figure><img src="{e((x if isinstance(x, str) else x["s"]))}" alt="{e(n["t"])}" loading="lazy"></figure>' for x in n.get('g', []))
    src = f'<p class="source">Fuente: <a href="{e(n["src"])}" rel="noopener">{e(n.get("sn") or n["src"])}</a></p>' if n.get('src') else ''
    return (f'<article class="article"><a class="cta light sm back" href="blog">Volver a Noticias</a>'
            f'<span class="kind" style="background:{e(n.get("c"))}">{e(n.get("k"))}</span><time datetime="{iso(n.get("d"))[:10]}">{e(n.get("d"))}</time>'
            f'<h1>{n["t"]}</h1><p class="dek">{n.get("x", "")}</p><span class="by">Por La Guayaba Ilustrada</span>'
            f'<div class="cover"><img src="{e(n["img"])}" alt="{e(n.get("alt"))}"></div>'
            f'<div class="body">{body}</div>{("<div class=gal>" + g + "</div>") if g else ""}{src}</article>')


def main():
    tpl = open(p('blog.html'), encoding='utf-8').read()
    os.makedirs(p('notas'), exist_ok=True)
    keep = set()
    for n in POSTS:
        url = f'{SITE}/notas/{n["id"]}'
        img = SITE + '/' + n['img'].split('?')[0]
        meta = head_meta(strip(n['t']) + ' · ' + NAME, strip(n.get('x')), url, 'article', img,
                         f'\n<meta property="article:published_time" content="{iso(n.get("d"))}">'
                         f'\n<meta property="article:section" content="{e(n.get("k"))}">\n' + ld(article_ld(n, url)))
        f = p('notas', n['id'] + '.html'); keep.add(f)
        write(f, from_template(tpl, meta, static_article(n), note_id=n['id']))
    for f in glob.glob(p('notas', '*.html')):
        if f not in keep:
            os.remove(f)

    # precios.html
    secs = ''.join(
        f'<section class="pz"><h2>{e(s["t"])}</h2><p class="pzd">{e(s["d"])}</p><ul class="prices">' +
        ''.join(f'<li><span><b>{e(r[0])}</b><small>{e(r[1])}</small></span><em>{e(label(r))}</em></li>' for r in s['pr']) +
        '</ul></section>' for s in SVC)
    css = ('<style>.pzwrap{max-width:860px;margin:0 auto;padding:40px 0;display:flex;flex-direction:column;gap:34px}'
           '.pzwrap h1{font-weight:900;font-size:clamp(36px,5vw,64px);line-height:1;letter-spacing:-.03em}.pz h2{font-weight:900;font-size:26px}'
           '.pzd{color:var(--gray);margin:4px 0 12px}.prices{list-style:none;margin:0;padding:6px 22px;border:1.5px solid var(--line);border-radius:24px}'
           '.prices li{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 0;border-bottom:1.5px solid var(--line)}'
           '.prices li:last-child{border-bottom:0}.prices b{display:block}.prices small{display:block;color:var(--gray);font-size:14px}'
           '.prices em{font-style:normal;font-weight:900;white-space:nowrap}.qa{border-bottom:1.5px solid var(--line);padding:16px 0}'
           '.qa summary{font-weight:700;cursor:pointer}.qa p{color:var(--gray);margin-top:8px}</style>')
    main_p = (f'<div class="pzwrap"><span class="eyebrow">Precios 2026</span><h1>Precios de branding, diseño web, video y contenido en Cuernavaca.</h1>'
              f'<p>Precios en pesos mexicanos, más IVA si necesitas factura. Arma tu proyecto en el <a href="index.html#cotizador">cotizador</a> '
              f'o escríbenos por <a href="https://wa.me/527209097907">WhatsApp</a>.</p>{secs}'
              f'<section class="pz"><h2>Preguntas frecuentes</h2>{faq_html()}</section></div>')
    meta = head_meta('Precios de diseño web, branding y video en Cuernavaca · ' + NAME,
                     'Lista de precios 2026 de La Guayaba Ilustrada: páginas web desde $4,500, logotipo desde $6,500, reels desde $1,200, planes de redes desde $6,500 al mes. Cuernavaca, Morelos.',
                     SITE + '/precios', extra='\n' + ld({'@context': 'https://schema.org', '@graph': [ORG, WEBSITE, faq_ld()]}))
    pr = from_template(tpl, meta, main_p, base=False, keep_scripts=False).replace('</style>', '</style>' + css, 1)
    pr = pr.replace('aria-current="page"', '')
    write(p('precios.html'), pr)

    # index.html y blog.html: datos estructurados
    idx = open(p('index.html'), encoding='utf-8').read()
    idx = block(idx, 'ld', ld({'@context': 'https://schema.org', '@graph': [ORG, WEBSITE, faq_ld()]}))
    idx = block(idx, 'faq', faq_html()) if '<!--seo:faq-->' in idx else idx
    write(p('index.html'), idx)
    blog = open(p('blog.html'), encoding='utf-8').read()
    blog = block(blog, 'ld', ld({'@context': 'https://schema.org', '@graph': [
        {'@type': 'Blog', '@id': SITE + '/blog#blog', 'url': SITE + '/blog', 'name': 'Blog de ' + NAME, 'inLanguage': 'es-MX',
         'publisher': {'@id': SITE + '/#negocio'},
         'blogPost': [{'@type': 'BlogPosting', 'headline': strip(n['t'])[:110], 'url': f'{SITE}/notas/{n["id"]}', 'datePublished': iso(n.get('d'))} for n in POSTS[:20]]},
        {'@type': 'Organization', '@id': SITE + '/#negocio', 'name': NAME, 'url': SITE + '/', 'logo': SITE + '/assets/icon-512.png'}]}))
    write(p('blog.html'), blog)

    # sitemap, robots, rss, llms
    today = datetime.now().strftime('%Y-%m-%d')
    urls = [(SITE + '/', today, '1.0'), (SITE + '/precios', today, '0.9'), (SITE + '/blog', iso(POSTS[0]['d'])[:10] if POSTS else today, '0.8')]
    urls += [(f'{SITE}/notas/{n["id"]}', iso(n.get('d'))[:10], '0.6') for n in POSTS]
    write(p('sitemap.xml'), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          ''.join(f'  <url><loc>{u}</loc><lastmod>{d}</lastmod><priority>{pr_}</priority></url>\n' for u, d, pr_ in urls) + '</urlset>\n')
    write(p('robots.txt'), f'User-agent: *\nAllow: /\nDisallow: /drafts/\nDisallow: /inbox/\nDisallow: /scripts/\nDisallow: /worker/\n\n'
                           f'Sitemap: {SITE}/sitemap.xml\n')
    rfc = lambda d: datetime.fromisoformat(iso(d)).strftime('%a, %d %b %Y %H:%M:%S -0600')
    write(p('feed.xml'), '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
          f'<title>{NAME} · Noticias</title><link>{SITE}/blog</link><description>Noticias de publicidad, diseño, marcas y redes sociales.</description>'
          f'<language>es-MX</language><atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>' +
          ''.join(f'<item><title>{e(strip(n["t"]))}</title><link>{SITE}/notas/{n["id"]}</link><guid>{SITE}/notas/{n["id"]}</guid>'
                  f'<pubDate>{rfc(n.get("d"))}</pubDate><category>{e(n.get("k"))}</category><description>{e(strip(n.get("x")))}</description></item>'
                  for n in POSTS[:30]) + '</channel></rss>\n')
    lines = [f'# {NAME}', '',
             '> Agencia creativa independiente en Cuernavaca, Morelos, México. Branding, páginas web, diseño gráfico, video y locución, '
             'fotografía, motion graphics, modelado 3D y contenido con inteligencia artificial. Director creativo: Sergio Enrique Martínez Toledo.', '',
             f'- Sitio: {SITE}/', f'- WhatsApp: 720 909 7907 (https://wa.me/527209097907)', '- Correo: hola@guayabailustrada.com.mx', f'- Instagram: {IG}', f'- Facebook: {FB}', '- Instagram de noticias (Newsbrand): https://www.instagram.com/lgi.newsbrand/', '- Ubicación: Cuernavaca, Morelos, México', '',
             '## Servicios y precios (MXN, más IVA si requieres factura)', '']
    for s in SVC:
        lines.append(f'### {s["t"]}')
        lines += [f'- {r[0]}: {label(r)}. {r[1]}.' for r in s['pr']]
        lines.append('')
    lines += ['### Planes mensuales', '- Esencial: $6,500 al mes', '- Profesional: $12,500 al mes', '- Marca completa: $22,000 al mes',
              '- Contrato mínimo de 3 meses, 10% de descuento pagando 6 meses, cancelación con 30 días de aviso.', '',
              '## Preguntas frecuentes', ''] + [f'**{q}** {a}\n' for q, a in faq_items()] + \
             ['## Páginas', f'- [Precios]({SITE}/precios)', f'- [Noticias]({SITE}/blog)', f'- [RSS]({SITE}/feed.xml)', '', '## Notas recientes'] + \
             [f'- [{strip(n["t"])}]({SITE}/notas/{n["id"]}): {strip(n.get("x"))}' for n in POSTS[:20]]
    write(p('llms.txt'), '\n'.join(lines) + '\n')
    print(f'SEO listo: {len(POSTS)} notas')


if __name__ == '__main__':
    main()
