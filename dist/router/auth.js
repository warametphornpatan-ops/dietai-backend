"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const config_1 = require("../config");
const database_1 = require("../database");
const rateLimiter_1 = require("../middleware/rateLimiter");
const router = (0, express_1.Router)();
// 🔐 Register
router.post('/register', rateLimiter_1.authLimiter, async (req, res) => {
    try {
        const { email, password, name } = req.body;
        if (!email || !password || !name) {
            return res.status(400).json({ error: '❌ กรุณากรอกข้อมูลให้ครบ' });
        }
        // Check if user exists
        const existingUser = await (0, database_1.executeQuery)('SELECT id FROM users WHERE email = ?', [email]);
        if (existingUser.length > 0) {
            return res.status(400).json({ error: '❌ Email นี้ถูกใช้แล้ว' });
        }
        // Hash password
        const hashedPassword = await bcryptjs_1.default.hash(password, 10);
        // Create user
        await (0, database_1.executeQuery)('INSERT INTO users (email, password, name, created_at) VALUES (?, ?, ?, NOW())', [email, hashedPassword, name]);
        res.status(201).json({
            message: '✅ สมัครสมาชิกสำเร็จ',
            email
        });
    }
    catch (error) {
        console.error('❌ Register error:', error);
        res.status(500).json({ error: '❌ เกิดข้อผิดพลาด: ' + error.message });
    }
});
// 🔓 Login
router.post('/login', rateLimiter_1.authLimiter, async (req, res) => {
    try {
        const { email, password } = req.body;
        if (!email || !password) {
            return res.status(400).json({ error: '❌ กรุณากรอก email และ password' });
        }
        // Find user
        const users = await (0, database_1.executeQuery)('SELECT * FROM users WHERE email = ?', [email]);
        if (users.length === 0) {
            return res.status(401).json({ error: '❌ Email หรือ password ไม่ถูกต้อง' });
        }
        const user = users[0];
        // Check password
        const validPassword = await bcryptjs_1.default.compare(password, user.password);
        if (!validPassword) {
            return res.status(401).json({ error: '❌ Email หรือ password ไม่ถูกต้อง' });
        }
        // Generate JWT
        const token = jsonwebtoken_1.default.sign({ id: user.id, email: user.email, name: user.name }, config_1.config.jwt.secret, { expiresIn: config_1.config.jwt.expiresIn });
        res.json({
            message: '✅ เข้าสู่ระบบสำเร็จ',
            token,
            user: {
                id: user.id,
                email: user.email,
                name: user.name
            }
        });
    }
    catch (error) {
        console.error('❌ Login error:', error);
        res.status(500).json({ error: '❌ เกิดข้อผิดพลาด: ' + error.message });
    }
});
// 👤 Get Profile
router.get('/profile', rateLimiter_1.authLimiter, async (req, res) => {
    try {
        const token = req.headers.authorization?.split(' ')[1];
        if (!token) {
            return res.status(401).json({ error: '❌ ไม่พบ token' });
        }
        // Verify token
        const decoded = jsonwebtoken_1.default.verify(token, config_1.config.jwt.secret);
        // Get user
        const users = await (0, database_1.executeQuery)('SELECT id, email, name, created_at FROM users WHERE id = ?', [decoded.id]);
        if (users.length === 0) {
            return res.status(404).json({ error: '❌ ไม่พบผู้ใช้' });
        }
        res.json({
            message: '✅ ดึงข้อมูลสำเร็จ',
            user: users[0]
        });
    }
    catch (error) {
        console.error('❌ Profile error:', error);
        res.status(401).json({ error: '❌ Token ไม่ถูกต้อง' });
    }
});
exports.default = router;
//# sourceMappingURL=auth.js.map