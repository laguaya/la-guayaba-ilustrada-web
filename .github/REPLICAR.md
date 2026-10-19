# Cómo replicar el sistema de notas de La Guayaba Ilustrada en otro sitio

Guía para copiar este sistema a otra marca (por ejemplo Fandom Focus). Repo de referencia: https://github.com/laguaya/la-guayaba-ilustrada-web (público).

## Qué hace el sistema
1. **Redactor** (tarea programada de Claude, cada 2 horas a las 7:05, 9:05… 21:05, hora CDMX): lee `.github/redactor.md` y en cada vuelta escribe:
   - una nota para la web y el carrusel: `drafts/<id>.json`
   - un Reel de otra noticia, con video real de esa misma noticia: `drafts/reels/<id>.json`
   - luego hace push.
2. **Bot de Telegram**, en GitHub Actions (`.github/workflows/notas.yml` → `scripts/notas.py --listen`). Corre sin parar y se relanza solo. Hace esto:
   - Manda cada nota a Telegram con foto real, texto y carrusel de 4 láminas. Botones: 🌐 Solo web, 📲 Web + Instagram, 🚀 Web + Instagram + TikTok, ajustar encuadre, otras fotos y descartar.
   - Arma cada Reel en cuanto llega y lo manda **en punto**, a las 8, 10, 12, 14, 16, 18, 20 y 22 h, con el botón 📲 Subir a Instagram y TikTok.
   - Publica en la web: `posts.js` y `notas/<id>.html` con SEO (`scripts/seo.py`). Si la fuente trae video de YouTube o Vimeo, lo incrusta.
   - Publica en Instagram (Graph API). Deja al menos 8 minutos entre publicaciones, reintenta con espera si Meta bloquea y revisa que no se haya publicado antes de reintentar, para nunca duplicar.
   - Publica en TikTok (Content Posting API, `scripts/tiktok.py`). Mientras la app no esté aprobada, el video llega como borrador. El copy de TikTok se manda solo, en un mensaje aparte.
   - Recibe pedidos de Sergio: links o texto en `inbox/`, fotos, "otra imagen", `tiktok` (conectar) y `tiktok prueba`.
3. **Web estática** en Cloudflare Pages: cada push a `main` publica. Cada archivo debe pesar menos de 25 MiB.

## Archivos clave (copiar y adaptar)
| Archivo | Para qué |
|---|---|
| `scripts/notas.py` | Bot de Telegram, publicación web, Instagram, TikTok y colas |
| `scripts/reel.py` | Reel de 60 s: video real, cortes en tomas reales, voz ElevenLabs, subtítulos, música bajita y CTA |
| `scripts/voz.py` | ElevenLabs (voice id fijo, modelo eleven_v4) y alineación con faster-whisper |
| `scripts/tomas.py` | Detecta tomas del video y arma la hoja de contactos |
| `scripts/carrusel.py`, `carrusel_video.py`, `ig_estilos.py`, `portada.py`, `encuadre.py` | Carrusel fijo o animado y portada (aquí van la plantilla y los colores de la marca) |
| `scripts/fuentes.py` | Fotos y MP4 reales de la fuente |
| `scripts/seo.py` | HTML de cada nota, sitemap, feed y llms.txt |
| `scripts/tiktok.py` | OAuth (tokens cifrados en `drafts/.tiktok.enc`), video, fotos y estado |
| `.github/workflows/notas.yml` | Bot 24/7 (Python 3.12, ffmpeg, deno, yt-dlp con curl-cffi, faster-whisper, cryptography) |
| `.github/redactor.md` | Instrucciones del redactor: estilo, fuentes, Reels, SEO por red y reglas de Sergio |
| `tiktok/index.html`, `terminos.html`, `privacidad.html` | Página de retorno de TikTok y páginas legales |
| `assets/audio/musica/` | Música de fondo de los Reels |

## Secretos de GitHub del repo nuevo (los pone Sergio; nunca en el chat)
- `TELEGRAM_TOKEN`: bot nuevo creado en @BotFather. El chat id va en el workflow.
- `IG_TOKEN`, `IG_USER_ID`: cuenta de Instagram de la marca.
- `ELEVENLABS_API_KEY`: el voice id va en `scripts/voz.py`.
- `YT_COOKIES`: cookies de YouTube en formato Netscape, para que yt-dlp baje desde GitHub.
- `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`: de la app de TikTok Developers. Puede ser la misma app agregando otra Redirect URI y otro target user, o una app nueva.

## Reglas de Sergio que hay que conservar
- **Formato del Reel:**
  - Dura exactamente 60 s.
  - Todo lo que dice la voz se ve en pantalla.
  - Solo video real de esa misma noticia: nunca stock ni videos de la marca sobre otro tema.
  - Cortes limpios sin efectos y tomas de al menos 1 s.
  - Sin el audio original del clip. La música va más baja que la voz y sigue hasta el minuto.
- **Voz:**
  - Sin pausas largas ni puntos suspensivos.
  - Pronunciación: en `pronunciar` solo van los nombres raros. Las palabras conocidas se escriben normal. La regla aplica solo a la voz del Reel; nunca a la web ni al carrusel.
- **Textos y publicación:**
  - Copy y hashtags distintos para cada red (web, Instagram y TikTok), pensados para SEO.
  - Nunca publicar dos veces lo mismo.
  - Los Reels salen en punto, uno por horario.

## Orden recomendado para Fandom Focus
1. Repo nuevo en GitHub, conectado a Cloudflare Pages.
2. Copiar `scripts/`, el workflow, `tiktok/` y las páginas legales.
3. Cambiar la marca:
   - colores: verde lima #CEFF00, negro y blanco
   - logo y tipografía
   - nombre de la cuenta y textos fijos
4. Reescribir `.github/redactor.md` para cine y cultura pop, con las fuentes de entretenimiento y la voz de Fandom Focus (skill "Guiones Fandom Focus").
5. Bot nuevo de Telegram y secretos.
6. Prueba de punta a punta con una nota y un Reel.
7. Tarea programada del redactor, cada 2 horas.
