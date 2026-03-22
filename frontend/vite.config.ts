import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [
      'localhost',
      '0.0.0.0',
      'graciela-noninterdependent-lukewarmly.ngrok-free.dev',
      '*.ngrok-free.dev',
    ],
  },
})
