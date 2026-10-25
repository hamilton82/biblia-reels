import argparse
import asyncio
import json
import math
import os
import random
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

PALETAS = [
    ((18, 30, 68), (75, 20, 90), (100, 120, 230)),
    ((10, 38, 54), (20, 16, 50), (50, 170, 190)),
    ((48, 12, 22), (22, 15, 48), (230, 130, 70)),
    ((12, 42, 32), (10, 22, 52), (70, 205, 165)),
    ((42, 16, 62), (16, 16, 46), (185, 95, 225)),
    ((26, 30, 48), (62, 26, 62), (150, 160, 210)),
    ((52, 26, 12), (36, 12, 32), (235, 175, 85)),
    ((12, 22, 50), (32, 62, 84), (90, 205, 225)),
]

NOTAS = {
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99,
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00, "A3": 220.00, "B3": 246.94,
}
PROGRESION = [
    ["C3", "E3", "G3", "C4", "E4", "G4", "C5", "E5"],
    ["G3", "E3", "G3", "B3", "D4", "G4", "B3", "D5"],
    ["A3", "E3", "A3", "C4", "E4", "A4", "C5", "E5"],
    ["F3", "C3", "F3", "A3", "C4", "F4", "A4", "C5"],
]


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


def fondo(idx):
    (r1, g1, b1), (r2, g2, b2), (gr, gg, gb) = PALETAS[idx % len(PALETAS)]
    ty = np.linspace(0, 1, H)[:, None]
    tx = np.linspace(0, 1, W)[None, :]
    t = (0.72 * ty + 0.28 * tx) if idx % 2 else ty
    t = t * t * (3 - 2 * t)
    img = np.empty((H, W, 3), dtype=np.uint8)
    for c, (a, b) in enumerate(((r1, r2), (g1, g2), (b1, b2))):
        img[:, :, c] = (a + (b - a) * t).astype(np.uint8)
    img = Image.fromarray(img, "RGB").convert("RGBA")

    rng = random.Random(idx * 97 + 13)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for _ in range(2):
        cx, cy = rng.randint(0, W), rng.randint(int(H * 0.25), int(H * 0.85))
        radio = rng.randint(320, 560)
        alpha = rng.randint(28, 45)
        d.ellipse([cx - radio, cy - radio, cx + radio, cy + radio], fill=(gr, gg, gb, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(70))
    img = Image.alpha_composite(img, overlay)
    if idx % 3 == 0:
        estrellas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        de = ImageDraw.Draw(estrellas)
        for _ in range(120):
            x, y = rng.randint(0, W), rng.randint(int(H * 0.04), int(H * 0.30))
            r = rng.choice([1.2, 1.8, 2.4])
            a = rng.randint(60, 160)
            de.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 240, a))
        for _ in range(35):
            x, y = rng.randint(0, W), rng.randint(int(H * 0.78), int(H * 0.98))
            r = rng.choice([1.0, 1.6])
            de.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 240, rng.randint(40, 100)))
        img = Image.alpha_composite(img, estrellas)
    img = img.convert("RGB")
    return img


def diamante(d, cx, cy, tam, color):
    d.polygon([(cx, cy - tam), (cx + tam, cy), (cx, cy + tam), (cx - tam, cy)], fill=color)


def marca_superior(d):
    marca = fuente(46)
    d.text((W // 2, 160), "BIBLIA+", font=marca, fill=(200, 180, 120), anchor="mm")
    ancho = marca.getlength("BIBLIA+") / 2
    diamante(d, W // 2 - ancho - 40, 160, 12, (200, 180, 120))
    diamante(d, W // 2 + ancho + 40, 160, 12, (200, 180, 120))


def render_versiculo(ref, texto, idx):
    img = fondo(idx)
    d = ImageDraw.Draw(img)
    marca_superior(d)
    cuerpo = fuente(64)
    lineas = envolver(f"“{texto}”", cuerpo, W - 160)
    while len(lineas) * 82 > H - 560 and cuerpo.size > 40:
        cuerpo = fuente(cuerpo.size - 4)
        lineas = envolver(f"“{texto}”", cuerpo, W - 160)
    y = H // 2 - len(lineas) * 41 - 40
    for linea in lineas:
        d.text((W // 2 + 3, y + 3), linea, font=cuerpo, fill=(0, 0, 0), anchor="mm")
        d.text((W // 2, y), linea, font=cuerpo, fill=(245, 242, 232), anchor="mm")
        y += 82
    fref = fuente(52)
    d.text((W // 2, y + 60), ref, font=fref, fill=(212, 175, 90), anchor="mm")
    return img


def render_cta(idx):
    img = fondo((idx + 5) % 997)
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


def nota(freq, dur, rate, ataque=0.02, decaimiento=4.0, harmonicos=(1.0, 0.32, 0.14, 0.06)):
    n = int(rate * dur)
    t = np.arange(n) / rate
    audio = np.zeros(n)
    for k, peso in enumerate(harmonicos, start=1):
        audio += peso * np.sin(2 * math.pi * freq * k * t)
    ataque_n = max(1, int(rate * ataque))
    ataque_env = np.linspace(0, 1, ataque_n)
    audio[:ataque_n] *= ataque_env
    audio *= np.exp(-decaimiento * np.maximum(t - ataque, 0))
    return audio * 0.35


def generar_musica(ruta_wav, segundos, bpm=66):
    rate = 44100
    n = int(rate * segundos)
    t = np.arange(n) / rate
    mezcla = np.zeros(n)
    dur_batida = 60 / bpm
    dur_acorde = dur_batida * 4

    for c in range(int(segundos / dur_acorde) + 1):
        inicio = int(c * dur_acorde * rate)
        acorde = PROGRESION[c % len(PROGRESION)]
        pad = acorde[0:3] + [acorde[6]]
        for nota_n in pad:
            f = NOTAS[nota_n]
            seg = nota(f, dur_acorde * 1.15, rate, ataque=0.9, decaimiento=0.35, harmonicos=(1.0, 0.25, 0.08, 0.02))
            pos = inicio
            if pos < n:
                fin = min(n, pos + len(seg))
                mezcla[pos:fin] += seg[: fin - pos] * 0.30
        for i, nota_n in enumerate(acorde):
            if nota_n not in NOTAS:
                continue
            f = NOTAS[nota_n]
            seg = nota(f, dur_batida * 2.0, rate, ataque=0.005, decaimiento=3.4)
            pos = inicio + int(i * dur_batida * rate)
            if pos < n:
                fin = min(n, pos + len(seg))
                mezcla[pos:fin] += seg[: fin - pos] * 0.22

    eco = np.zeros(n)
    retardo1 = int(0.30 * rate)
    retardo2 = int(0.60 * rate)
    eco[retardo1:] += mezcla[:-retardo1] * 0.30
    eco[retardo2:] += mezcla[:-retardo2] * 0.12
    mezcla = mezcla + eco

    a = math.exp(-2 * math.pi * 2400 / rate)
    taps = 400
    kernel = a ** np.arange(taps)
    kernel /= kernel.sum()
    mezcla = np.convolve(mezcla, kernel, mode="same")

    fade_in = int(1.2 * rate)
    mezcla[:fade_in] *= np.linspace(0, 1, fade_in)
    fade_out = int(1.6 * rate)
    mezcla[-fade_out:] *= np.linspace(1, 0, fade_out)
    pico = np.max(np.abs(mezcla)) or 1.0
    mezcla = mezcla / pico * 0.62
    mezcla = mezcla + np.random.normal(0, 0.0015, n)
    pcm = (mezcla * 32767).astype(np.int16)
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
    parser.add_argument("--indice", type=int, default=None)
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
    if args.indice is not None:
        indice = args.indice % len(versos)
    else:
        indice = (ultimo + 1) % len(versos)
        estado_path.write_text(json.dumps({"ultimo": indice}), encoding="utf-8")
    verso = versos[indice]
    print(f"Versículo {indice + 1}/{len(versos)}: {verso['ref']}")

    img_v = render_versiculo(verso["ref"], verso["texto"], indice)
    img_c = render_cta(indice)
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
            f"[a0][a1]concat=n=2:v=0:a=1,volume=1.0[voz];"
            f"[4:a]aformat=sample_rates=44100:channel_layouts=stereo,aloop=loop=-1:size=2e9,volume=0.75[mus];"
            f"[voz][mus]amix=inputs=2:duration=first:dropout_transition=3:normalize=0,"
            f"afade=t=out:st={total - 1.4:.2f}:d=1.4[a]"
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
        f"Descarga la app Biblia+ gratis (toda la Biblia, audiolibros, planes de lectura):\n"
        f"{PLAY_URL}\n\n"
        f"Y en el enlace de nuestra biografía.\n\n"
        f"#biblia #jesus #fe #cristiano #palabradedios #versiculo #dios"
    )
    (tmp / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"VIDEO: {p_video}")
    print(f"DURACION: {total:.1f}s")


if __name__ == "__main__":
    main()
