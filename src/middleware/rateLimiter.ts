import rateLimit from 'express-rate-limit';

export const createRateLimiter = (windowMs: number, max: number) => {
  return rateLimit({
    windowMs,
    max,
    message: '⚠️ ลองเยอะเกินไป โปรดรอสักครู่',
    standardHeaders: true,
    legacyHeaders: false,
    skip: (req) => {
      // Skip rate limiting for health checks
      return req.path === '/' || req.path === '/api/health/db';
    },
  });
};

export const apiLimiter = createRateLimiter(15 * 60 * 1000, 100); // 100 requests per 15 minutes
export const authLimiter = createRateLimiter(15 * 60 * 1000, 5); // 5 requests per 15 minutes (prevent brute force)
export const uploadLimiter = createRateLimiter(60 * 60 * 1000, 20); // 20 uploads per hour
