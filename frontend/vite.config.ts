import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const variant = env.VITE_VARIANT || mode;
  const ports: Record<string, number> = { user: 5173, vendor: 5174, admin: 5175 };
  const selectedPort = ports[variant] ?? 5173;
  return {
    build: {
      // Keep build output inside the frontend directory so Vercel can serve it
      outDir: variant ? `dist/${variant}` : 'dist',
      emptyOutDir: true,
    },
    server: {
      port: selectedPort,
      strictPort: true,
      host: '127.0.0.1',
    },
    define: {
      'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      }
    },
    plugins: [react()],
  };
});
