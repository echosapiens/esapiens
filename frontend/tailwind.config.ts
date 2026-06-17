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
        surface: {
          DEFAULT: "#0f1522",
          raised: "#18202f",
          hover: "#1e2840",
          active: "#25304a",
        },
        accent: {
          blue: "#3b82f6",
          green: "#22c55e",
          red: "#ef4444",
          purple: "#a855f7",
          orange: "#f59e0b",
          cyan: "#06b6d4",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["Roboto Mono", "SF Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        xs: ["11px", "16px"],
        sm: ["13px", "20px"],
        base: ["14px", "22px"],
        lg: ["16px", "24px"],
        xl: ["20px", "28px"],
        "2xl": ["24px", "32px"],
      },
      boxShadow: {
        gold: "0 0 12px rgba(201, 168, 76, 0.15)",
      },
    },
  },
  plugins: [],
};

export default config;