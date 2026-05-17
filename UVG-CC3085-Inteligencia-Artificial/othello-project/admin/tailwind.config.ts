import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "hsl(48 38% 97%)",
        foreground: "hsl(154 18% 18%)",
        card: "hsl(0 0% 100%)",
        "card-foreground": "hsl(154 18% 18%)",
        primary: "hsl(152 54% 27%)",
        "primary-foreground": "hsl(48 38% 97%)",
        secondary: "hsl(44 50% 91%)",
        "secondary-foreground": "hsl(154 18% 18%)",
        muted: "hsl(45 21% 92%)",
        "muted-foreground": "hsl(155 8% 40%)",
        accent: "hsl(23 87% 56%)",
        "accent-foreground": "hsl(0 0% 100%)",
        border: "hsl(45 19% 83%)",
        input: "hsl(45 19% 83%)",
        ring: "hsl(152 54% 27%)",
        destructive: "hsl(0 72% 45%)",
        "destructive-foreground": "hsl(0 0% 98%)"
      },
      boxShadow: {
        panel: "0 18px 45px rgba(43, 62, 49, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
