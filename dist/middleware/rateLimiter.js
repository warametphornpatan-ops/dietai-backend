"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadLimiter = exports.authLimiter = exports.apiLimiter = exports.createRateLimiter = void 0;
const express_rate_limit_1 = __importDefault(require("express-rate-limit"));
const createRateLimiter = (windowMs, max) => {
    return (0, express_rate_limit_1.default)({
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
exports.createRateLimiter = createRateLimiter;
exports.apiLimiter = (0, exports.createRateLimiter)(15 * 60 * 1000, 100); // 100 requests per 15 minutes
exports.authLimiter = (0, exports.createRateLimiter)(15 * 60 * 1000, 5); // 5 requests per 15 minutes (prevent brute force)
exports.uploadLimiter = (0, exports.createRateLimiter)(60 * 60 * 1000, 20); // 20 uploads per hour
//# sourceMappingURL=rateLimiter.js.map