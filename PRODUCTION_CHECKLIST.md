# ✅ Production Readiness Checklist

## 🔐 Security

- [x] JWT_SECRET: ต้องสร้างใหม่ (ไม่ใช้ default)
- [x] Database password: ต้องตั้งเข้มแข็ง (ไม่ใช้ blank)
- [x] Database user: ต้องใช้ user ที่ไม่ใช่ root
- [x] CORS origins: ต้องเป็น domain จริง (ไม่ใช่ localhost)
- [x] NODE_ENV: ต้องเป็น production
- [x] Security headers: ✅ เพิ่มแล้ว
- [x] Rate limiting: ✅ เพิ่มแล้ว
- [x] HTTPS/SSL: ต้องตั้งค่า (ใช้ Let's Encrypt)

## 🗄️ Database

- [ ] MySQL running on university server
- [ ] Database `dietai` created
- [ ] User `dietai_user` created with strong password
- [ ] Tables created (users, nutrition_data, etc.)
- [ ] Backup strategy setup

## 🚀 Deployment

- [ ] .env.production updated with real values
- [ ] npm install --production
- [ ] npm run build (TypeScript compiled)
- [ ] PM2 installed globally
- [ ] PM2 ecosystem.config.json configured
- [ ] Nginx reverse proxy configured
- [ ] SSL certificate installed

## 📊 Monitoring

- [ ] PM2 logs setup
- [ ] Error logging configured
- [ ] PM2 monitoring enabled
- [ ] Uptime monitoring setup

## 🔄 Before Deploy

### 1. Generate New JWT Secret
```bash
openssl rand -base64 32
# Copy the output to .env.production
```

### 2. Create Database User
```sql
CREATE USER 'dietai_user'@'db_server_ip' IDENTIFIED BY 'STRONG_PASSWORD';
GRANT ALL ON dietai.* TO 'dietai_user'@'db_server_ip';
FLUSH PRIVILEGES;
```

### 3. Update .env.production
```
NODE_ENV=production
PORT=4000
DB_HOST=10.0.0.100
DB_PORT=3306
DB_USER=dietai_user
DB_PASSWORD=YOUR_STRONG_PASSWORD
DB_NAME=dietai
JWT_SECRET=YOUR_GENERATED_SECRET
CORS_ORIGINS=https://youruniversity.edu,https://api.youruniversity.edu
```

### 4. Build & Test
```bash
npm run build
# Verify dist folder exists
NODE_ENV=production node dist/server.js
# Should output: ✅ [BOOT] API listening on http://127.0.0.1:4000
```

### 5. Deploy with PM2
```bash
npm install -g pm2
pm2 start ecosystem.config.json --env production
pm2 save
pm2 startup
```

### 6. Test Endpoints
```bash
# Health check
curl http://localhost:4000

# Database check
curl http://localhost:4000/api/health/db

# Register user
curl -X POST http://localhost:4000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@uni.edu","password":"password123","name":"Test User"}'

# Login
curl -X POST http://localhost:4000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@uni.edu","password":"password123"}'
```

## ⚠️ Do NOT:

- ❌ Commit .env files to git
- ❌ Use root database user
- ❌ Use default JWT_SECRET
- ❌ Leave passwords blank
- ❌ Hardcode database credentials
- ❌ Deploy without HTTPS
- ❌ Skip database backup
- ❌ Ignore error logs

## 📞 Deployment Support

มีปัญหา? ตรวจสอบ:
1. PM2 logs: `pm2 logs`
2. Database connection: `mysql -u dietai_user -p -h DB_HOST dietai`
3. API health: `curl http://localhost:4000`
4. Port available: `lsof -i :4000`

**ระบุปัญหาที่ได้จากการตรวจสอบข้างบนเมื่อขอความช่วยเหลือ** 🎯
