import os
import sys
from getpass import getpass

import psycopg2
from passlib.hash import bcrypt_sha256

try:
    from dotenv import load_dotenv
except ImportError:
    print("❌ ยังไม่ได้ติดตั้ง python-dotenv  ->  รัน:  pip install python-dotenv")
    sys.exit(1)


def get_database_url() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(here, ".env"))
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("❌ ไม่พบ DATABASE_URL ใน .env")
        sys.exit(1)
    if "127.0.0.1" in url or "localhost" in url:
        print("⚠️  DATABASE_URL ที่อ่านได้ชี้ไป localhost ไม่ใช่ Supabase")
        print(f"   ค่าที่อ่านได้ขึ้นต้นว่า: {url[:30]}...")
        if input("   จะใช้ค่านี้ต่อไหม? (y/N): ").strip().lower() != "y":
            sys.exit(1)
    return url

def ask(label: str, required: bool = True) -> str:
    while True:
        val = input(f"{label}: ").strip()
        if val or not required:
            return val
        print("  * จำเป็นต้องกรอก")

def main() -> None:
    database_url = get_database_url()

    print("\n=== กรอกข้อมูลแอดมินคนแรก ===")
    first_name = ask("ชื่อจริง (first_name)")
    last_name = ask("นามสกุล (last_name)")
    username = ask("username")
    email = ask("email")
    org_code = ask("org_code (เช่น GA0014455)")
    citizen_id = ask("เลขบัตรประชาชน ", required=False) or None

    while True:
        password = getpass("ตั้งรหัสผ่าน (พิมพ์จะไม่แสดง): ")
        confirm = getpass("ยืนยันรหัสผ่านอีกครั้ง: ")
        if not password:
            print("  * รหัสผ่านห้ามว่าง")
        elif password != confirm:
            print("  * รหัสผ่านไม่ตรงกัน ลองใหม่")
        else:
            break

    password_hash = bcrypt_sha256.hash(password)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT admin_id FROM admins WHERE email = %s OR username = %s",
                (email, username),
            )
            row = cur.fetchone()
            if row:
                print(f"\nℹ️  มีแอดมินนี้อยู่แล้ว (admin_id={row[0]}) ไม่สร้างซ้ำ")
                return

            cur.execute(
                """
                INSERT INTO admins
                    (org_code, citizen_id, first_name, last_name,
                     email, username, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING admin_id
                """,
                (org_code, citizen_id, first_name, last_name,
                 email, username, password_hash),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
        print(f"\n✅ สร้างแอดมินคนแรกสำเร็จ (admin_id={new_id}, username={username})")
        print("   ล็อกอินด้วย username + password + org_code นี้ได้เลย")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ เกิดข้อผิดพลาด: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()