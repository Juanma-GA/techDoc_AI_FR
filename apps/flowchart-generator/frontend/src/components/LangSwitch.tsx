import { Button, cn } from "@internal/ui";
import { useTranslation } from "react-i18next";

const LANGS = ["fr", "en"] as const;

export function LangSwitch({ vertical = false }: { vertical?: boolean }) {
  const { i18n } = useTranslation();
  const current = i18n.resolvedLanguage ?? "fr";
  return (
    <div className={cn("flex gap-1", vertical && "flex-col")}>
      {LANGS.map((lang) => (
        <Button
          key={lang}
          size="sm"
          variant={current === lang ? "primary" : "ghost"}
          onClick={() => void i18n.changeLanguage(lang)}
          aria-pressed={current === lang}
        >
          {lang.toUpperCase()}
        </Button>
      ))}
    </div>
  );
}
