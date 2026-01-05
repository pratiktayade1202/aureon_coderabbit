/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        paper: {
          canvas: "#F3F4F6",
          surface: "#FFFFFF",
          cream: "#FDFCF8",
        },
        ink: {
          DEFAULT: "#0F172A",
          strong: "#0F172A",
          muted: "#64748B",
          faint: "#94A3B8",
        },
        aureon: {
          gold: "#B45309",
          blue: "#2563EB",
          border: "#CBD5E1",
        },
        status: {
          success: "#059669",
          danger: "#B91C1C",
          warning: "#D97706",
        },
      },
      boxShadow: {
        none: "none",
        subtle: "0 1px 0 0 rgba(15, 23, 42, 0.06)",
      },
      borderRadius: {
        sm: "0.125rem",
        md: "0.25rem",
        lg: "0.5rem",
        xl: "0.5rem",
        "2xl": "0.5rem",
      },
    },
  },
  plugins: [],
};
