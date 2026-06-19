from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db

router = APIRouter(
    tags=["organization"]
)

@router.get("/{org_code}")
def check_organization(org_code: str, db: Session = Depends(get_db)):
    # 1. หน้าบ้านอาจส่งมาเป็น 'CA0032045' หรือ '32045' ล้างให้เหลือเฉพาะตัวเลข
    clean_input = "".join(filter(str.isdigit, org_code))
    
    if not clean_input:
        raise HTTPException(
            status_code=400, 
            detail="รหัสหน่วยงานต้องมีตัวเลขประกอบอยู่ด้วย"
        )

    # 2. คิวรีข้อมูลจากตาราง health_office (ล้างเครื่องหมายคำพูด " ออกให้สะอาดตั้งแต่ใน SQL)
    sql = text("""
    SELECT REPLACE("COL 1", '"', '') AS hospital_name
    FROM health_office 
    WHERE REPLACE("COL 4", '"', '') = :code 
       OR REPLACE("COL 3", '"', '') LIKE :code_like
    LIMIT 1
""")
    
    # 3. ใช้ .mappings().first() เพื่ออ่านค่าผ่านชื่อ Key (คอลัมน์ Alias) ได้อย่างปลอดภัย
    result = db.execute(sql, {
        "code": clean_input,
        "code_like": f"%{clean_input}%"
    }).mappings().first()
    
    # ถ้าค้นหาในตาราง health_office แล้วไม่เจอข้อมูล
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"ไม่พบรหัสหน่วยงาน {clean_input} ในระบบ"
        )
        
    # 4. ส่งกลับเป็น Object ที่มี Key ชื่อ "name" ตรงตามที่หน้าบ้านแกะค่าไปใช้ (.name)
    return {"name": result["hospital_name"]}