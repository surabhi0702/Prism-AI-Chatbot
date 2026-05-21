/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html","./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void:    "var(--bg-main)",
        bg1:     "var(--bg-card)",
        bg2:     "var(--bg-card)",
        bg3:     "var(--bg-card)",
        bg4:     "var(--bg-card)",
        line:    "var(--border)",
        line2:   "var(--border)",
        ink:     "var(--text-main)",
        ink2:    "var(--text-dim)",
        ink3:    "var(--text-dim)",
        gold:    "var(--accent)",
        silver:  "#60A5FA",
        grn:     "#34D399",
        red:     "#F05252",
        ora:     "var(--accent)",
        pur:     "#A78BFA",
        pink:    "#F472B6",
        teal:    "#2DD4BF",
        amber:   "#FBBF24",
      },
      fontFamily: {
        sans:  ["'DM Sans'", "sans-serif"],
        mono:  ["'Fira Code'", "monospace"],
        disp:  ["'Syne'", "sans-serif"],
      },
    },
  },
  plugins: [],
}
