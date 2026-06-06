import { PrismaClient } from "@prisma/client";

console.log("📦 Loading database module...");

const prisma = new PrismaClient({
  log: process.env.NODE_ENV === "development" 
    ? ["query", "error", "warn"] 
    : ["error"],
});

// Test database connection
(async () => {
  try {
    console.log("🔗 Testing database connection...");
    await prisma.$executeRawUnsafe("SELECT 1");
    console.log("✅ Database connected successfully");
  } catch (err: any) {
    console.error("❌ Database connection error:", err.message);
  }
})();

console.log("📦 Database module initialized");

export { prisma };
export default prisma;
