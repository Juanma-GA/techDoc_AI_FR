import { Badge, Button, buttonVariants } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { BrexViolationsPanel } from "../../../components/BrexViolationsPanel";
import { wizardApi, type WizardDm } from "../../../lib/api";

export function GeneratedDmRow({ dm, docId, commonFields, hasBrex }: {
  dm: WizardDm; docId: string; commonFields: Set<string>; hasBrex: boolean;
}) {
  const { t } = useTranslation();
  const missing = (dm.missing_fields ?? []).filter((field) => !commonFields.has(field));
  return <div className="space-y-3 border-b border-md py-3 [content-visibility:auto]">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <span>{dm.is_orphan ? t("migration.dm.orphan") : dm.title}{" "}
        <Badge variant="info">{t(`dmType.${dm.dm_type}`)}</Badge>{" "}
        {dm.cir_unresolved?.length ? <Badge variant="warning" title={dm.cir_unresolved.join(", ")}>
          {t("migration.generate.cirUnresolved", { count: dm.cir_unresolved.length })}
        </Badge> : null}
      </span>
      {dm.has_xml ? <a href={wizardApi.dmXmlUrl(docId, dm.dm_id)}
        className={buttonVariants({ variant: "secondary", size: "sm" })}>{t("migration.generate.xml")}</a>
        : <Button type="button" variant="secondary" size="sm" disabled
          title={t("migration.generate.generationPending")}>{t("migration.generate.xml")}</Button>}
    </div>
    {dm.xsd_valid === false ? <p role="alert" className="text-danger">
      {t("migration.generate.xsdIncomplete")}
    </p> : missing.length ? <p role="status" className="text-warning">
      {t("migration.generate.missingDataWarning")}
    </p> : null}
    {dm.xsd_valid === false ? <details>
      <summary>{t("migration.ui.validationDetails")}</summary>
      {dm.xsd_violations?.length ? <ul className="space-y-2 py-2">
        {dm.xsd_violations.map((violation, index) => <li key={`${violation.rule}-${index}`}>
          <code>{violation.path}</code>: {violation.message}
        </li>)}
      </ul> : <p>{t("migration.generate.xsdNoDetails")}</p>}
    </details> : null}
    <details>
      <summary>{t("migration.ui.brexDetails")}</summary>
      <BrexViolationsPanel hasProfile={hasBrex} isComplete={dm.has_xml === true}
        violations={dm.brex_violations ?? []} />
    </details>
    {missing.length ? <details>
      <summary>{t("migration.generate.missingFields", { count: missing.length })}</summary>
      <ul className="space-y-1 py-2">{missing.map((field) => <li className="break-all" key={field}>{field}</li>)}</ul>
    </details> : null}
  </div>;
}
