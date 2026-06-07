# app/routers/food_images.py
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import Response
from datetime import datetime
from bson import ObjectId

from ..db.mongo import food_images_col, wrap_binary
from app.routers.user import get_current_user

router = APIRouter(
    prefix="/food-images",
    tags=["Food Images"]
)

@router.post("")
async def upload_food_image(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
):
    try:
        content = await file.read()

        doc = {
            "filename": file.filename,
            "content_type": file.content_type or "image/jpeg",
            "data": wrap_binary(content),
            "user_id": current_user.id,
            "created_at": datetime.utcnow(),
        }

        result = food_images_col.insert_one(doc)
        
        base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        image_url = f"{base_url}/food-images/{result.inserted_id}"
        
        return {"id": str(result.inserted_id), "url": image_url}

    except Exception as e:
        import traceback
        traceback.print_exc()  # ← จะ print ใน Render log
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{image_id}")
async def get_food_image(image_id: str):
    try:
        oid = ObjectId(image_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")

    doc = food_images_col.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="image not found")

    return Response(content=doc["data"], media_type=doc["content_type"])