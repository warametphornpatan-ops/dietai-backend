from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, text
from datetime import date
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from ..database import get_db
from .. import models
from ..security import get_current_user

router = APIRouter(tags=["Foods"])

THAI_TZ = timezone(timedelta(hours=7))

class FoodLogRequest(BaseModel):
    food_name: str
    calories: float
    carbs: float
    protein: float
    fat: float
    image_url: Optional[str] = None

# ---- เพิ่ม Pydantic Models สำหรับจัดรูปแบบ Response ให้หน้า Dashboard อ่านง่าย ----
class FoodItemFormat(BaseModel):
    name: str
    calories: int
    category: str
    image_url: str

class BeverageFormat(BaseModel):
    name: str
    calories: float
    protein: float
    fat: float

class FoodRecommendationResponse(BaseModel):
    bmi: float
    category: str
    advice: str
    recommended_dishes: List[FoodItemFormat]
    beverages: List[BeverageFormat]


# ==================== Helper Function สำหรับจับคู่รูปภาพในเครื่อง ====================
def get_local_image_path(menu_id: int) -> str:
    """ จับคู่ MenuID กับ Path รูปภาพในโฟลเดอร์ public/foods ของ Next.js """
    return f"/foods/{menu_id}.jpg"


def get_bmi_group(bmi: float) -> str:
    """แปลง BMI เป็น bmi_group สำหรับ query database"""
    if bmi < 18.5:
        return "under"
    elif 18.5 <= bmi < 23.0:
        return "normal"
    elif 23.0 <= bmi < 25.0:
        return "over"
    else:
        return "severe-over"


def get_bmi_category_text(bmi: float) -> str:
    """ส่งข้อความหมวดหมู่ BMI"""
    if bmi < 18.5:
        return "น้ำหนักต่ำกว่าเกณฑ์ (Underweight)"
    elif 18.5 <= bmi < 23.0:
        return "น้ำหนักปกติ สุขภาพดี (Normal Weight)"
    elif 23.0 <= bmi < 25.0:
        return "น้ำหนักเกิน / เริ่มอ้วน (Overweight)"
    else:
        return "อ้วนมาก (Obesity)"


def get_medical_advice(bmi: float) -> str:
    """ส่งคำแนะนำทางการแพทย์ตามเกณฑ์ BMI"""
    if bmi < 18.5:
        return "เน้นอาหารโปรตีนสูงและคาร์โบไฮเดรตเชิงซ้อน เพิ่มพลังงานด้วยมื้อย่อยเพื่อเสริมสร้างมวลกล้ามเนื้อ"
    elif 18.5 <= bmi < 23.0:
        return "รักษาสมดุลพลังงาน ทานอาหารครบ 5 หมู่ในสัดส่วนที่เหมาะสม หลีกเลี่ยงอาหารหวานหรือมันจัดเกินไป"
    elif 23.0 <= bmi < 25.0:
        return "จำกัดอาหารประเภททอดและมันจัด ลดคาร์โบไฮเดรต เน้นโปรตีนไขมันต่ำและผลไม้ที่มีกากใยสูง"
    else:
        return "เน้นอาหารนึ่ง ต้ม ย่าง ดัชนีน้ำตาลต่ำ งดของทอดและขนมหวานเด็ดขาด เพื่อป้องกันภาวะแทรกซ้อน"


# 🌟 สำหรับดึงยอดรวมโภชนาการประจำวัน
@router.get("/today/{user_id}")
def get_daily_summary(
    user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if str(current_user.id) != str(user_id):
        raise HTTPException(status_code=403, detail="ไม่สามารถเข้าถึงข้อมูลของผู้อื่นได้")

    today = datetime.now(THAI_TZ).date()

    summary = db.query(
        func.sum(models.FoodLog.calories).label("calories"),
        func.sum(models.FoodLog.carbs).label("carbs"),
        func.sum(models.FoodLog.protein).label("protein"),
        func.sum(models.FoodLog.fat).label("fat")
    ).filter(
        models.FoodLog.user_id == str(user_id),
        func.date(models.FoodLog.created_at) == today
    ).first()

    return {
        "user_id": str(user_id),
        "date": today,
        "total_calories": summary.calories or 0,
        "total_carbs": summary.carbs or 0,
        "total_protein": summary.protein or 0,
        "total_fat": summary.fat or 0
    }


# 🌟 สำหรับบันทึกอาหารที่กินเข้าไปใหม่
@router.post("/add")
def create_food_log(
    data: FoodLogRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_log = models.FoodLog(
        user_id=str(current_user.id),
        food_name=data.food_name,
        calories=data.calories,
        carbs=data.carbs,
        protein=data.protein,
        fat=data.fat,
        image_url=data.image_url
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return {
        "message": "บันทึกสำเร็จ",
        "log": {
            "id": new_log.id,
            "user_id": new_log.user_id,
            "food_name": new_log.food_name,
            "calories": new_log.calories,
            "carbs": new_log.carbs,
            "protein": new_log.protein,
            "fat": new_log.fat,
            "image_url": new_log.image_url,
            "created_at": new_log.created_at.isoformat() if getattr(new_log, "created_at", None) else None
        }
    }


@router.get("/log")
def get_user_food_logs(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logs = db.query(models.FoodLog).filter(
        models.FoodLog.user_id == str(current_user.id)
    ).order_by(models.FoodLog.created_at.desc()).all()

    return logs


# 🌟 ✅ อัปเดต: ใช้ตาราง food_bmi_recommendations เพื่อแนะนำอาหารตามเกณฑ์ BMI
@router.get("/recommendations", response_model=FoodRecommendationResponse)
def get_food_recommendations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ดึงค่า BMI ของผู้ใช้ที่ Login อยู่ปัจจุบัน
    bmi = getattr(current_user, "bmi", None)

    if not bmi:
        raise HTTPException(status_code=400, detail="ไม่พบค่าข้อมูล BMI ของผู้ใช้ในระบบ")

    # แปลง BMI เป็น bmi_group
    bmi_group = get_bmi_group(bmi)
    category_msg = get_bmi_category_text(bmi)
    medical_advice = get_medical_advice(bmi)

    recommended_dishes_with_data = []
    recommended_beverages = []

    try:
        # ✅ 1. Query food_bmi_recommendations JOIN thai_foodmenu ตามเกณฑ์ BMI
        query = text("""
            SELECT 
                fbr.id,
                fbr.menu_id,
                tm."ThaiName",
                tm."Calories",
                tm."Category"
            FROM food_bmi_recommendations fbr
            JOIN thai_foodmenu tm ON fbr.menu_id = tm."MenuID"
            WHERE fbr.bmi_group = :bmi_group
            ORDER BY tm."Category", tm."ThaiName"
        """)
        
        db_foods = db.execute(query, {"bmi_group": bmi_group}).mappings().all()
        
        # ✅ 2. จัดเรียงอาหารตามหมวดหมู่
        for row in db_foods:
            menu_id = row["menu_id"]
            thai_name = row["ThaiName"]
            calories = row["Calories"]
            category = row["Category"]
            local_image = get_local_image_path(menu_id)

            recommended_dishes_with_data.append({
                "name": thai_name,
                "calories": int(calories) if calories else 350,
                "category": category if category else "อาหาร",
                "image_url": local_image
            })
        
        # ✅ 3. ดึงข้อมูลเครื่องดื่มกลุ่ม นม/โยเกิร์ต จากตาราง thai_nutrition
        query_drink = text("""
            SELECT food_thai, calories, protein, fat 
            FROM thai_nutrition 
            WHERE food_thai LIKE '%นม%' OR food_thai LIKE '%โยเกิร์ต%' OR food_thai LIKE '%เวย์%'
            LIMIT 5
        """)
        
        db_drinks = db.execute(query_drink).mappings().all()
        
        for row in db_drinks:
            recommended_beverages.append({
                "name": row["food_thai"],
                "calories": float(row["calories"] or 0),
                "protein": float(row["protein"] or 0),
                "fat": float(row["fat"] or 0)
            })

    except Exception as e:
        print(f"❌ Database Fetch Error: {e}")
        # ข้อมูลสำรองกรณีฐานข้อมูลมีปัญหา (Fallback)
        recommended_dishes_with_data = [
            {"name": "น้ำเปล่า", "calories": 0, "category": "เครื่องดื่ม", "image_url": "/foods/water.jpg"}
        ]
        recommended_beverages = [
            {"name": "น้ำเปล่าสะอาด", "calories": 0, "protein": 0, "fat": 0}
        ]

    return {
        "bmi": float(bmi),
        "category": category_msg,
        "advice": medical_advice,
        "recommended_dishes": recommended_dishes_with_data,
        "beverages": recommended_beverages
    }


# ✅ เพิ่ม endpoint /foods ที่รองรับหลาย query parameter
@router.get("/")
def get_foods(
    menuId: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    aiName: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    ดึงข้อมูลอาหารจากฐานข้อมูล สามารถค้นหาโดย:
    - menuId: ค้นหาด้วย MenuID เฉพาะ (e.g., ?menuId=68)
    - category: ค้นหาด้วย Category (e.g., ?category=ผลไม้)
    - aiName: ค้นหาด้วย EnglishName (สำหรับ AI detection) (e.g., ?aiName=banana)
    """
    
    base_query = """
        SELECT "MenuID", "ThaiName", "EnglishName", "Calories", "Category",
               "Nutrition"
        FROM thai_foodmenu
        WHERE 1=1
    """
    
    params = {}
    
    # สร้าง WHERE clause แบบไดนามิก
    if menuId is not None:
        base_query += """ AND "MenuID" = :menuId"""
        params["menuId"] = menuId
    elif category is not None:
        base_query += """ AND "Category" = :category"""
        params["category"] = category
    elif aiName is not None:
        base_query += """ AND LOWER("EnglishName") LIKE LOWER(:aiName)"""
        params["aiName"] = f"%{aiName}%"
    
    result = db.execute(text(base_query), params).mappings().all()
    
    return [
        {
            "MenuID": r["MenuID"],
            "ThaiName": r["ThaiName"],
            "EnglishName": r["EnglishName"],
            "Calories": r["Calories"],
            "Category": r["Category"],
            "Nutrition": r["Nutrition"],
        }
        for r in result
    ]


@router.get("/by-category")
def get_foods_by_category(category: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("""SELECT "MenuID", "ThaiName", "EnglishName", "Calories", "Category",
                       "Nutrition"
                FROM thai_foodmenu WHERE "Category" = :cat"""),
        {"cat": category}
    ).mappings().all()
    return [
        {
            "MenuID": r["MenuID"],
            "ThaiName": r["ThaiName"],
            "EnglishName": r["EnglishName"],
            "Calories": r["Calories"],
            "Category": r["Category"],
            "Nutrition": r["Nutrition"],
        }
        for r in result
    ]

@router.get("/search")
def search_food_by_name(name: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            SELECT "MenuID", "ThaiName", "EnglishName", "Calories", "Category",
                   "Nutrition"
            FROM thai_foodmenu
            WHERE LOWER("EnglishName") LIKE LOWER(:name)
               OR LOWER("ThaiName") LIKE LOWER(:name)
            LIMIT 5
        """),
        {"name": f"%{name}%"}
    ).mappings().all()

    return [
        {
            "MenuID": r["MenuID"],
            "ThaiName": r["ThaiName"],
            "EnglishName": r["EnglishName"],
            "Calories": r["Calories"],
            "Category": r["Category"],
            "Nutrition": r["Nutrition"],
        }
        for r in result
    ]

    

@router.post("/FoodUploadModel")
async def upload_food_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # 1. บันทึกรูปภาพลงเครื่องเซิร์ฟเวอร์ก่อน
    file_location = f"static/uploads/{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())

    # 2. ส่งรูปไปให้ AI วิเคราะห์ (อันนี้คือจุดที่ต้องเชื่อมกับโมเดล YOLO/CNN ของคุณ)
    # ตัวอย่าง: result = predict_food(file_location)
    
    # 3. สมมติว่า AI วิเคราะห์ได้ค่ามาแล้ว ให้บันทึกลง Database ทันที
    new_log = models.FoodLog(
        user_id=str(current_user.id),
        food_name="ชื่ออาหารจาก AI", # แทนที่ด้วยผลลัพธ์จาก AI
        calories=500,               # แทนที่ด้วยผลลัพธ์จาก AI
        carbs=50,
        protein=20,
        fat=10,
        image_url=file_location
    )
    
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    return {"message": "วิเคราะห์และบันทึกสำเร็จ", "data": new_log}