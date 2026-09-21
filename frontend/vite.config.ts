import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    // CVE-2026-39364 reproduction lab
    host: '0.0.0.0',

    fs: {
      allow: [
        fileURLToPath(new URL('.', import.meta.url)),
      ],

      deny: [
        '**/cve-lab/secret.env',
      ],
    },

    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})