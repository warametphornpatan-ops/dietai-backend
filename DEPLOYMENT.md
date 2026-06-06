# 🚀 Production Deployment Guide

## ✅ Pre-Deployment Checklist

### 1. Environment Configuration
```bash
# Copy .env.production template
cp .env.production .env.production.local

# Update with your values:
# - DB_HOST: Your university database server IP
# - DB_USER: Database user (NOT root)
# - DB_PASSWORD: Strong password
# - JWT_SECRET: Generate new with: openssl rand -base64 32
# - CORS_ORIGINS: Your university domain
```

### 2. Database Setup
```bash
# Create database user (DO NOT USE ROOT)
mysql> CREATE USER 'dietai_user'@'localhost' IDENTIFIED BY 'STRONG_PASSWORD';
mysql> GRANT ALL ON dietai.* TO 'dietai_user'@'localhost';
mysql> FLUSH PRIVILEGES;

# Create tables (if not exists)
mysql> CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Install Dependencies
```bash
cd back-end
npm install --production
npm run build
```

### 4. Setup PM2
```bash
# Install PM2 globally (if not already)
npm install -g pm2

# Start with production config
pm2 start ecosystem.config.json --env production

# Make it restart on system reboot
pm2 startup
pm2 save
```

### 5. Setup Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name api.youruniversity.edu;

    location / {
        proxy_pass http://127.0.0.1:4000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6. Setup SSL Certificate (Let's Encrypt)
```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --nginx -d api.youruniversity.edu

# Auto-renew
sudo systemctl enable certbot.timer
```

## 🔐 Security Best Practices

✅ **Never commit .env files**
✅ **Use environment variables for secrets**
✅ **Rotate JWT_SECRET regularly**
✅ **Use HTTPS/SSL in production**
✅ **Setup firewall rules**
✅ **Enable rate limiting**
✅ **Monitor logs regularly**
✅ **Backup database daily**

## 📊 Monitoring

### PM2 Monitoring
```bash
pm2 monit              # Real-time monitoring
pm2 logs               # View logs
pm2 logs --lines 100   # Last 100 lines
pm2 delete all         # Stop all processes
```

### Check Server Status
```bash
pm2 list               # List processes
pm2 status             # Process status
pm2 info smart-carb-api
```

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check MySQL is running
systemctl status mysql

# Check connection
mysql -u dietai_user -p -h DB_HOST dietai

# Check firewall
sudo ufw allow 3306
```

### Port Already in Use
```bash
# Find process using port 4000
lsof -i :4000

# Kill process
kill -9 <PID>
```

### Check Logs
```bash
pm2 logs smart-carb-api
tail -f /var/log/syslog
```

## 📈 Performance Optimization

- Max memory: 500MB (configurable in ecosystem.config.json)
- Cluster mode: Enabled (scales with CPU cores)
- Connection pool: 10 connections
- Rate limiting: 100 requests per 15 minutes

## 🔄 Deployment Process

1. Pull latest code
2. Update .env.production
3. `npm install`
4. `npm run build`
5. `pm2 restart all`
6. Verify: `curl http://localhost:4000`
7. Check logs: `pm2 logs`

## 📞 Support Contacts

For issues:
- Database: Check DB server logs
- API: Check PM2 logs
- SSL: Check Certbot logs
- Nginx: Check `/var/log/nginx/error.log`
