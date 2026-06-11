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
def get_local_image_path(menu_name: str) -> str:
    """ จับคู่ชื่อเมนูไทยกับ Path รูปภาพในโฟลเดอร์ public/foods ของ Next.js """
    default_path = "/foods/default-food.jpg"
    
    image_mapping = {
        "กล้วย": "/foods/banana.jpg",
        "ส้ม": "/foods/orange.jpg",
        "แอปเปิ้ล": "/foods/apple.jpg",
        "มะม่วง": "/foods/mango.jpg",
        "มังคุด": "/foods/mangosteen.jpg",
        "ขนมชั้น": "/foods/khanom-chan.jpg",
        "ขนมตาล": "/foods/khanom-tan.jpg",
        "ขนมบ้าบิ่น": "/foods/ba-bin.jpg",
        "ทองม้วน": "/foods/thong-muan.jpg",
        "บราวนี่": "/foods/brownie.jpg",
        "แพนเค้ก": "/foods/pancake.jpg",
        "วาฟเฟิล": "/foods/waffle.jpg",
        "ข้าวกะเพรา": "/foods/ka-prao.jpg",
        "ไข่ดาว": "/foods/fried-egg.jpg",
        "โจ๊ก": "/foods/jok.jpg",
        "ข้าวผัดพริกแกง": "/foods/pad-prik-gaeng.jpg",
        "ข้าวไข่เจียว": "/foods/kai-jeow.jpg",
        "ข้าวขาหมู": "/foods/kha-mu.jpg",
        "ข้าวหมูแดง": "/foods/mu-daeng.jpg",
        "ข้าวหมูกรอบ": "/foods/mu-grob.jpg",
        "ข้าวมันไก่": "/foods/khao-man-gai.jpg",
        "ข้าวคลุกกะปิ": "/foods/khao-khluk-kapi.jpg",
        "ข้าว": "/foods/rice.jpg",
        "ผัดไทย": "/foods/pad-thai.jpg",
        "ราดหน้า": "/foods/rad-na.jpg",
        "ก๋วยเตี๋ยว": "/foods/noodle.jpg",
        "ผัดซีอิ๊ว": "/foods/pad-see-ew.jpg"
    }
    return image_mapping.get(menu_name, default_path)


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


# 🌟 อัปเดตและปรับปรุง: ระบบกรองเมนูและแนะนำรูปภาพตามค่า BMI สดจากฐานข้อมูล SQL
@router.get("/recommendations", response_model=FoodRecommendationResponse)
def get_food_recommendations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ดึงค่า BMI ของผู้ใช้ที่ Login อยู่ปัจจุบันมาคำนวณอัตโนมัติ
    bmi = getattr(current_user, "bmi", None)

    if not bmi:
        raise HTTPException(status_code=400, detail="ไม่พบค่าข้อมูล BMI ของผู้ใช้ในระบบ")

    # กำหนดกลุ่มชื่ออาหารที่มีในโปรเจกต์ของคุณ
    project_fruits = ["กล้วย", "ส้ม", "แอปเปิ้ล", "มะม่วง", "มังคุด"]
    project_desserts = ["ขนมชั้น", "ขนมตาล", "ขนมบ้าบิ่น", "ทองม้วน", "บราวนี่", "แพนเค้ก", "วาฟเฟิล"]
    
    selected_mains = []
    selected_fruits = []
    selected_desserts = []
    drink_keywords = []
    
    category_msg = ""
    medical_advice = ""

    # 🎯 ลอจิกกรองชื่ออาหารตามเกณฑ์ทางการแพทย์เพื่อความปลอดภัยของผู้ใช้
    if bmi < 18.5:
        category_msg = "น้ำหนักต่ำกว่าเกณฑ์ (Underweight)"
        medical_advice = "เน้นอาหารโปรตีนสูงและคาร์โบไฮเดรตเชิงซ้อน เพิ่มพลังงานด้วยมื้อย่อยเพื่อเสริมสร้างมวลกล้ามเนื้อ"
        selected_mains = ["ข้าวมันไก่", "ข้าวขาหมู", "ข้าวหมูแดง", "ข้าวไข่เจียว", "โจ๊ก", "ผัดซีอิ๊ว", "ราดหน้า"]
        selected_fruits = ["กล้วย", "มะม่วง", "แอปเปิ้ล"]
        selected_desserts = ["แพนเค้ก", "วาฟเฟิล", "ขนมชั้น", "ขนมตาล", "ทองม้วน"]
        drink_keywords = ["รสธรรมชาติ, ต่อ 100 มล.", "รสช็อกโกแลต", "เวย์โปรตีนผง"]
        
    elif 18.5 <= bmi < 23.0:
        category_msg = "น้ำหนักปกติ สุขภาพดี (Normal Weight)"
        medical_advice = "รักษาสมดุลพลังงาน ทานอาหารครบ 5 หมู่ในสัดส่วนที่เหมาะสม หลีกเลี่ยงอาหารหวานหรือมันจัดเกินไป"
        selected_mains = ["ข้าวกะเพรา", "ข้าวผัดพริกแกง", "โจ๊ก", "ข้าวหมูแดง", "ผัดไทย", "ก๋วยเตี๋ยว", "ข้าว"]
        selected_fruits = ["ส้ม", "แอปเปิ้ล", "มังคุด", "กล้วย"]
        selected_desserts = ["ขนมบ้าบิ่น", "ทองม้วน", "บราวนี่"]
        drink_keywords = ["รสธรรมชาติ, ต่อ 100 มล.", "โยเกิร์ต, รสธรรมชาติ"]

    elif 23.0 <= bmi < 25.0:
        category_msg = "น้ำหนักเกิน / เริ่มอ้วน (Overweight)"
        medical_advice = "จำกัดอาหารประเภททอดและมันจัด ลดคาร์โบไฮเดรต เน้นโปรตีนไขมันต่ำและผลไม้ที่มีกากใยสูง"
        selected_mains = ["ข้าวกะเพรา", "โจ๊ก", "ก๋วยเตี๋ยว", "ข้าว"]
        selected_fruits = ["แอปเปิ้ล", "ส้ม", "มังคุด"]
        selected_desserts = []
        drink_keywords = ["พร่องมันเนย", "โยเกิร์ต, ไขมันต่ำ"]

    else:
        category_msg = "อ้วนมาก (Obesity)"
        medical_advice = "เน้นอาหารนึ่ง ต้ม ย่าง ดัชนีน้ำตาลต่ำ งดของทอดและขนมหวานเด็ดขาด เพื่อป้องกันภาวะแทรกซ้อน"
        selected_mains = ["โจ๊ก", "ก๋วยเตี๋ยว", "ข้าว"]
        selected_fruits = ["แอปเปิ้ล"]
        selected_desserts = []
        drink_keywords = ["ขาดมันเนย", "พร่องมันเนย, ยูเอชที รสธรรมชาติ"]

    combined_names = selected_mains + selected_fruits + selected_desserts

    recommended_dishes_with_data = []
    recommended_beverages = []

    try:
        # 💾 1. ดึงข้อมูลแคลอรีจากตาราง thai_foodmenu และทำการผูก Path รูปภาพที่ดาวน์โหลดเก็บไว้
        if combined_names:
            in_clause = ", ".join([f":name{i}" for i in range(len(combined_names))])
            query_params = {f"name{i}": name for i, name in enumerate(combined_names)}
            
            query = text(f"SELECT ThaiName, Calories, Category FROM thai_foodmenu WHERE ThaiName IN ({in_clause})")
            db_food = db.execute(query, query_params).mappings().all()
            food_map = {row["ThaiName"]: row for row in db_food}
            
            for name in combined_names:
                calories = food_map.get(name, {}).get("Calories") or 350
                category = food_map.get(name, {}).get("Category") or "อาหาร"
                local_image = get_local_image_path(name)

                recommended_dishes_with_data.append({
                    "name": name,
                    "calories": int(calories),
                    "category": category,
                    "image_url": local_image
                })
        
        # 💾 2. ดึงข้อมูลเครื่องดื่มกลุ่ม นม/โยเกิร์ต จากตาราง thai_nutrition ในฐานข้อมูล SQL
        if drink_keywords:
            conditions = [f"food_thai LIKE :drink{i}" for i in range(len(drink_keywords))]
            drink_params = {f"drink{i}": f"%{kw}%" for i, kw in enumerate(drink_keywords)}
            
            query_drink = text(f"SELECT food_thai, calories, protein, fat FROM thai_nutrition WHERE {' OR '.join(conditions)}")
            db_drinks = db.execute(query_drink, drink_params).mappings().all()
            
            for row in db_drinks:
                recommended_beverages.append({
                    "name": row["food_thai"],
                    "calories": float(row["calories"] or 0),
                    "protein": float(row["protein"] or 0),
                    "fat": float(row["fat"] or 0)
                })

    except Exception as e:
        print(f"Database Fetch Error: {e}")
        # ข้อมูลสำรองกรณีฐานข้อมูลมีปัญหา (Fallback)
        recommended_dishes_with_data = [{
            "name": n, "calories": 350, "category": "ทั่วไป", "image_url": get_local_image_path(n)
        } for n in combined_names]
        recommended_beverages = [{"name": "น้ำเปล่าสะอาด", "calories": 0, "protein": 0, "fat": 0}]

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
            "Nutrition": r["Nutrition"],  # ← ต้องส่งกลับด้วย!
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