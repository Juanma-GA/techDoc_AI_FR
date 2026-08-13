import type { Config } from "tailwindcss";

import preset from "@internal/design-tokens/tailwind-preset";

export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../../../packages/ui/src/**/*.{ts,tsx}",
  ],
  safelist: [
    "ct",
    "layout",
    "sidebar",
    "sidebar-header",
    "brand",
    "nav-group",
    "nav-group-title",
    "nav-item",
    "lang-switch",
    "lang-btn",
    "page-header",
    "label",
  ],
} satisfies Config;
