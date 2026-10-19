import { Card, CardContent, CardHeader, CardTitle } from "@internal/ui";
import { useTranslation } from "react-i18next";

import type { Operation } from "../lib/workspace-api";

export function WorkspaceOperations({ operations }: { operations: Operation[] }) {
  const { t, i18n } = useTranslation();
  if (operations.length === 0) return null;
  return (
    <Card>
      <CardHeader><CardTitle>{t("history.operations")}</CardTitle></CardHeader>
      <CardContent>
        <ol className="max-h-60 space-y-2 overflow-auto">
          {operations.map((operation, index) => (
            <li key={`${operation.at}-${index}`} className="flex flex-wrap justify-between gap-2 text-sm">
              <span>{index + 1}. {t(`history.actions.${operation.kind}`)}</span>
              <time dateTime={operation.at} className="text-xs text-fg-dim">
                {new Date(operation.at).toLocaleString(i18n.resolvedLanguage)}
              </time>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
