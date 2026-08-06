import os
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

cloudinary.config(
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key    = os.environ["CLOUDINARY_API_KEY"],
    api_secret = os.environ["CLOUDINARY_API_SECRET"],
    secure     = True,
)

async def upload_image(file: UploadFile) -> str:
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        folder="hash-commerce/products",
        resource_type="image",
    )
    return result["secure_url"]
