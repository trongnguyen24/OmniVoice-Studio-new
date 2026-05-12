import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import path from 'path'
import { readFileSync } from 'fs'

const pkg = JSON.parse(readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'));

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  clearScreen: false,
  resolve: {
    preserveSymlinks: false,
    alias: {
      '@tauri-apps/plugin-dialog': path.resolve(__dirname, 'node_modules/@tauri-apps/plugin-dialog/dist-js/index.js'),
    },
  },
  server: {
    port: 3901,
    strictPort: true,
    host: false,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
})
