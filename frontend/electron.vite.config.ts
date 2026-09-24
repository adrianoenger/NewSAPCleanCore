import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    envDir: resolve(__dirname, '..'),
    resolve: {
      alias: { '@': resolve(__dirname, 'src/renderer/src') }
    },
    server: { port: 5173, strictPort: true },
    plugins: [react(), tailwindcss()]
  }
})
