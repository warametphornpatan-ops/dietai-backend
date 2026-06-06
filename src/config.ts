import dotenv from "dotenv";
import path from "path";

// Load environment-specific .env file
const envFile = process.env.NODE_ENV === "production" 
  ? path.join(process.cwd(), ".env.production") 
  : path.join(process.cwd(), ".env");

console.log(`📦 Loading environment from: ${envFile}`);
dotenv.config({ path: envFile });

export const config = {
  port: Number(process.env.PORT) || 4000,
  nodeEnv: process.env.NODE_ENV || "development",
  
  // Database - now using DATABASE_URL (Supabase)
  database: {
    url: process.env.DATABASE_URL || "postgresql://localhost/dietai",
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

  // Supabase
  supabase: {
    url: process.env.SUPABASE_URL,
    key: process.env.SUPABASE_KEY,
  },
};

// Validate critical config
const validateConfig = () => {
  const required = ["DATABASE_URL", "JWT_SECRET"];
  const missing = required.filter(key => !process.env[key]);
  
  if (missing.length > 0 && process.env.NODE_ENV === "production") {
    console.error(`❌ Missing environment variables: ${missing.join(", ")}`);
    process.exit(1);
  }
};

validateConfig();
