from fastapi import APIRouter, UploadFile, File, HTTPException
import httpx
import io

router = APIRouter(prefix="/food", tags=["food-recognition"])

HF_URL = "https://waramet-yolo-brain-api.hf.space/detect"

@router.post("/detect")
async def detect_all(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="ไฟล์รูปภาพไม่ถูกต้อง")

    # ยิงรูปไปหา HuggingFace
    try:
        files = {"file": (file.filename, image_bytes, file.content_type)}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(HF_URL, files=files)
        hf_data = response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI Brain error: {str(e)}")

    # แปลงผลลัพธ์จาก HF ให้ตรงกับ format เดิม
    final_predictions = []
    for item in hf_data.get("foods", []):
        final_predictions.append({
            "class": item["name"].strip().lower(),
            "raw_class": item["name"],
            "confidence": round(item["confidence"] * 100, 2),
            "type": "food",
            "source": item.get("source", "unknown")
        })

    return {"predictions": final_predictions}