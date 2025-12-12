import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        timeout: 600000, // 10分钟超时（SSE连接需要长时间保持）
        ws: true, // 支持WebSocket
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            // 对于SSE请求，设置更长的超时
            if (req.url?.includes('/api/crawl')) {
              proxyReq.setTimeout(600000); // 10分钟
            }
          });
        }
      }
    }
  }
})







