import type { Config } from "tailwindcss";

import preset from "@internal/design-tokens/tailwind-preset";

export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../../../packages/ui/src/**/*.{ts,tsx}",
  ],
} satisfies Config;
