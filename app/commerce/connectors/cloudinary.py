import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException

# Volumen Railway: montá el volumen en /data desde el dashboard
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIZE = 5 * 1024 * 1024  # 5MB

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXTENSIONS    = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

async def upload_image(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Formato no permitido. Usá JPG, PNG, WEBP o GIF.")

    contents = await file.read()

    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="La imagen supera el límite de 5MB.")

    ext      = EXTENSIONS[file.content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / filename

    filepath.write_bytes(contents)

    base_url = os.environ.get("API_BASE_URL", "https://hash-cloud-production.up.railway.app")
    return f"{base_url}/uploads/{filename}"
