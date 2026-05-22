import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import { resolve } from 'path';
import preact from '@preact/preset-vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [preact()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    esbuild: {
      drop: mode === 'production' ? ['console', 'debugger'] : [],
    },
    build: {
      outDir: 'dist',
      rollupOptions: {
        input: {
          main: resolve(__dirname, 'index.html'),
          'oauth-callback': resolve(__dirname, 'oauth-callback.html'),
          background: resolve(__dirname, 'src/background.ts'),
        },
        output: { entryFileNames: '[name].js' },
      },
    },
    define: {
      __BACKEND_ORIGIN__: JSON.stringify(env.VITE_BACKEND_ORIGIN ?? 'http://localhost:8000'),
    },
  };
});
