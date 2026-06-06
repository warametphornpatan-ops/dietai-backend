import express from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import cors from "cors";
import multer from "multer";

import { config } from "./config";
import { prisma } from "./database";
import { apiLimiter, authLimiter, uploadLimiter } from "./middleware/rateLimiter";
import { securityHeaders } from "./middleware/securityHeaders";
import authRoutes from "./router/auth";
import { uploadToSupabase } from "./utils/supabaseStorage";

const app = express();

// ✅ Security Headers
app.use(securityHeaders);

// ✅ Rate Limiting
app.use(apiLimiter);

app.use(cors({ 
  origin: config.cors.origin,
  credentials: config.cors.credentials,
})); 
app.use(express.json());

// ✅ Use memory storage instead of disk (better for serverless)
const storage = multer.memoryStorage();
const upload = multer({ 
  storage: storage,
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB limit
});

// ✅ Upload endpoint with Supabase Storage
app.post("/upload", uploadLimiter, upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "กรุณาแนบไฟล์รูปภาพ" });
    }
    
    const imageUrl = await uploadToSupabase(req.file);
    res.status(200).json({ message: "อัปโหลดรูปสำเร็จ", imageUrl });
  } catch (error: any) {
    console.error("Upload error:", error);
    res.status(500).json({ error: "เกิดข้อผิดพลาดในการอัปโหลดไฟล์" });
  }
});

// ✅ health check
app.get("/", (_req, res) => {
  console.log("📍 GET / called");
  return res.json({ message: "🚀 Smart Carb Analyzer API Ready" });
});

// Test Database Connection
app.get("/api/health/db", async (_req, res) => {
  try {
    console.log("📍 GET /api/health/db called");
    await prisma.$executeRawUnsafe("SELECT 1 as test");
    console.log("✅ Database connection successful");
    res.json({ status: "ok", database: "connected" });
  } catch (error: any) {
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
app.use("/api/auth", authRoutes);

// ✅ start server (ของเดิม)
const port = config.port;
app.listen(port, () => {
  console.log(`✅ [BOOT] API listening on http://127.0.0.1:${port}`);
  console.log(`🌍 Environment: ${config.nodeEnv}`);
  console.log(`🔒 CORS Origins: ${config.cors.origin.join(", ")}`);
});