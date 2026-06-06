"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = void 0;
const dotenv_1 = __importDefault(require("dotenv"));
const path_1 = __importDefault(require("path"));
// Load environment-specific .env file
const envFile = process.env.NODE_ENV === "production"
    ? path_1.default.join(process.cwd(), ".env.production")
    : path_1.default.join(process.cwd(), ".env");
console.log(`📦 Loading environment from: ${envFile}`);
dotenv_1.default.config({ path: envFile });
exports.config = {
    port: Number(process.env.PORT) || 4000,
    nodeEnv: process.env.NODE_ENV || "development",
    // Database
    database: {
        host: process.env.DB_HOST || "localhost",
        port: Number(process.env.DB_PORT) || 3306,
        user: process.env.DB_USER || "root",
        password: process.env.DB_PASSWORD || "",
        database: process.env.DB_NAME || "dietai",
    },
    // JWT
    jwt: {
        secret: process.env.JWT_SECRET || "your-secret-key-change-in-production",
        expiresIn: process.env.JWT_EXPIRES_IN || "24h",
    },
    // CORS
    cors: {
        origin: (process.env.CORS_ORIGINS || "http://localhost:3000").split(","),
        credentials: true,
    },
    // API
    api: {
        prefix: "/api",
    },
};
// Validate critical config
const validateConfig = () => {
    const required = ["DB_HOST", "DB_USER", "DB_NAME", "JWT_SECRET"];
    const missing = required.filter(key => !process.env[key]);
    if (missing.length > 0 && process.env.NODE_ENV === "production") {
        console.error(`❌ Missing environment variables: ${missing.join(", ")}`);
        process.exit(1);
    }
};
validateConfig();
//# sourceMappingURL=config.js.map