import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/r2-movies': {
        target: 'https://pub-26547a0f0f74415f9e77724b24edd8fe.r2.dev',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/r2-movies/, ''),
      },
    },
  },
})
