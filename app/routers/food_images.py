import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from datetime import datetime
from supabase import create_client

from app.routers.user import get_current_user

router = APIRouter(
    prefix="/food-images",
    tags=["Food Images"]
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
BUCKET_NAME = "food-images"

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@router.post("")
async def upload_food_image(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
):
    try:
        content = await file.read()
        ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{current_user.id}/{datetime.utcnow().timestamp()}.{ext}"

        supabase = get_supabase()
        supabase.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=content,
            file_options={"content-type": file.content_type or "image/jpeg"}
        )

        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
        return {"url": public_url}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))