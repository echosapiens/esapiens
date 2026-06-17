import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: "#f9f7f4",
          50: "#fdfcfa",
          100: "#f9f7f4",
          200: "#f3efe8",
          300: "#ebe4d7",
          400: "#ddd2be",
          500: "#c9bda5",
          600: "#b5a689",
          700: "#96876d",
          800: "#7a6d59",
          900: "#645a49",
        },
        navy: {
          DEFAULT: "#0f1b2d",
          50: "#e8ecf2",
          100: "#c5cdd9",
          200: "#9dabbe",
          300: "#7589a4",
          400: "#566e8f",
          500: "#375479",
          600: "#2a4060",
          700: "#1e2f47",
          800: "#152338",
          900: "#0f1b2d",
        },
        gold: {
          DEFAULT: "#c9a84c",
          50: "#faf6eb",
          100: "#f3eacc",
          200: "#e9d698",
          300: "#dfc266",
          400: "#d5b24e",
          500: "#c9a84c",
          600: "#a98a3c",
          700: "#896c2f",
          800: "#6b5424",
          900: "#503e1a",
        },
        /* ── macOS system colors ─────────────────────────────────── */
        system: {
          red: "#ff3b30",
          orange: "#ff9500",
          yellow: "#ffcc00",
          green: "#34c759",
          blue: "#007aff",
          purple: "#af52de",
          pink: "#ff2d55",
          gray: {
            DEFAULT: "#8e8e93",
            50: "#f2f2f7",
            100: "#e5e5ea",
            200: "#d1d1d6",
            300: "#c7c7cc",
            400: "#aeaeb2",
            500: "#8e8e93",
            600: "#636366",
            700: "#48484a",
            800: "#3a3a3c",
            900: "#1c1c1e",
          },
        },
        border: "rgba(0,0,0,0.08)",
        muted: "rgba(0,0,0,0.04)",
        "muted-foreground": "#64748b",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["Roboto Mono", "SF Mono", "monospace"],
      },
      fontSize: {
        mac: "13px",
        "mac-sm": "11px",
        "mac-lg": "15px",
      },
      animation: {
        "mac-sheet-in": "mac-sheet-in 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
        "mac-shimmer": "mac-shimmer 1.5s ease-in-out infinite",
      },
      keyframes: {
        "mac-sheet-in": {
          from: { opacity: "0", transform: "translateY(12px) scale(0.97)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        "mac-shimmer": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;