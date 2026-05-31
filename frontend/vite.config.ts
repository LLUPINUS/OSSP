import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // cloudflared quick tunnel 도메인 허용 (없으면 Vite가 "Blocked request" 반환)
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
