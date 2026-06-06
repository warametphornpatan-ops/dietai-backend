# 🚀 Smart Carb Analyzer - Backend Setup Guide

## 📋 Prerequisites
- Node.js 18+
- MySQL 8.0+
- npm or yarn

## ⚙️ Installation

### 1. Install dependencies
```bash
npm install
```

### 2. Setup Environment Variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your configuration
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=dietai
JWT_SECRET=your-secret-key
```

### 3. Setup Database
```bash
# Generate Prisma client
npm run prisma:generate

# Run migrations
npm run prisma:migrate

# (Optional) Open Prisma Studio
npm run prisma:studio
```

### 4. Start Development Server
```bash
npm run dev
```

Server will run at: `http://127.0.0.1:4000`

## 🐛 Troubleshooting

### Database Connection Error
- ✅ Check MySQL is running
- ✅ Verify DB credentials in `.env`
- ✅ Database `dietai` exists

### CORS Error
- ✅ Update `CORS_ORIGINS` in `.env` with your frontend URL
- ✅ Separate multiple origins with commas

### Port Already in Use
```bash
# Change PORT in .env
PORT=5000
```

## 📝 Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | development | production/development |
| `PORT` | 4000 | Server port |
| `DB_HOST` | 127.0.0.1 | Database host |
| `DB_PORT` | 3306 | Database port |
| `DB_USER` | root | Database user |
| `DB_PASSWORD` | - | Database password |
| `DB_NAME` | dietai | Database name |
| `JWT_SECRET` | - | JWT signing secret |
| `CORS_ORIGINS` | http://localhost:3000 | Allowed origins |

## 🔒 Security Notes
- 🚨 **Never commit `.env` file**
- 🚨 Use strong `JWT_SECRET` in production
- 🚨 Change default database credentials
- 🚨 Rotate JWT_SECRET regularly
