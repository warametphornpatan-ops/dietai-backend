/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        // เมื่อหน้าบ้านเรียกไปที่ /api/... 
        source: '/api/:path*',
        // ให้ Next.js ส่งต่อไปที่ Backend (Python) ที่พอร์ต 8000 ให้เอง
        destination: 'http://127.0.0.1:8000/:path*', 
      },
    ];
  },
};

export default nextConfig;