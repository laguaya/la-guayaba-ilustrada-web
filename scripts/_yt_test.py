import sys, re; sys.path.insert(0,'scripts')
import fuentes
urls=["https://rivian.com/stories/new-software-halloween-ghostbusters-2026","https://www.topgear.com/car-news/usa/who-you-gonna-call-new-ecto-r1-rivians-ghostbusters-themed-electric-suv","https://www.kbb.com/car-news/rivian-halloween-mode-2026-goes-gangbusters-for-ghostbusters/","https://www.jalopnik.com/2281691/rivian-halloween-mode-ghostbusters-officially-licensed-movie-sounds-games/","https://www.gearpatrol.com/?p=1043629","https://www.automotiveaddicts.com/?p=124156","https://hauntedattractionnetwork.com/rivian-halloween-mode/","https://www.techradar.com/vehicle-tech/hybrid-electric-vehicles/just-silly-enough-to-be-perfect-ive-seen-rivians-ghostbusters-ecto-r1-in-action"]
for u in urls:
    try:
        h=fuentes.pagina(u)
        print(u[:60], len(h), fuentes.mp4s_de_pagina(u), sorted(set(re.findall(r'https?://[^"\'\s<>]+?\.(?:m3u8|mp4|webm)', h)))[:5], sorted(set(re.findall(r'(?:ctfassets|mux\.com|jwplayer\.com/[\w/.-]+|stream\.mux|cloudinary[^"\s]+video|brightcove)[^"\'\s<>]{0,80}', h)))[:6])
    except Exception as e: print(u[:60], 'ERR', e)
