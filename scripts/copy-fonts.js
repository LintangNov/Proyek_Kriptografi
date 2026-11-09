// Menyalin font ke frontend/assets/fonts agar aplikasi desktop tetap utuh tanpa internet.
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const target = path.join(root, "frontend", "assets", "fonts");
fs.mkdirSync(target, { recursive: true });

const fonts = [
  ["plus-jakarta-sans", [400, 500, 600, 700]],
  ["jetbrains-mono", [400, 500]],
];

for (const [family, weights] of fonts) {
  for (const weight of weights) {
    const file = `${family}-latin-${weight}-normal.woff2`;
    fs.copyFileSync(path.join(root, "node_modules", "@fontsource", family, "files", file), path.join(target, file));
    console.log("copied", file);
  }
}
