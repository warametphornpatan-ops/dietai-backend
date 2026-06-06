"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
// src/server.ts
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const multer_1 = __importDefault(require("multer"));
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const config_1 = require("./config");
const database_1 = require("./database");
const rateLimiter_1 = require("./middleware/rateLimiter");
const securityHeaders_1 = require("./middleware/securityHeaders");
const auth_1 = __importDefault(require("./router/auth"));
const app = (0, express_1.default)();
// ✅ Security Headers
app.use(securityHeaders_1.securityHeaders);
// ✅ Rate Limiting
app.use(rateLimiter_1.apiLimiter);
app.use((0, cors_1.default)({
    origin: config_1.config.cors.origin,
    credentials: config_1.config.cors.credentials,
}));
app.use(express_1.default.json());
const uploadDir = path_1.default.join(process.cwd(), "uploads");
if (!fs_1.default.existsSync(uploadDir)) {
    fs_1.default.mkdirSync(uploadDir);
}
// ✅ เพิ่มใหม่: เปิดให้หน้าบ้านเรียกดูรูปได้ผ่าน URL เช่น http://localhost:4000/uploads/รูปภาพ.jpg
app.use("/uploads", express_1.default.static(uploadDir));
// ✅ เพิ่มใหม่: ตั้งค่า Multer ว่าจะเซฟไฟล์ไว้ไหน และตั้งชื่อไฟล์ยังไง
const storage = multer_1.default.diskStorage({
    destination: function (req, file, cb) {
        cb(null, uploadDir); // เซฟลงโฟลเดอร์ uploads
    },
    filename: function (req, file, cb) {
        // ตั้งชื่อไฟล์ใหม่ด้วยเวลาปัจจุบัน เพื่อป้องกันชื่อซ้ำ
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + path_1.default.extname(file.originalname));
    }
});
const upload = (0, multer_1.default)({ storage: storage });
// ✅ Upload endpoint with rate limiting
app.post("/upload", rateLimiter_1.uploadLimiter, upload.single("file"), (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: "กรุณาแนบไฟล์รูปภาพ" });
        }
        // สร้าง URL ของรูปภาพเพื่อส่งกลับไปให้หน้าบ้าน (เช่น /uploads/170987654321-xxx.jpg)
        const imageUrl = `/uploads/${req.file.filename}`;
        res.status(200).json({ message: "อัปโหลดรูปสำเร็จ", imageUrl: imageUrl });
    }
    catch (error) {
        console.error("Upload error:", error);
        res.status(500).json({ error: "เกิดข้อผิดพลาดในการอัปโหลดไฟล์" });
    }
});
// ✅ health check (ของเดิม)
app.get("/", (_req, res) => {
    console.log("📍 GET / called");
    return res.json({ message: "🚀 Smart Carb Analyzer API Ready" });
});
// Test Database Connection
app.get("/api/health/db", async (_req, res) => {
    try {
        console.log("📍 GET /api/health/db called");
        const rows = await (0, database_1.executeQuery)("SELECT 1 as test");
        console.log("✅ Database query result:", rows);
        res.json({ status: "ok", database: "connected", result: rows });
    }
    catch (error) {
        console.error("❌ Database query failed:", error);
        res.status(500).json({
            status: "error",
            database: "disconnected",
            error: error.message
        });
    }
});
// ... โค้ด REGISTER, LOGIN, GET PROFILE ของคุณอยู่ตรงนี้ (คงไว้เหมือนเดิมเลยครับ) ...
// ✅ Auth Routes
app.use("/api/auth", auth_1.default);
// ✅ start server (ของเดิม)
const port = config_1.config.port;
app.listen(port, () => {
    console.log(`✅ [BOOT] API listening on http://127.0.0.1:${port}`);
    console.log(`🌍 Environment: ${config_1.config.nodeEnv}`);
    console.log(`🔒 CORS Origins: ${config_1.config.cors.origin.join(", ")}`);
});
//# sourceMappingURL=server.js.map