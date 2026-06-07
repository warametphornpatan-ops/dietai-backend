from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image
import io

router = APIRouter(prefix="/food", tags=["food-recognition"])

_fruit_model = None
_best_model = None

def get_models():
    global _fruit_model, _best_model
    import torch
    from ultralytics import YOLO
    import ultralytics.nn.tasks

    torch.serialization.add_safe_globals([
        ultralytics.nn.tasks.DetectionModel
    ])

    if _fruit_model is None:
        _fruit_model = YOLO("foods_carb.pt")
    if _best_model is None:
        _best_model = YOLO("best.pt")
    return _fruit_model, _best_model


@router.post("/detect")
async def detect_all(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="ไฟล์รูปภาพไม่ถูกต้อง")

    fruit_model, best_model = get_models()

    final_predictions = []

    fruit_results = fruit_model(image, conf=0.50)
    for result in fruit_results:
        if result.boxes is not None:
            for box in result.boxes:
                final_predictions.append({
                    "class": fruit_model.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "fruit"
                })

    best_results = best_model(image, conf=0.75)
    for result in best_results:
        if result.boxes is not None:
            for box in result.boxes:
                final_predictions.append({
                    "class": best_model.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "food"
                })

    return {"predictions": final_predictions}