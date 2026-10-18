import requests, re
H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}
b='https://invidious.f5.si'
j=requests.get(f'{b}/api/v1/videos/AzErJdWUDTE',params={'local':'true'},headers=H,timeout=30).json()
for f in (j.get('formatStreams',[])+j.get('adaptiveFormats',[]))[:6]:
    u=f['url']; u=b+u if u.startswith('/') else u
    for hdr in ({}, {'Range':'bytes=0-'}):
        try:
            r=requests.get(u,headers={**H,**hdr},timeout=30,stream=True,allow_redirects=True)
            print(f.get('qualityLabel'), f.get('type','')[:20], hdr, r.status_code, r.headers.get('content-type'), r.headers.get('content-length'), r.url[:90])
        except Exception as e: print('ERR',str(e)[:100])
print(u[:200])
# dash / latest_version endpoint
for q in ('/latest_version?id=AzErJdWUDTE&itag=18&local=true','/latest_version?id=AzErJdWUDTE&itag=137&local=true'):
    r=requests.get(b+q,headers=H,timeout=30,stream=True); print(q, r.status_code, r.headers.get('content-type'), r.headers.get('content-length'))
