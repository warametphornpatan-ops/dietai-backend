"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getNutritionData = getNutritionData;
exports.executeQuery = executeQuery;
const promise_1 = __importDefault(require("mysql2/promise"));
const config_1 = require("./config");
console.log('📦 Loading database module...');
console.log('🔧 Initializing database pool with config:', {
    host: config_1.config.database.host,
    port: config_1.config.database.port,
    user: config_1.config.database.user,
    database: config_1.config.database.database,
});
const pool = promise_1.default.createPool({
    host: config_1.config.database.host,
    user: config_1.config.database.user,
    password: config_1.config.database.password,
    database: config_1.config.database.database,
    port: config_1.config.database.port,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0,
});
console.log('📦 Database pool created');
// ทดสอบการเชื่อมต่อ (async)
(async () => {
    try {
        console.log('🔗 Testing database connection...');
        const conn = await pool.getConnection();
        console.log('✅ Database connected successfully');
        conn.release();
    }
    catch (err) {
        console.error('❌ Database connection error:', err.message);
    }
})();
console.log('📦 Database module initialized');
async function getNutritionData() {
    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query('SELECT * FROM nutrition_data');
        connection.release();
        const rowArray = Array.isArray(rows) ? rows : [];
        console.log("✅ Nutrition data retrieved:", rowArray.length, "records");
        return rowArray;
    }
    catch (error) {
        console.error("❌ Error fetching nutrition data:", error);
        throw error;
    }
}
async function executeQuery(query, values) {
    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query(query, values);
        connection.release();
        return rows;
    }
    catch (error) {
        console.error("❌ Database query error:", error);
        throw error;
    }
}
exports.default = pool;
//# sourceMappingURL=database.js.map