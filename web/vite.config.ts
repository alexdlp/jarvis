import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Development configuration. Production widgets are built independently by
// scripts/build-widgets.mjs, which discovers their HTML entry points.
export default defineConfig({
  plugins: [react()],
})
