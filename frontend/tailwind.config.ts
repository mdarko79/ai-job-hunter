import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "serif"],
        mono: ["var(--font-mono)", "monospace"]
      },
      colors: {
        ink: {
          950: "#05060A",
          900: "#0A0C14",
          800: "#10131D",
          700: "#181C28",
          600: "#222637",
          500: "#2D3245"
        },
        accent: {
          DEFAULT: "#3DF5C0",
          glow: "#5BFFD4",
          dim: "#1FB792"
        },
        electric: {
          DEFAULT: "#4D8DFF",
          glow: "#7AAEFF"
        },
        warn: "#FFB454",
        danger: "#FF5C7A",
        purple: "#B78AFF"
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)"
      },
      backgroundSize: {
        "grid-32": "32px 32px"
      },
      boxShadow: {
        glow: "0 0 40px -12px rgba(61,245,192,0.45)",
        "glow-blue": "0 0 40px -12px rgba(77,141,255,0.55)"
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-up": "fadeUp 0.5s ease-out forwards",
        shimmer: "shimmer 2.5s linear infinite"
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" }
        }
      }
    }
  },
  plugins: []
};

export default config;
