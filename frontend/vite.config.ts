import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5469', // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
        changeOrigin: true,
        secure: false,
        ws: false, // WebSocket not needed for SSE
        // Keep the /api prefix - don't rewrite since backend expects /api/...
        // Vite proxy by default forwards /api/* to target/api/*
        rewrite: (path) => path,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Proxying request:', req.method, req.url, '→', 'http://127.0.0.1:5469' + req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('Proxy response:', req.method, req.url, 'Status:', proxyRes.statusCode);
          });
        },
      },
    },
  },
})
