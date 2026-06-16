"""
อัลกอริทึมตรวจสอบเลขบัตรประชาชนไทย (Thai ID Card Validation)

รูปแบบ: XXXXXXXXXXX (13 หลัก)
- หลักที่ 1: เพศ/ศตวรรษ (0-9)
- หลักที่ 2-5: ปี พ.ศ. (4 หลัก)
- หลักที่ 6-7: เดือน (01-12)
- หลักที่ 8-9: วัน (01-31)
- หลักที่ 10-13: เลขประจำตัวบุคคล (4 หลัก)
- หลักที่ 13: ตัวตรวจสอบ (Checksum)
"""


def validate_thai_id(citizen_id: str) -> dict:
    errors = []
    
    # 1. ตรวจสอบความยาว
    citizen_id_clean = citizen_id.replace("-", "").strip()
    if len(citizen_id_clean) != 13:
        return {
            "is_valid": False,
            "message": f"เลขบัตรต้อง 13 หลัก พบ {len(citizen_id_clean)} หลัก",
            "errors": ["length_invalid"]
        }
    
    # 2. ตรวจสอบว่าเป็นตัวเลขทั้งหมด
    if not citizen_id_clean.isdigit():
        return {
            "is_valid": False,
            "message": "เลขบัตรต้องเป็นตัวเลขเท่านั้น",
            "errors": ["not_numeric"]
        }
    
    # 3. ตรวจสอบ Checksum Digit
    weights = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(citizen_id_clean[i]) * weights[i] for i in range(12))
    
    remainder = total % 11
    check_digit = (11 - remainder) % 10
    actual_check_digit = int(citizen_id_clean[12])
    
    if check_digit != actual_check_digit:
        errors.append("checksum_invalid")
    
    # 4. ส่งผลลัพธ์
    if errors:
        error_messages = {
            "checksum_invalid": "เลขบัตรไม่ถูกต้อง (ไม่ผ่านการตรวจสอบ Checksum)"
        }
        return {
            "is_valid": False,
            "message": "เลขบัตรไม่ถูกต้อง",
            "errors": errors,
            "details": [error_messages.get(e, e) for e in errors]
        }
    
    return {
        "is_valid": True,
        "message": "เลขบัตรถูกต้อง",
        "errors": []
    }


# ===== Test Cases =====
if __name__ == "__main__":
    test_cases = [
        ("1234567890123", "Valid format (example)"),
        ("1234567890120", "Invalid checksum"),
        ("12345678901", "Too short"),
        ("123456789012A", "Contains letter"),
        ("1234569012345", "Invalid month (90)"),
    ]
    
    for citizen_id, description in test_cases:
        result = validate_thai_id(citizen_id)
        print(f"\n{description}")
        print(f"ID: {citizen_id}")
        print(f"Valid: {result['is_valid']}")
        print(f"Message: {result['message']}")
        if result['errors']:
            print(f"Errors: {result['errors']}")