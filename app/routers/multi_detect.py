from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image
import io

router = APIRouter(prefix="/food", tags=["food-recognition"])

# ยังไม่โหลดตอนนี้
_food_model = None
_fruit_model = None
_best_model = None

def get_models():
    global _food_model, _fruit_model, _best_model
    import torch
    from ultralytics import YOLO
    import ultralytics.nn.tasks

    # แก้ปัญหา PyTorch 2.6 ไม่ยอมโหลด YOLO weights
    torch.serialization.add_safe_globals([
        ultralytics.nn.tasks.DetectionModel
    ])

    if _food_model is None:
        _food_model = YOLO("food.pt")
    if _fruit_model is None:
        _fruit_model = YOLO("foods_carb.pt")
    if _best_model is None:
        _best_model = YOLO("best.pt")
    return _food_model, _fruit_model, _best_model

@router.post("/detect")
async def detect_all(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="ไฟล์รูปภาพไม่ถูกต้อง")

    food_model, fruit_model, best_model = get_models()  # โหลดเฉพาะตอนเรียกใช้

    final_predictions = []

    food_results = food_model(image, conf=0.75)
    for result in food_results:
        if result.boxes is not None:
            for box in result.boxes:
                final_predictions.append({
                    "class": food_model.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "food"
                })

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