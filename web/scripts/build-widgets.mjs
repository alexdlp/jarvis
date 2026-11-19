import { readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { build } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// Locate web/ independently of the terminal's working directory.
const root = fileURLToPath(new URL("../", import.meta.url));

// Each HTML file in web/ defines an independent widget.
const files = await readdir(root, { withFileTypes: true });
const widgets = files
  .filter((file) => file.isFile() && file.name.endsWith(".html"))
  .map((file) => file.name)
  .sort();

if (widgets.length === 0) {
  throw new Error("No widget HTML entry points were found.");
}

for (const [index, widget] of widgets.entries()) {
  await build({
    root,
    configFile: false,
    plugins: [react(), viteSingleFile()],
    build: {
      outDir: "dist",

      // Clear previous output once, preserving widgets built afterward.
      emptyOutDir: index === 0,

      rolldownOptions: {
        input: resolve(root, widget),
      },
    },
  });
}
