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
        border: "#e2ddd5",
        muted: "#f3efe8",
        "muted-foreground": "#64748b",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
      animation: {
        "pulse-gold": "pulse-gold 2s ease-in-out infinite",
      },
      keyframes: {
        "pulse-gold": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
      },
    },
  },
  plugins: [],
};

export default config;