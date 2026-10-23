import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import wave
from datetime import date
from pathlib import Path

import edge_tts
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent
W, H = 1080, 1920
VOICE = "es-VE-SebastianNeural"
PLAY_URL = "https://play.google.com/store/apps/details?id=com.santabiblia.santa_biblia"
CTA_TEXTO = "¿Quieres aprender más de la Biblia? Descarga Biblia gratis desde el enlace de la biografía."


def fuente(size, negrita=True):
    nombres = [
        "C:/Windows/Fonts/segoeuib.ttf" if negrita else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if negrita else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for n in nombres:
        if os.path.exists(n):
            return ImageFont.truetype(n, size)
    return ImageFont.load_default()


def envolver(texto, fuente_obj, max_ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if fuente_obj.getlength(prueba) <= max_ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def fondo(degradado):
    img = Image.new("RGB", (W, H))
    px = img.load()
    (r1, g1, b1), (r2, g2, b2) = degradado
    for y in range(H):
        t = y / H
        t = t * t * (3 - 2 * t)
        color = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
        for x in range(W):
            px[x, y] = color
    overlay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(overlay)
    d.ellipse([-W * 0.3, H * 0.25, W * 1.3, H * 0.95], fill=70)
    overlay = overlay.filter(ImageFilter.GaussianBlur(180))
    img = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, overlay.point(lambda v: v // 4))
    return img


def diamante(d, cx, cy, tam, color):
    d.polygon([(cx, cy - tam), (cx + tam, cy), (cx, cy + tam), (cx - tam, cy)], fill=color)


def marca_superior(d):
    marca = fuente(46)
    d.text((W // 2, 160), "BIBLIA+", font=marca, fill=(200, 180, 120), anchor="mm")
    ancho = marca.getlength("BIBLIA+") / 2
    diamante(d, W // 2 - ancho - 40, 160, 12, (200, 180, 120))
    diamante(d, W // 2 + ancho + 40, 160, 12, (200, 180, 120))


def render_versiculo(ref, texto):
    img = fondo(((18, 30, 68), (75, 20, 90)))
    d = ImageDraw.Draw(img)
    marca_superior(d)
    cuerpo = fuente(64)
    lineas = envolver(f"“{texto}”", cuerpo, W - 160)
    while len(lineas) * 82 > H - 560 and cuerpo.size > 40:
        cuerpo = fuente(cuerpo.size - 4)
        lineas = envolver(f"“{texto}”", cuerpo, W - 160)
    y = H // 2 - len(lineas) * 41 - 40
    for linea in lineas:
        d.text((W // 2, y), linea, font=cuerpo, fill=(245, 242, 232), anchor="mm")
        y += 82
    fref = fuente(52)
    d.text((W // 2, y + 60), ref, font=fref, fill=(212, 175, 90), anchor="mm")
    return img


def render_cta():
    img = fondo(((15, 25, 60), (120, 40, 30)))
    d = ImageDraw.Draw(img)
    marca_superior(d)
    grande = fuente(72)
    lineas = envolver("¿Quieres aprender más de la Biblia?", grande, W - 160)
    y = H // 2 - 220
    for linea in lineas:
        d.text((W // 2, y), linea, font=grande, fill=(245, 242, 232), anchor="mm")
        y += 92
    botón = fuente(60)
    d.rounded_rectangle([W // 2 - 340, y + 50, W // 2 + 340, y + 170], radius=28, fill=(30, 160, 80))
    d.text((W // 2, y + 110), "Descarga Biblia+", font=botón, fill=(255, 255, 255), anchor="mm")
    enlace = fuente(42)
    d.text((W // 2, y + 240), "Enlace en la biografía", font=enlace, fill=(212, 175, 90), anchor="mm")
    return img


async def tts(texto, ruta_mp3):
    comunicado = edge_tts.Communicate(texto, VOICE, rate="-5%")
    await comunicado.save(str(ruta_mp3))


def duracion_mp3(ruta):
    out = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(ruta)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for linea in (out.stderr or "").splitlines():
        if "Duration" in linea:
            partes = linea.split("Duration:")[1].split(",")[0].strip()
            h, m, s = partes.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 5.0


def generar_musica(ruta_wav, segundos, bpm=60):
    rate = 44100
    n = int(rate * segundos)
    t = np.linspace(0, segundos, n, False)
    acordes = [
        [220.00, 261.63, 329.63],
        [174.61, 220.00, 261.63],
        [196.00, 246.94, 293.66],
        [164.81, 196.00, 246.94],
    ]
    dur_acorde = 60 / bpm * 4
    audio = np.zeros(n)
    for i, f0 in enumerate(t):
        idx = int(i / rate / dur_acorde) % len(acordes)
        senal = 0.0
        for freq in acordes[idx]:
            senal += np.sin(2 * math.pi * freq * i / rate)
            senal += 0.35 * np.sin(2 * math.pi * freq * 2 * i / rate)
        env = 0.25 + 0.08 * math.sin(2 * math.pi * 0.08 * i / rate)
        audio[int(i)] = senal * env
    audio = audio / np.max(np.abs(audio)) * 0.45
    ruido = np.random.normal(0, 0.008, n)
    audio = audio + ruido
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(str(ruta_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def ffmpeg(*args):
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run([exe, "-y", *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-3000:] if r.stderr else "ffmpeg error")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", default=str(ROOT / "media"))
    parser.add_argument("--nombre", default=None)
    args = parser.parse_args()

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "build"
    tmp.mkdir(exist_ok=True)

    versos = json.loads((ROOT / "verses.json").read_text(encoding="utf-8"))
    estado_path = ROOT / "estado.json"
    ultimo = -1
    if estado_path.exists():
        ultimo = json.loads(estado_path.read_text(encoding="utf-8")).get("ultimo", -1)
    indice = (ultimo + 1) % len(versos)
    estado_path.write_text(json.dumps({"ultimo": indice}), encoding="utf-8")
    verso = versos[indice]
    print(f"Versículo {indice + 1}/{len(versos)}: {verso['ref']}")

    img_v = render_versiculo(verso["ref"], verso["texto"])
    img_c = render_cta()
    p_v = tmp / "versiculo.png"
    p_c = tmp / "cta.png"
    img_v.save(p_v)
    img_c.save(p_c)

    p_voz_v = tmp / "voz_versiculo.mp3"
    p_voz_c = tmp / "voz_cta.mp3"
    asyncio.run(tts(f"{verso['texto']}. {verso['ref']}.", p_voz_v))
    asyncio.run(tts(CTA_TEXTO, p_voz_c))

    dur_v = max(duracion_mp3(p_voz_v) + 1.8, 12.0)
    dur_c = duracion_mp3(p_voz_c) + 2.0
    total = dur_v + dur_c

    p_musica = tmp / "musica.wav"
    generar_musica(p_musica, total + 1)

    nombre = args.nombre or f"reel_{date.today().isoformat()}"
    p_video = salida / f"{nombre}.mp4"

    ffmpeg(
        "-loop", "1", "-t", f"{dur_v:.2f}", "-i", p_v,
        "-loop", "1", "-t", f"{dur_c:.2f}", "-i", p_c,
        "-i", p_voz_v, "-i", p_voz_c, "-i", p_musica,
        "-filter_complex",
        (
            f"[0:v]fps=30,format=yuv420p,settb=AVTB[v0];"
            f"[1:v]fps=30,format=yuv420p,settb=AVTB[v1];"
            f"[v0][v1]concat=n=2:v=1:a=0,format=yuv420p[v];"
            f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur={dur_v:.2f}[a0];"
            f"[3:a]aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur={dur_c:.2f}[a1];"
            f"[a0][a1]concat=n=2:v=0:a=1[voz];"
            f"[4:a]aformat=sample_rates=44100:channel_layouts=stereo,aloop=loop=-1:size=2e9,volume=1.4[mus];"
            f"[voz][mus]amix=inputs=2:duration=first:dropout_transition=3,"
            f"volume=1.0,afade=t=out:st={total - 1.2:.2f}:d=1.2[a]"
        ),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{total:.2f}",
        "-movflags", "+faststart",
        p_video,
    )

    caption = (
        f"{verso['texto']}\n\n-- {verso['ref']} --\n\n"
        f"Descarga Biblia+ gratis. Enlace en la biografía.\n\n"
        f"#biblia #jesus #fe #cristiano #palabradedios #versiculo #dios"
    )
    (tmp / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"VIDEO: {p_video}")
    print(f"DURACION: {total:.1f}s")


if __name__ == "__main__":
    main()
