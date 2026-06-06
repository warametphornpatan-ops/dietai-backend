import { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { config } from '../config';
import { executeQuery } from '../database';
import { authLimiter } from '../middleware/rateLimiter';

const router = Router();

interface AuthRequest extends Request {
  user?: any;
}

// 🔐 Register
router.post('/register', authLimiter, async (req: AuthRequest, res: Response) => {
  try {
    const { email, password, name } = req.body;

    if (!email || !password || !name) {
      return res.status(400).json({ error: '❌ กรุณากรอกข้อมูลให้ครบ' });
    }

    // Check if user exists
    const existingUser = await executeQuery('SELECT id FROM users WHERE email = ?', [email]);
    if ((existingUser as any[]).length > 0) {
      return res.status(400).json({ error: '❌ Email นี้ถูกใช้แล้ว' });
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Create user
    await executeQuery(
      'INSERT INTO users (email, password, name, created_at) VALUES (?, ?, ?, NOW())',
      [email, hashedPassword, name]
    );

    res.status(201).json({ 
      message: '✅ สมัครสมาชิกสำเร็จ',
      email 
    });
  } catch (error: any) {
    console.error('❌ Register error:', error);
    res.status(500).json({ error: '❌ เกิดข้อผิดพลาด: ' + error.message });
  }
});

// 🔓 Login
router.post('/login', authLimiter, async (req: AuthRequest, res: Response) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: '❌ กรุณากรอก email และ password' });
    }

    // Find user
    const users = await executeQuery('SELECT * FROM users WHERE email = ?', [email]) as any[];
    if (users.length === 0) {
      return res.status(401).json({ error: '❌ Email หรือ password ไม่ถูกต้อง' });
    }

    const user = users[0];

    // Check password
    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(401).json({ error: '❌ Email หรือ password ไม่ถูกต้อง' });
    }

    // Generate JWT
    const token = jwt.sign(
      { id: user.id, email: user.email, name: user.name } as any,
      config.jwt.secret as string | Buffer,
      { expiresIn: config.jwt.expiresIn } as any
    );

    res.json({ 
      message: '✅ เข้าสู่ระบบสำเร็จ',
      token,
      user: {
        id: user.id,
        email: user.email,
        name: user.name
      }
    });
  } catch (error: any) {
    console.error('❌ Login error:', error);
    res.status(500).json({ error: '❌ เกิดข้อผิดพลาด: ' + error.message });
  }
});

// 👤 Get Profile
router.get('/profile', authLimiter, async (req: AuthRequest, res: Response) => {
  try {
    const token = req.headers.authorization?.split(' ')[1];

    if (!token) {
      return res.status(401).json({ error: '❌ ไม่พบ token' });
    }

    // Verify token
    const decoded: any = jwt.verify(token, config.jwt.secret);

    // Get user
    const users = await executeQuery('SELECT id, email, name, created_at FROM users WHERE id = ?', [decoded.id]) as any[];
    if (users.length === 0) {
      return res.status(404).json({ error: '❌ ไม่พบผู้ใช้' });
    }

    res.json({ 
      message: '✅ ดึงข้อมูลสำเร็จ',
      user: users[0]
    });
  } catch (error: any) {
    console.error('❌ Profile error:', error);
    res.status(401).json({ error: '❌ Token ไม่ถูกต้อง' });
  }
});

export default router;