import mysql from 'mysql2/promise';

// 1. ตั้งค่าการเชื่อมต่อฐานข้อมูล
const pool = mysql.createPool({
  host: 'localhost',      // หรือ 127.0.0.1
  user: 'root',           // username ของ phpMyAdmin (ค่าเริ่มต้นของ XAMPP มักจะเป็น root)
  password: '',           // รหัสผ่าน (ถ้าไม่ได้ตั้งไว้ ให้ปล่อยว่าง)
  database: 'dietai',     // ชื่อฐานข้อมูลตามในรูปของคุณ
  waitForConnections: true,
  connectionLimit: 10,
});

// 2. สร้างฟังก์ชันดึงข้อมูลมาใช้งาน
export async function getNutritionData() {
  try {
    // ใช้คำสั่ง SQL ดึงข้อมูลทั้งหมด
    const [rows] = await pool.query('SELECT * FROM nutrition_data');
    
    console.log("ดึงข้อมูลสำเร็จ:", rows);
    return rows; // ข้อมูลที่ได้จะเป็น Array ของ Object นำไปใช้ต่อได้เลย

  } catch (error) {
    console.error("เกิดข้อผิดพลาดในการดึงข้อมูล:", error);
  }
}

// ตัวอย่างการเรียกใช้งาน
// getNutritionData();