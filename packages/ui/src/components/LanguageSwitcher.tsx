import { cn } from "../lib/utils";

export type LanguageSwitcherProps = {
  languages: readonly string[];
  currentLanguage: string;
  onLanguageChange: (language: string) => void;
  ariaLabel?: string;
};

export function LanguageSwitcher({
  languages,
  currentLanguage,
  onLanguageChange,
  ariaLabel = "Language",
}: LanguageSwitcherProps) {
  return (
    <div className="ui-language-switch" role="group" aria-label={ariaLabel}>
      {languages.map((language) => {
        const isActive = currentLanguage === language;

        return (
          <button
            key={language}
            type="button"
            className={cn("ui-language-button", isActive && "ui-language-button-active")}
            aria-pressed={isActive}
            onClick={() => onLanguageChange(language)}
          >
            {language.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}