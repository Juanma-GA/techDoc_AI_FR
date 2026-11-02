import { useState } from "react";
import type { TFunction } from "i18next";
import {
  AlertCircle,
  CheckCircle2,
  FileUp,
  Loader2,
  Trash2,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  SelectMenu,
} from "@internal/ui";

import type {
  DmValidationResult,
  DmValidationStatus,
  DmValidationViolation,
} from "../lib/api";
import { collectDroppedFiles } from "../lib/validationDrop";

export type ValidationItem = Omit<DmValidationResult, "status"> & {
  id: string;
  file: File | null;
  generated?: { docId: string; dmId: string };
  displayName: string;
  status: DmValidationStatus | "checking";
};

type Props = {
  items: ValidationItem[];
  visibleItems: ValidationItem[];
  selected: ValidationItem | null;
  errorsOnly: boolean;
  pendingCount: number;
  progress: { completed: number; total: number };
  validCount: number;
  invalidCount: number;
  unverifiableCount: number;
  onErrorsOnlyChange: (checked: boolean) => void;
  onSelectItem: (id: string) => void;
  onClear: () => void;
  onChooseIssue: (item: ValidationItem, issue: string) => void;
  onRemove: (id: string) => void;
  onImport: (files: File[]) => void;
  onError: (error: unknown) => void;
};

const ISSUES = ["4.1", "4.2"] as const;

function statusVariant(status: ValidationItem["status"]): "success" | "warning" | "info" {
  if (status === "valid") return "success";
  if (status === "invalid" || status === "unverifiable") return "warning";
  return "info";
}

function statusIcon(status: ValidationItem["status"]) {
  if (status === "valid") return <CheckCircle2 aria-hidden="true" size={15} />;
  if (status === "invalid" || status === "unverifiable")
    return <AlertCircle aria-hidden="true" size={15} />;
  return <Loader2 aria-hidden="true" className="s1k-validation-spin" size={15} />;
}

function errorTypes(item: ValidationItem, t: TFunction): string {
  const rules = [...new Set(
    item.violations.filter((violation) => violation.severity === "error").map((value) => value.rule),
  )];
  if (rules.length) return rules.join(", ");
  if (item.status === "unverifiable") return t("validation.status.unverifiable");
  if (item.status === "needs_issue") return t("validation.status.needsIssue");
  return t("common.none");
}

function locationLabel(violation: DmValidationViolation, t: TFunction) {
  if (violation.line == null) return violation.path || "/";
  const line = t("validation.line", { line: violation.line });
  return violation.column == null ? line : `${line}:${violation.column}`;
}

export function ValidationResults({
  items,
  visibleItems,
  selected,
  errorsOnly,
  pendingCount,
  progress,
  validCount,
  invalidCount,
  unverifiableCount,
  onErrorsOnlyChange,
  onSelectItem,
  onClear,
  onChooseIssue,
  onRemove,
  onImport,
  onError,
}: Props) {
  const { t } = useTranslation();
  const [listDragging, setListDragging] = useState(false);

  const importDroppedFiles = async (dataTransfer: DataTransfer) => {
    try {
      onImport(await collectDroppedFiles(dataTransfer));
    } catch (error) {
      onError(error);
    }
  };

  return (
    <>
      {progress.total ? (
        <p role="status" aria-live="polite">{t("validation.progress", progress)}</p>
      ) : null}

      <div className="s1k-validation-summary" aria-live="polite">
        <span>{t("validation.summary.documents", { count: items.length })}</span>
        <Badge variant="success">{t("validation.summary.valid", { count: validCount })}</Badge>
        <Badge variant={invalidCount ? "warning" : "info"}>
          {t("validation.summary.invalid", { count: invalidCount })}
        </Badge>
        <Badge variant="info">
          {t("validation.summary.unverifiable", { count: unverifiableCount })}
        </Badge>
        {items.length ? (
          <label className="s1k-validation-error-filter">
            <Checkbox
              checked={errorsOnly}
              onCheckedChange={onErrorsOnlyChange}
              aria-label={t("validation.filterErrorsOnly")}
            />
            <span>{t("validation.filterErrorsOnly")}</span>
          </label>
        ) : null}
        {pendingCount ? (
          <span className="s1k-validation-pending text-label font-mono uppercase text-fg-dim" role="status">
            <Loader2 aria-hidden="true" className="s1k-validation-spin" size={14} />
            {t("validation.pending", { count: pendingCount })}
          </span>
        ) : null}
        {items.length ? (
          <Button type="button" variant="ghost" size="sm" className="s1k-validation-clear"
            onClick={onClear}>
            <Trash2 aria-hidden="true" size={14} /> {t("validation.clear")}
          </Button>
        ) : null}
      </div>

      <div className="s1k-validation-grid">
        <Card className="s1k-validation-list-panel" role="region" aria-labelledby="validation-list-title">
          <CardHeader>
            <CardTitle id="validation-list-title">
              {t("validation.listTitle", { count: visibleItems.length })}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1">
            {visibleItems.length ? (
              <div className="s1k-validation-table-scroll">
                <table className="s1k-validation-table">
                  <thead>
                    <tr>
                      <th>{t("validation.columns.parsing")}</th>
                      <th>{t("validation.columns.dmc")}</th>
                      <th>{t("validation.columns.version")}</th>
                      <th>{t("validation.columns.schema")}</th>
                      <th>{t("validation.columns.errorType")}</th>
                      <th>{t("validation.columns.errorCount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleItems.map((item) => (
                      <tr
                        key={item.id}
                        className={item.id === selected?.id ? "s1k-validation-is-selected" : ""}
                        aria-selected={item.id === selected?.id}
                        tabIndex={0}
                        onClick={() => onSelectItem(item.id)}
                        onKeyDown={(event) => {
                          if (event.target !== event.currentTarget) return;
                          if (event.key !== "Enter" && event.key !== " ") return;
                          event.preventDefault();
                          onSelectItem(item.id);
                        }}
                      >
                        <td>
                          <Badge variant={statusVariant(item.status)}>
                            {statusIcon(item.status)} {t(`validation.status.${item.status}`)}
                          </Badge>
                        </td>
                        <td>
                          <Button type="button" variant="ghost" className="s1k-validation-row-select"
                            title={item.displayName} onClick={() => onSelectItem(item.id)}>
                            <strong>{item.dmc || item.displayName}</strong>
                            {item.dmc ? <small>{item.displayName}</small> : null}
                          </Button>
                        </td>
                        <td>
                          {item.status === "needs_issue" ? (
                            <SelectMenu
                              triggerClassName="s1k-validation-issue-select"
                              value={item.issue ?? ""}
                              label={t("validation.chooseIssueFor", { filename: item.displayName })}
                              onValueChange={(issue) => {
                                if (issue) onChooseIssue(item, issue);
                              }}
                              options={[
                                { value: "", label: t("validation.chooseIssue") },
                                ...ISSUES.map((issue) => ({ value: issue, label: issue })),
                              ]}
                            />
                          ) : item.issue ? `Issue ${item.issue}` : t("common.none")}
                        </td>
                        <td>{item.schema || t("common.none")}</td>
                        <td className="s1k-validation-error-type">{errorTypes(item, t)}</td>
                        <td className="s1k-validation-count-cell">
                          <Badge variant={item.error_count ? "warning" : "success"}>
                            {item.error_count}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div
                data-testid="validation-empty-list"
                className={`s1k-validation-empty-list${items.length === 0 ? " s1k-validation-empty-drop" : ""}${listDragging ? " s1k-validation-is-dragging" : ""}`}
                onDragEnter={(event) => {
                  if (items.length) return;
                  event.preventDefault();
                  setListDragging(true);
                }}
                onDragOver={(event) => {
                  if (items.length) return;
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "copy";
                }}
                onDragLeave={(event) => {
                  if (items.length || event.currentTarget.contains(event.relatedTarget as Node | null)) return;
                  setListDragging(false);
                }}
                onDrop={(event) => {
                  if (items.length) return;
                  event.preventDefault();
                  setListDragging(false);
                  void importDroppedFiles(event.dataTransfer);
                }}
              >
                {items.length ? (
                  <>
                    <CheckCircle2 aria-hidden="true" size={24} />
                    <span>{t("validation.noErrorsToShow")}</span>
                  </>
                ) : (
                  <>
                    <FileUp aria-hidden="true" size={24} />
                    <span>{t("validation.emptyList")}</span>
                  </>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="s1k-validation-detail-panel" role="region" aria-labelledby="validation-detail-title" aria-live="polite">
          {selected ? (
            <>
              <div className="s1k-validation-detail-heading">
                <div className="s1k-validation-detail-title">
                  <Badge variant={statusVariant(selected.status)}>
                    {statusIcon(selected.status)} {t(`validation.status.${selected.status}`)}
                  </Badge>
                  <CardTitle id="validation-detail-title" className="break-words">
                    {selected.dmc || selected.displayName}
                  </CardTitle>
                  <span className="s1k-validation-filename text-label font-mono uppercase text-fg-dim">
                    {selected.displayName}
                  </span>
                </div>
                <Button type="button" variant="ghost" size="sm" className="s1k-validation-remove"
                  aria-label={t("validation.remove")} title={t("validation.remove")}
                  onClick={() => onRemove(selected.id)}>
                  <X aria-hidden="true" size={16} />
                </Button>
              </div>
              {selected.status === "checking" ? (
                <p className="s1k-validation-state-message">
                  <Loader2 aria-hidden="true" className="s1k-validation-spin" size={18} />
                  {t("validation.detail.checking")}
                </p>
              ) : null}
              {selected.status === "valid" ? (
                <p className="s1k-validation-state-message s1k-validation-is-valid">
                  <CheckCircle2 aria-hidden="true" size={19} />
                  <span>{t("validation.detail.valid")}</span>
                </p>
              ) : null}
              {selected.status === "needs_issue" ? (
                <p className="s1k-validation-state-message">
                  <AlertCircle aria-hidden="true" size={19} />
                  <span>{selected.message || t("validation.detail.chooseIssue")}</span>
                </p>
              ) : null}
              {selected.status === "unverifiable" ? (
                <p className="s1k-validation-state-message">
                  <AlertCircle aria-hidden="true" size={19} />
                  <span>{t("validation.detail.unverifiable")}</span>
                </p>
              ) : null}

              {selected.violations.length ? (
                <div className="s1k-validation-violations">
                  <h3 className="text-label font-mono uppercase text-fg-dim">
                    {t("validation.detail.violations", { count: selected.violations.length })}
                  </h3>
                  {selected.violations.map((violation, index) => (
                    <article className="s1k-validation-violation" key={`${violation.rule}-${index}`}>
                      <div className="s1k-validation-violation-meta">
                        <Badge variant={violation.severity === "error" ? "warning" : "info"}>
                          {violation.rule}
                        </Badge>
                        <span className="text-label font-mono uppercase text-fg-dim">
                          {locationLabel(violation, t)}
                        </span>
                      </div>
                      <p>{violation.message}</p>
                      {violation.path && violation.path !== "/" ? (
                        <code className="s1k-validation-error-path">{violation.path}</code>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <>
              <CardHeader>
                <CardTitle id="validation-detail-title">{t("validation.detail.panelTitle")}</CardTitle>
              </CardHeader>
              <CardContent className="flex-1">
                <div
                  className="s1k-validation-empty-detail"
                  data-testid="validation-empty-detail"
                >
                  <CheckCircle2 aria-hidden="true" size={24} />
                  <span>{t("validation.detail.selectDm")}</span>
                </div>
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
