import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/js/",

  build: {
    outDir: "app/static/js",
    emptyOutDir: true,

    rollupOptions: {
      input: "app/src/main.ts",

      output: {
        entryFileNames: "main.js",
        assetFileNames: "[name][extname]",
      },
    },
  },
});