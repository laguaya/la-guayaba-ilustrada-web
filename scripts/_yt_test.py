import requests, json
vid='AzErJdWUDTE'
H={'User-Agent':'Mozilla/5.0'}
inv=['https://inv.nadeko.net','https://invidious.nerdvpn.de','https://yewtu.be','https://invidious.f5.si','https://iv.melmac.space','https://invidious.privacyredirect.com','https://inv.tux.pizza','https://invidious.jing.rocks','https://iv.ggtyler.dev','https://invidious.reallyaweso.me']
for b in inv:
    try:
        r=requests.get(f'{b}/api/v1/videos/{vid}',params={'local':'true'},headers=H,timeout=20)
        ok = r.status_code
        fs = r.json().get('formatStreams',[]) if ok==200 else []
        u = fs[-1]['url'] if fs else ''
        if u and u.startswith('/'): u=b+u
        size=0
        if u:
            rr=requests.get(u,headers=H,timeout=30,stream=True); size=rr.status_code
        print('INV',b,ok,len(fs),size)
    except Exception as e: print('INV',b,'ERR',str(e)[:80])
pip=['https://pipedapi.kavin.rocks','https://pipedapi.adminforge.de','https://api.piped.private.coffee','https://pipedapi.reallyaweso.me','https://piped-api.lunar.icu']
for b in pip:
    try:
        r=requests.get(f'{b}/streams/{vid}',headers=H,timeout=20)
        vs=[s for s in r.json().get('videoStreams',[]) if not s.get('videoOnly')] if r.status_code==200 else []
        st=0
        if vs:
            rr=requests.get(vs[0]['url'],headers=H,timeout=30,stream=True); st=rr.status_code
        print('PIPED',b,r.status_code,len(vs),st)
    except Exception as e: print('PIPED',b,'ERR',str(e)[:80])
for b in ['https://api.cobalt.tools','https://cobalt-api.kwiatekmiki.com','https://cobalt.canine.tools']:
    try:
        r=requests.post(b+'/',json={'url':f'https://www.youtube.com/watch?v={vid}','videoQuality':'1080'},headers={**H,'Accept':'application/json','Content-Type':'application/json'},timeout=30)
        print('COBALT',b,r.status_code,r.text[:150])
    except Exception as e: print('COBALT',b,'ERR',str(e)[:80])
