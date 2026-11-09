/** Token mengikuti file Figma "AegisVault Design System". */
module.exports = {
  content: ["./frontend/index.html", "./frontend/app.js", "./frontend/dev-mock.js"],
  // Nama kelas ini dirangkai saat runtime di app.js, jadi Tailwind tidak bisa menemukannya sendiri.
  safelist: ["badge-ok", "badge-bad", "badge-warn", "badge-neutral", "btn-primary", "btn-secondary", "btn-ghost", "btn-danger"],
  theme: {
    extend: {
      colors: {
        canvas: "#F5F6F8",
        surface: "#FFFFFF",
        muted: "#EEF0F4",
        strong: "#E5E8F0",
        selected: "#D5DBE0",
        line: "#878D99",
        ink: "#1A1D24",
        ink2: "#555B67",
        ink3: "#656B77",
        amber: { 50: "#FFF8EB", 100: "#FFEDC7", 300: "#FFC34D", 400: "#F9AE1F", 500: "#EE9208", 700: "#9A4E08", 800: "#7C3E0D" },
        ok: { bg: "#ECFDF5", line: "#059669", text: "#065F46" },
        bad: { bg: "#FEF2F2", line: "#DC2626", text: "#991B1B" },
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      fontSize: {
        display: ["32px", { lineHeight: "40px", fontWeight: "700" }],
        h1: ["24px", { lineHeight: "32px", fontWeight: "700" }],
        h2: ["20px", { lineHeight: "28px", fontWeight: "700" }],
        h3: ["16px", { lineHeight: "24px", fontWeight: "600" }],
        reading: ["16px", { lineHeight: "26px" }],
        body: ["14px", { lineHeight: "22px" }],
        label: ["13px", { lineHeight: "18px", fontWeight: "600" }],
        caption: ["12px", { lineHeight: "16px", fontWeight: "500" }],
      },
      boxShadow: {
        card: "0 1px 2px rgba(26,30,46,.03), 0 4px 16px rgba(26,30,46,.04)",
        raised: "0 12px 36px rgba(26,30,46,.14)",
      },
    },
  },
  plugins: [],
};
