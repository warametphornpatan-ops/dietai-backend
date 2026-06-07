from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image
import io

router = APIRouter(prefix="/food", tags=["food-recognition"])

_model = None

def get_model():
    global _model
    from ultralytics import YOLO
    if _model is None:
        _model = YOLO("foods_carb.pt")
    return _model


@router.post("/detect")
async def detect_all(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="ไฟล์รูปภาพไม่ถูกต้อง")

    model = get_model()
    final_predictions = []

    results = model(image, conf=0.50)
    for result in results:
        if result.boxes is not None:
            for box in result.boxes:
                class_name = model.names[int(box.cls[0])]
                
                # Normalize: trim whitespace + lowercase
                normalized_name = class_name.strip().lower()
                
                final_predictions.append({
                    "class": normalized_name,  # ส่งชื่อที่ normalize แล้ว
                    "raw_class": class_name,   # เก็บชื่อเดิมไว้ด้วยเผื่อ debug
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "food"
                })

    return {"predictions": final_predictions}