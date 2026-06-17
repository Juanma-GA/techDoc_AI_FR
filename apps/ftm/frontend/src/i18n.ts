/**
 * i18n — FTM Agent.
 *
 * Source de verite des libelles : le bundle backend `/api/v1/i18n/{lang}` (cles
 * a plat type "nav.manager"), recupere au runtime et fusionne par-dessus les
 * locales frontend embarquees (fallback app-shell : erreurs, ErrorBoundary…).
 * Memes cles que la preview HTML => parite garantie. FR + EN. La langue active
 * est persistee dans localStorage["ftm-lang"] (meme cle que la preview).
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import fr from "./locales/fr.json";

const STORAGE_KEY = "ftm-lang";
const SUPPORTED = ["fr", "en"] as const;
type Lang = (typeof SUPPORTED)[number];

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

/**
 * "nav.manager" => { nav: { manager } } : deplie le bundle plat du backend en
 * structure imbriquee pour rester compatible avec le keySeparator "." d'i18next
 * (et donc cohabiter avec les locales frontend imbriquees).
 */
function unflatten(flat: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(flat)) {
    const parts = key.split(".");
    const leaf = parts.pop();
    if (leaf === undefined) continue;
    let node = out;
    for (const p of parts) {
      if (typeof node[p] !== "object" || node[p] === null) node[p] = {};
      node = node[p] as Record<string, unknown>;
    }
    node[leaf] = value;
  }
  return out;
}

const loaded: Record<string, boolean> = {};

/**
 * Recupere le bundle backend pour `lang`, le deplie et le fusionne (deep merge,
 * overwrite) par-dessus les locales embarquees. Idempotent par langue.
 * Silencieux si le backend est injoignable : on garde le fallback embarque.
 */
async function loadBackendBundle(lang: string): Promise<void> {
  if (loaded[lang]) return;
  try {
    const res = await fetch(`${API_BASE}/i18n/${lang}`);
    if (!res.ok) return;
    const data = (await res.json()) as { translations?: Record<string, string> };
    const dict = data.translations ?? {};
    if (Object.keys(dict).length > 0) {
      i18n.addResourceBundle(lang, "translation", unflatten(dict), true, true);
      loaded[lang] = true;
    }
  } catch {
    // Backend injoignable : fallback sur les locales frontend embarquees.
  }
}

function storedLang(): Lang {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "en" || v === "fr" ? v : "fr";
}

/**
 * Initialise i18next avec les locales embarquees, puis fusionne le bundle
 * backend (FR + langue active) AVANT le premier render pour eviter tout flash
 * de cle brute. A appeler une seule fois depuis `main.tsx`.
 */
export async function initI18n(): Promise<void> {
  const lng = storedLang();
  await i18n.use(initReactI18next).init({
    resources: {
      fr: { translation: fr },
      en: { translation: en },
    },
    lng,
    fallbackLng: "fr",
    supportedLngs: SUPPORTED as unknown as string[],
    interpolation: { escapeValue: false },
    returnEmptyString: false,
  });
  await loadBackendBundle("fr");
  if (lng !== "fr") await loadBackendBundle(lng);
}

/**
 * Change la langue active : charge le bundle backend si besoin, applique et
 * persiste. Utilise par le switcher FR/EN du sidebar.
 */
export async function setAppLanguage(lang: Lang): Promise<void> {
  await loadBackendBundle(lang);
  await i18n.changeLanguage(lang);
  localStorage.setItem(STORAGE_KEY, lang);
}

export { SUPPORTED as SUPPORTED_LANGS };
export type { Lang };
export default i18n;
