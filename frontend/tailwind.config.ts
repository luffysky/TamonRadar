import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe6ff",
          500: "#3b6fe0",
          600: "#2f5597",
          700: "#244478",
        },
      },
    },
  },
  plugins: [],
};

export default config;
