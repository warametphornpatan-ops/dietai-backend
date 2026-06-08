from ultralytics import YOLO

# ระบุตำแหน่งไฟล์โมเดลของคุณให้ถูกต้อง
model_path = r"C:\Projectend\back-end\foods_carb.pt" 

try:
    print("กำลังโหลดโมเดล...")
    model = YOLO(model_path)
    
    # ดึงชื่อคลาสทั้งหมดที่อยู่ในโมเดลออกมา
    classes = model.names
    
    print(f"\n✅ โมเดลนี้รู้จักอาหารทั้งหมด {len(classes)} ชนิด ได้แก่:")
    print("-" * 30)
    
    # วนลูปเพื่อปริ้นท์ ID และชื่ออาหารออกมาให้ดูง่ายๆ
    for class_id, class_name in classes.items():
        print(f"ID {class_id} : {class_name}")
        
    print("-" * 30)

except Exception as e:
    print(f"❌ เกิดข้อผิดพลาด: {e}")