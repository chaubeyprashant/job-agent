/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      colors: {
        surface: {
          900: "#0c0f14",
          800: "#131820",
          700: "#1a2130",
          600: "#222b3d",
        },
        ink: {
          50: "#f4f6fa",
          100: "#e2e7f0",
          200: "#c5cedc",
          300: "#9aa8bd",
          400: "#6b7a92",
        },
        brand: {
          DEFAULT: "#3d9cf0",
          dim: "#2563a8",
          glow: "#7ec8ff",
        },
        accent: "#f4b942",
      },
      boxShadow: {
        panel: "0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,0.04)",
        lift: "0 8px 32px rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};
