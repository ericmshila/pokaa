import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Listen on all interfaces (not just localhost) so the dev
    // server is reachable from other devices on the same LAN, or
    // over a virtual LAN like Hamachi/Tailscale — not just this
    // machine. Combine with `uvicorn --host 0.0.0.0` on the backend.
    host: true,
  },
})
