from fastapi import APIRouter, UploadFile, File, HTTPException
from ultralytics import YOLO
from PIL import Image
import io

router = APIRouter(prefix="/food", tags=["food-recognition"])

try:
    food_model = YOLO("food.pt")
    fruit_model = YOLO("foods_carb.pt")
    
    # หมายเหตุ: ปรับชื่อตัวแปรไม่ให้ทับกัน (จากเดิม foods_model ซ้ำกัน 2 บรรทัด)
    # ถ้าอยากใช้ foods.pt ด้วย สามารถปลดคอมเมนต์บรรทัดล่างนี้ และเพิ่ม Step 4 ได้ครับ
    # foods_model = YOLO("foods.pt") 
    
    best_model = YOLO("best.pt")  
    print("✅ โหลดโมเดล Food/Foods และ foods_carb/best สำเร็จ!")
except Exception as e:
    print(f"❌ โหลดโมเดลไม่สำเร็จ: {e}")

@router.post("/detect")
async def detect_all(file: UploadFile = File(...)):
    try:
        # อ่านไฟล์รูปภาพที่อัปโหลดเข้ามา
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="ไฟล์รูปภาพไม่ถูกต้อง")

    final_predictions = []
    
    # --- STEP 1: ตรวจจับอาหารด้วย food_model ---
    food_results = food_model(image, conf=0.75) 
    for result in food_results:
        # ✅ ป้องกัน Error: ตรวจสอบก่อนว่า result.boxes ไม่ใช่ค่าว่าง (None)
        if result.boxes is not None:
            for box in result.boxes:
                final_predictions.append({
                    "class": food_model.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "food"
                })

    # --- STEP 2: ตรวจจับผลไม้ด้วย fruit_model ---
    # ตั้งค่า conf ได้ตามต้องการ (เช่น 0.5 คือต้องมั่นใจ 50% ขึ้นไปถึงจะแสดงผล)
    fruit_results = fruit_model(image, conf=0.50) 
    for result in fruit_results:
        # ✅ ป้องกัน Error
        if result.boxes is not None:
            for box in result.boxes:
                final_predictions.append({
                    "class": fruit_model.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "fruit"
                })

    # --- STEP 3: ตรวจจับอาหารประเภทอื่นๆ ด้วย best_model ---
    best_results = best_model(image, conf=0.75)
    for result in best_results:
        # ✅ ป้องกัน Error
        if result.boxes is not None:
            for box in result.boxes:
                final_predictions.append({
                    "class": best_model.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]) * 100, 2),
                    "type": "food"
                })

    # ส่งผลลัพธ์ทั้งหมดกลับไปในรูปแบบ JSON
    return {"predictions": final_predictions}