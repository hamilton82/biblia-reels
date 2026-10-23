import os
import sys
import time

import requests

BASE = "https://graph.instagram.com"
TOKEN = os.environ.get("IG_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "17841444271733710")
VIDEO_URL = os.environ.get("VIDEO_URL", "")
CAPTION = os.environ.get("CAPTION", "")


def exigir(condicion, mensaje):
    if not condicion:
        print(f"ERROR: {mensaje}")
        sys.exit(1)


def refrescar_token(token):
    r = requests.get(
        f"{BASE}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=30,
    )
    if r.ok:
        nuevo = r.json().get("access_token")
        print("Token refrescado (60 días más).")
        return nuevo or token
    print(f"Aviso: no se pudo refrescar el token ({r.status_code}). Uso el actual.")
    return token


def main():
    exigir(TOKEN, "Falta la variable IG_TOKEN")
    exigir(VIDEO_URL, "Falta la variable VIDEO_URL (HTTPS público del vídeo)")
    exigir(CAPTION, "Falta la variable CAPTION")

    token = refrescar_token(TOKEN)

    r = requests.post(
        f"{BASE}/{IG_USER_ID}/media",
        data={
            "media_type": "REELS",
            "video_url": VIDEO_URL,
            "caption": CAPTION,
            "access_token": token,
        },
        timeout=60,
    )
    if not r.ok:
        print(f"ERROR creando contenedor: {r.status_code} {r.text}")
        sys.exit(1)
    container = r.json()["id"]
    print(f"Contenedor: {container}")

    for intento in range(60):
        time.sleep(10)
        r = requests.get(
            f"{BASE}/{container}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        )
        estado = r.json().get("status_code", "?")
        print(f"Estado: {estado}")
        if estado == "FINISHED":
            break
        if estado in ("ERROR", "EXPIRED"):
            print(f"ERROR procesando el vídeo: {r.json()}")
            sys.exit(1)
    else:
        print("ERROR: timeout esperando el vídeo (10 min).")
        sys.exit(1)

    r = requests.post(
        f"{BASE}/{IG_USER_ID}/media_publish",
        data={"creation_id": container, "access_token": token},
        timeout=60,
    )
    if not r.ok:
        print(f"ERROR publicando: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"¡PUBLICADO! media_id={r.json().get('id')}")


if __name__ == "__main__":
    main()
