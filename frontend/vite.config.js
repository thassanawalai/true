import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // รองรับการเปิดผ่าน Cloud Shell Web Preview
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8080', // ส่ง /api ไปหา FastAPI อัตโนมัติ
    },
  },
})