import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  CollapsibleSection,
  DemoModeSettingsCard,
  EmptyState,
  FormField,
  Input,
  KpiCard,
  LlmSettingsPanel,
  PageHeader,
  Select,
  Skeleton,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  Tooltip,
  type DemoMode,
  type LlmSettingsValue,
} from "@internal/ui";
import { FileText, Info } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

// Development-only reference page (registered in App.tsx when import.meta.env.DEV).
// Synthetic content only. Use it to review both themes, FR/EN and narrow viewports.

const SWATCHES = [
  ["bg-bg", "bg"],
  ["bg-bg-2", "bg-2"],
  ["bg-bg-3", "bg-3"],
  ["bg-card", "card"],
  ["bg-surface-sunken", "surface-sunken"],
  ["bg-brand", "brand"],
  ["bg-brand-soft", "brand-soft"],
  ["bg-success", "success"],
  ["bg-warning", "warning"],
  ["bg-danger", "danger"],
  ["bg-info", "info"],
  ["bg-accent-teal", "accent-teal"],
  ["bg-accent-purple", "accent-purple"],
  ["bg-accent-orange", "accent-orange"],
] as const;

const ROWS = [
  { name: "manual-a.pdf", status: "success", size: "1.2 MB" },
  { name: "manual-b.docx", status: "warning", size: "640 KB" },
  { name: "manual-c.xml", status: "danger", size: "88 KB" },
] as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function DesignGallery() {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(true);
  const [selected, setSelected] = useState(false);
  const [demoMode, setDemoMode] = useState<DemoMode>("normal");
  const [llmValue, setLlmValue] = useState<LlmSettingsValue>({
    llmEnabled: true,
    apiKeySet: true,
    baseUrl: "https://api.mistral.ai",
    models: { chat: "mistral-medium-latest", embed: "" },
  });

  return (
    <div className="flex flex-col gap-4" data-testid="design-gallery">
      <PageHeader
        eyebrow={t("design.eyebrow")}
        title={t("design.title")}
        description={t("design.subtitle")}
        actions={
          <>
            <Button variant="secondary">{t("design.secondary")}</Button>
            <Button>{t("design.primary")}</Button>
          </>
        }
      />

      <Section title={t("design.colors")}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {SWATCHES.map(([className, name]) => (
            <div key={name} className="flex flex-col gap-1.5">
              <div className={`h-10 rounded-sm border ${className}`} />
              <span className="font-mono text-xs text-fg-dim">{name}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-4">
          <span className="text-fg">text-fg</span>
          <span className="text-fg-dim">text-fg-dim</span>
          <span className="text-fg-muted">text-fg-muted</span>
          <span className="text-brand-text">text-brand-text</span>
          <span className="label">.label</span>
          <code>code</code>
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={t("design.buttons")}>
          <div className="flex flex-wrap items-center gap-2">
            <Button>{t("design.primary")}</Button>
            <Button variant="secondary">{t("design.secondary")}</Button>
            <Button variant="ghost">{t("design.ghost")}</Button>
            <Button variant="danger">{t("design.danger")}</Button>
            <Button disabled>{t("design.disabled")}</Button>
            <Button size="sm">{t("design.sample")}</Button>
            <Tooltip content={t("design.tooltip")}>
              <Button variant="secondary" size="icon" aria-label={t("design.tooltip")}>
                <Info size={16} aria-hidden="true" />
              </Button>
            </Tooltip>
          </div>
        </Section>

        <Section title={t("design.badges")}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{t("design.sample")}</Badge>
            <Badge variant="info">info</Badge>
            <Badge variant="success">success</Badge>
            <Badge variant="warning">warning</Badge>
            <Badge variant="danger">danger</Badge>
          </div>
        </Section>
      </div>

      <Section title={t("design.alerts")}>
        <div className="flex flex-col gap-2">
          <Alert variant="info">{t("design.alertInfo")}</Alert>
          <Alert variant="success">{t("design.alertSuccess")}</Alert>
          <Alert variant="warning">{t("design.alertWarning")}</Alert>
          <Alert variant="danger" title={t("design.danger")}>
            {t("design.alertDanger")}
          </Alert>
        </div>
      </Section>

      <Section title={t("design.form")}>
        <div className="grid gap-4 md:grid-cols-2">
          <FormField label={t("design.name")} hint={t("design.nameHint")} required>
            <Input defaultValue="AI4TECHDOC" />
          </FormField>
          <FormField label={t("design.model")}>
            <Select
              options={[
                { value: "medium", label: "mistral-medium-latest" },
                { value: "small", label: "mistral-small-latest" },
              ]}
            />
          </FormField>
          <FormField label={t("design.email")} error={t("design.emailError")}>
            <Input defaultValue="not-an-email" />
          </FormField>
          <FormField label={t("design.notes")}>
            <Textarea rows={2} />
          </FormField>
          <label className="flex items-center gap-2 text-sm text-fg">
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label={t("design.enabled")} />
            {t("design.enabled")}
          </label>
          <label className="flex items-center gap-2 text-sm text-fg">
            <Checkbox checked={selected} onCheckedChange={setSelected} aria-label={t("design.selected")} />
            {t("design.selected")}
          </label>
        </div>
      </Section>

      <Section title={t("design.tabs")}>
        <Tabs defaultValue="table">
          <TabsList aria-label={t("design.tabs")}>
            <TabsTrigger value="table">{t("design.tabTable")}</TabsTrigger>
            <TabsTrigger value="kpi">{t("design.tabKpi")}</TabsTrigger>
            <TabsTrigger value="loading">{t("design.tabLoading")}</TabsTrigger>
          </TabsList>
          <TabsContent value="table">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("design.columnName")}</TableHead>
                  <TableHead>{t("design.columnStatus")}</TableHead>
                  <TableHead className="text-right">{t("design.columnSize")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ROWS.map((row) => (
                  <TableRow key={row.name}>
                    <TableCell className="font-mono">{row.name}</TableCell>
                    <TableCell>
                      <Badge variant={row.status}>{row.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">{row.size}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TabsContent>
          <TabsContent value="kpi">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <KpiCard label={t("design.documents")} value={128} delta={{ direction: "up", label: "+12" }} />
              <KpiCard label={t("design.pages")} value="4 096" delta={{ direction: "stable" }} />
              <KpiCard label={t("design.errors")} value={3} delta={{ direction: "down", label: "-2" }} />
            </div>
          </TabsContent>
          <TabsContent value="loading">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-24 w-full rounded-lg" />
            </div>
          </TabsContent>
        </Tabs>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <EmptyState icon={FileText} title={t("design.empty")} description={t("design.emptyHint")} />
        <CollapsibleSection
          title={t("design.collapsible")}
          description={t("design.collapsibleHint")}
          defaultOpen={false}
          aside={<Badge variant="info">{t("design.sample")}</Badge>}
        >
          <FormField label={t("design.name")}>
            <Input />
          </FormField>
        </CollapsibleSection>
      </div>

      <Section title={t("design.settingsComponents")}>
        <div className="flex flex-col gap-4">
          <DemoModeSettingsCard
            mode={demoMode}
            onModeChange={setDemoMode}
            labels={{
              title: t("settings.demo.title"),
              hint: t("settings.demo.hint"),
              normal: t("settings.demo.normal"),
              demo: t("settings.demo.demo"),
              saveError: t("settings.demo.saveError"),
            }}
          />
          <LlmSettingsPanel
            value={llmValue}
            defaultOpen
            availableModels={["mistral-medium-latest", "mistral-small-latest", "mistral-embed"]}
            onSave={() => undefined}
            onTest={() => undefined}
            onToggleEnabled={(enabled) => setLlmValue((current) => ({ ...current, llmEnabled: enabled }))}
            labels={{
              title: t("design.llmTitle"),
              configured: t("design.llmConfigured"),
              notConfigured: t("design.llmNotConfigured"),
              disabled: t("design.llmDisabled"),
              enabled: t("design.llmEnabled"),
              enabledHint: t("design.llmEnabledHint"),
              apiKey: t("design.llmApiKey"),
              apiKeyKeep: t("design.llmApiKeyKeep"),
              baseUrl: t("design.llmBaseUrl"),
              models: { chat: t("design.llmChatModel"), embed: t("design.llmEmbedModel") },
              optionalModel: t("design.llmOptional"),
              modelsHint: t("design.llmModelsHint"),
              save: t("common.save"),
              test: t("design.llmTest"),
              loading: t("common.loading"),
            }}
          />
        </div>
      </Section>
    </div>
  );
}
