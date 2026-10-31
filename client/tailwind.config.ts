import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F7F5EF",
        ink: "#1E2420",
        muted: "#5E665F",
        line: "#E3DED2",
        primary: { DEFAULT: "#1F7A4D", soft: "#E3F1E8", dark: "#175C3A" },
        warn: { DEFAULT: "#C77700", soft: "#FFF1D6" },
        danger: { DEFAULT: "#B3261E", soft: "#FBE4E2" },
        info: { DEFAULT: "#2457D6", soft: "#E3EBFD" },
      },
      borderRadius: { card: "16px" },
      fontFamily: {
        sans: ['"Noto Sans"', '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
      },
      fontSize: { base: ["17px", "1.5"] },
    },
  },
  plugins: [],
};
export default config;
