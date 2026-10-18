import sys; sys.path.insert(0,'scripts')
import reel
print(reel.invidious('https://www.youtube.com/watch?v=AzErJdWUDTE','/tmp/v.mp4'))
import os; print(os.path.exists('/tmp/v.mp4') and os.path.getsize('/tmp/v.mp4'))
import voz; print(voz.alinear('drafts/voces/rivian-ghostbusters-bill-murray-halloween.mp3','Bil Mórrei volvió a cazar fantasmas')[0][:8])
