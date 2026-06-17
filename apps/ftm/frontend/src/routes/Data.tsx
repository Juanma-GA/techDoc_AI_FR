/**
 * Route /data — data administration: 8 KPIs from /admin/stats +
 * 3 reset buttons (analyses / chat / all) with double-click pattern (4 s).
 */
import { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  KpiCard,
  Spinner,
} from '@internal/ui';
import { resources, type AdminStatsOut } from '../lib/api';
import { PageHeader } from '../components/PageHeader';

type ResetScope = 'analyses' | 'chat' | 'all';

function formatBytes(n: number): string {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} Ko`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} Mo`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} Go`;
}

function buildKpis(s: AdminStatsOut, t: (k: string) => string) {
  return [
    { label: t('data.kpi.projects'), value: String(s.projects) },
    {
      label: t('data.kpi.files'),
      value: `${s.files} / ${s.file_versions} ${t('data.kpi.versions')}`,
    },
    { label: t('data.kpi.anomalies'), value: String(s.anomalies) },
    { label: t('data.kpi.runs'), value: String(s.analysis_runs) },
    { label: t('data.kpi.chunks'), value: String(s.document_chunks) },
    {
      label: t('data.kpi.chatSessions'),
      value: `${s.chat_sessions} / ${s.chat_messages} ${t('data.kpi.messages')}`,
    },
    { label: t('data.kpi.storage'), value: formatBytes(s.storage_bytes) },
    { label: t('data.kpi.db'), value: formatBytes(s.db_bytes) },
  ];
}

type ResetButtonProps = {
  scope: ResetScope;
  labelKey: string;
  confirmKey: string;
  variant: 'secondary' | 'danger';
  disabled: boolean;
  onReset: (scope: ResetScope) => Promise<void>;
};

function ResetButton({
  scope,
  labelKey,
  confirmKey,
  variant,
  disabled,
  onReset,
}: ResetButtonProps) {
  const { t } = useTranslation();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disarm = useCallback(() => {
    setArmed(false);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const handleClick = useCallback(async () => {
    if (!armed) {
      setArmed(true);
      timerRef.current = setTimeout(disarm, 4000);
      return;
    }
    disarm();
    setBusy(true);
    try {
      await onReset(scope);
    } finally {
      setBusy(false);
    }
  }, [armed, disarm, onReset, scope]);

  return (
    <Button
      variant={variant}
      disabled={disabled || busy}
      onClick={() => void handleClick()}
    >
      {busy ? <Spinner size="sm" /> : armed ? t(confirmKey) : t(labelKey)}
    </Button>
  );
}

export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const {
    data: stats,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => resources.admin.stats(),
  });

  const handleReset = useCallback(
    async (scope: ResetScope) => {
      setResetting(true);
      setFeedback(null);
      try {
        const out = await resources.admin.reset({ scope });
        const detail = Object.entries(out.deleted)
          .map(([k, v]) => `${k}:${v}`)
          .join(', ');
        setFeedback(`✓ ${scope} — ${detail}`);
        await qc.invalidateQueries({ queryKey: ['admin-stats'] });
      } catch (err) {
        setFeedback(`✗ ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setResetting(false);
      }
    },
    [qc],
  );

  const kpis = stats ? buildKpis(stats, t) : [];

  return (
    <div className="space-y-6 p-6">
      <PageHeader title={t('nav.data')} subtitle={t('page.data')} />

      {/* Card 1 — KPIs vue d'ensemble */}
      <Card>
        <CardHeader>
          <CardTitle>{t('data.overview')}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Spinner />}
          {isError && (
            <p className="text-sm text-status-err">{t('errors.network')}</p>
          )}
          {stats && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {kpis.map((kpi) => (
                <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Card 2 — reset par scope */}
      <Card>
        <CardHeader>
          <CardTitle>{t('data.resetTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            className="rounded border border-status-warn/40 bg-status-warn/10 px-4 py-3 text-sm text-fg [&_strong]:font-semibold"
            dangerouslySetInnerHTML={{ __html: t('data.resetHint') }}
          />
          <div className="flex flex-wrap items-center gap-3">
            <ResetButton
              scope="analyses"
              labelKey="data.resetAnalyses"
              confirmKey="data.confirmAnalyses"
              variant="secondary"
              disabled={resetting}
              onReset={handleReset}
            />
            <ResetButton
              scope="chat"
              labelKey="data.resetChat"
              confirmKey="data.confirmChat"
              variant="secondary"
              disabled={resetting}
              onReset={handleReset}
            />
            <ResetButton
              scope="all"
              labelKey="data.resetAll"
              confirmKey="data.confirmAll"
              variant="danger"
              disabled={resetting}
              onReset={handleReset}
            />
            {feedback && (
              <span className="ml-auto font-mono text-xs text-fg-dim">
                {feedback}
              </span>
            )}
          </div>
          <p className="font-mono text-xs text-fg-dim">
            <span className="font-semibold">{t('data.scopeAnalyses')}</span>
            {' = anomalies + runs + chunks'}
            <br />
            <span className="font-semibold">{t('data.scopeChat')}</span>
            {' = sessions + messages'}
            <br />
            <span className="font-semibold">{t('data.scopeAll')}</span>
            {' = projets, fichiers, anomalies, sessions, disque'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
