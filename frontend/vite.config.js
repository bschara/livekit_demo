import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Bind all interfaces, not just localhost, so other devices on the LAN
  // (e.g. a phone) can reach the dev server for testing.
  server: {
    host: '0.0.0.0',
  },
})
