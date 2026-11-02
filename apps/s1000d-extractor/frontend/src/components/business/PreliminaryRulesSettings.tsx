import { Button, Card, CardContent, CardHeader, CardTitle, Textarea } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiRequestError } from "../../lib/api/client";
import { formatApiError } from "../../lib/migrationUtils";
import {
  createRuleDraft, draftToGroups, parseExpressions, preliminaryRulesApi, preliminaryRulesQueryKey,
  removesExpressions, validRuleLists,
  type CategoryRuleDraft, type RuleKind, type RuleListChange, type RequirementRules,
} from "../../lib/preliminaryRules";

const queryKey = preliminaryRulesQueryKey;

export function PreliminaryRulesSettings() {
  const { t } = useTranslation();
  const contentId = useId();
  const [expanded, setExpanded] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const query = useQuery({ queryKey, queryFn: preliminaryRulesApi.read, refetchOnWindowFocus: false });
  return (
    <Card data-testid="preliminary-rules-panel">
      <CardHeader className="relative" data-testid="preliminary-rules-header">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1 basis-64">
            <CardTitle>{t("settingsRules.title")}</CardTitle>
            <p className="text-sm text-fg-dim">{t("settingsRules.summary")}</p>
            {hasUnsavedChanges ? <p className="mt-2 text-sm text-warning">{t("settingsRules.unsavedShort")}</p> : null}
          </div>
          <Button variant="secondary" size="sm" aria-expanded={expanded} aria-controls={contentId}
            className="after:absolute after:inset-0 after:cursor-pointer after:content-['']"
            onClick={() => setExpanded((value) => !value)}>
            {expanded ? <ChevronUp className="h-4 w-4" aria-hidden="true" />
              : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
            {t(expanded ? "settingsRules.collapse" : "settingsRules.expand")}
          </Button>
        </div>
      </CardHeader>
      <CardContent id={contentId} hidden={!expanded} className="space-y-4">
        <p className="text-sm text-fg-dim">{t("settingsRules.help")}</p>
        <p className="text-sm text-fg-dim">{t("settingsRules.priorities")}</p>
        {query.isPending ? <p role="status">{t("settingsRules.loading")}</p> : null}
        {query.isError ? (
          <div role="alert" className="space-y-2 text-danger">
            <p>{t("settingsRules.loadFailed")}: {formatApiError(t, query.error)}</p>
            <Button variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>
              {t("preliminary.retry")}
            </Button>
          </div>
        ) : null}
        {query.data ? <RulesEditor initial={query.data} onDirtyChange={setHasUnsavedChanges} /> : null}
      </CardContent>
    </Card>
  );
}

function RulesEditor({ initial, onDirtyChange }: {
  initial: RequirementRules;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(initial);
  const [draft, setDraft] = useState(() => createRuleDraft(initial.groups));
  const [armed, setArmed] = useState<"save" | "reload" | null>(null);
  const [reloading, setReloading] = useState(false);
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const dirty = JSON.stringify(draft) !== JSON.stringify(createRuleDraft(saved.groups));
  const groups = draftToGroups(draft);
  const valid = validRuleLists(groups);
  const removals = removesExpressions(saved.groups, groups);
  const changedElsewhere = saved.revision !== initial.revision;

  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (!dirty) return;
    const protect = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);

  const save = useMutation({
    mutationFn: () => preliminaryRulesApi.write({ revision: saved.revision, groups }),
    onSuccess: (next) => {
      setSaved(next);
      setDraft(createRuleDraft(next.groups));
      setFeedback({ error: false, message: t("settingsRules.saved", { revision: next.revision }) });
      queryClient.setQueryData(queryKey, next);
    },
    onError: (error: Error) => {
      const code = error instanceof ApiRequestError ? error.code : "";
      setFeedback({
        error: true,
        message: t(`settingsRules.errors.${code}`, { defaultValue: formatApiError(t, error) }),
      });
    },
  });
  const busy = save.isPending || reloading;
  const disarm = () => { clearTimeout(timer.current); setArmed(null); };
  const confirmAction = (target: "save" | "reload", action: () => void) => {
    if (armed !== target) {
      clearTimeout(timer.current);
      setArmed(target);
      timer.current = setTimeout(() => setArmed(null), 3000);
    } else {
      disarm();
      action();
    }
  };
  const update = (category: CategoryRuleDraft["category"], change: RuleListChange) => {
    setDraft((current) => current.map((entry) => entry.category === category ? {
      ...entry, [change.kind]: { ...entry[change.kind], [change.language]: change.text },
    } : entry));
    setFeedback(null);
    disarm();
  };
  const reload = async () => {
    setFeedback(null);
    setReloading(true);
    try {
      const next = await queryClient.fetchQuery({
        queryKey, queryFn: preliminaryRulesApi.read, staleTime: 0,
      });
      setSaved(next);
      setDraft(createRuleDraft(next.groups));
    } catch (error) {
      setFeedback({ error: true, message: formatApiError(t, error) });
    } finally {
      setReloading(false);
    }
  };
  const persist = () => { disarm(); setFeedback(null); save.mutate(); };
  const previewLanguage = i18n.language.startsWith("fr") ? "fr" : "en";

  return (
    <form className="space-y-4" aria-label={t("settingsRules.title")} onSubmit={(event) => {
      event.preventDefault();
      if (!valid || !dirty || busy || changedElsewhere) return;
      if (removals) confirmAction("save", persist);
      else persist();
    }}>
      <p className="text-sm text-fg-dim">{t("settingsRules.listHelp")}</p>
      <div className="space-y-3">
        {draft.map((category) => {
          const current = groups.filter((group) => group.category === category.category);
          const invalid = !validRuleLists(current);
          const preview = parseExpressions(category.keyword[previewLanguage]).slice(0, 5).join(", ");
          return (
            <details key={category.category} className="min-w-0 rounded-sm border border-md"
              data-testid={`rule-category-${category.category}`}>
              <summary className="cursor-pointer p-4">
                <span className="font-semibold">{t(`preliminary.category.${category.category}`)}</span>
                <span className="ml-3 text-sm text-fg-dim">{t("settingsRules.languageCount", {
                  fr: current.reduce((count, group) => count + group.fr.length, 0),
                  en: current.reduce((count, group) => count + group.en.length, 0),
                })}</span>
                <span className="mt-1 block truncate text-sm text-fg-dim">{preview || t("settingsRules.emptyCategory")}</span>
                {invalid ? <span className="mt-1 block text-sm text-danger">{t("settingsRules.required")}</span> : null}
              </summary>
              <div className="space-y-4 border-t border-md p-4">
                <CategoryLists draft={category} kind="keyword" disabled={busy}
                  onChange={(change) => update(category.category, change)} />
                <details>
                  <summary className="cursor-pointer text-sm text-fg-dim">{t("settingsRules.heading")}</summary>
                  <div className="mt-3">
                    <CategoryLists draft={category} kind="heading" disabled={busy}
                      onChange={(change) => update(category.category, change)} />
                  </div>
                </details>
              </div>
            </details>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={busy || !dirty || !valid || changedElsewhere} aria-busy={busy}>
          {t(busy ? "preliminary.saving" : armed === "save" ? "preliminary.confirmAgain" : "settingsRules.save")}
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={() => {
          if (dirty) confirmAction("reload", () => void reload());
          else void reload();
        }}>{t(armed === "reload" ? "preliminary.confirmAgain" : "settingsRules.reload")}</Button>
      </div>
      {dirty && removals ? <p className="text-sm text-warning">{t("settingsRules.confirmRemoval")}</p> : null}
      {!valid ? <p role="alert" className="text-danger">{t("settingsRules.required")}</p> : null}
      {changedElsewhere ? <p role="alert" className="text-warning">{t("settingsRules.changedElsewhere")}</p> : null}
      {feedback ? <p role={feedback.error ? "alert" : "status"} className={feedback.error ? "text-danger" : "text-success"}>
        {feedback.message}
      </p> : dirty ? <p role="status" className="text-warning">{t("settingsRules.unsaved")}</p> : null}
      <p className="text-sm text-fg-dim">{t("settingsRules.impact")}</p>
    </form>
  );
}

function CategoryLists({ draft, kind, disabled, onChange }: {
  draft: CategoryRuleDraft;
  kind: RuleKind;
  disabled: boolean;
  onChange: (change: RuleListChange) => void;
}) {
  const { t } = useTranslation();
  const helpId = useId();
  const values = draft[kind];
  const filled = parseExpressions(values.fr).length > 0 || parseExpressions(values.en).length > 0;
  return (
    <fieldset className="min-w-0 space-y-3" disabled={disabled}>
      <legend className={kind === "heading" ? "sr-only" : "text-sm font-semibold"}>{t(`settingsRules.${kind}`)}</legend>
      <p id={helpId} className="text-sm text-fg-dim">{t("settingsRules.onePerLine")}</p>
      <div className="grid gap-4 xl:grid-cols-2">
        {(["fr", "en"] as const).map((language) => (
          <label key={language} className="block min-w-0 space-y-2">
            <span>{t(language === "fr" ? "settingsRules.french" : "settingsRules.english")}</span>
            <Textarea lang={language} rows={5} value={values[language]} required={filled}
              aria-describedby={helpId} maxLength={201000}
              onChange={(event) => onChange({ kind, language, text: event.target.value })} />
            <span className="block text-sm text-fg-dim">{t("settingsRules.expressionCount", {
              count: parseExpressions(values[language]).length,
            })}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
