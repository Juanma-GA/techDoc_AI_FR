import type { AnomalyOut } from "./types";

export type KnowledgeEntry = {
  anomaly: AnomalyOut;
  project: string;
  filename: string;
  sourceId: string | null;
};

function normalized(value: string): string {
  return value.trim().replace(/\s+/g, " ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
}

export function knowledgeThemes(entries: KnowledgeEntry[], locale: string) {
  const grouped = new Map<string, KnowledgeEntry[]>();
  for (const entry of entries) {
    const key = normalized(entry.anomaly.category ?? "");
    const group = grouped.get(key) ?? [];
    group.push(entry);
    grouped.set(key, group);
  }

  return [...grouped.entries()].flatMap(([key, group]) => {
    const corrections = group.filter((entry) => entry.anomaly.status === "fixed");
    if (!corrections.length) return [];
    const lessons = new Map<string, { text: string; count: number }>();
    for (const { anomaly } of corrections) {
      const text = anomaly.suggestion.trim();
      if (!text) continue;
      const lessonKey = normalized(text);
      const lesson = lessons.get(lessonKey);
      if (lesson) lesson.count += 1;
      else lessons.set(lessonKey, { text, count: 1 });
    }
    const dates = corrections.flatMap(({ anomaly }) => anomaly.resolved_at ? [anomaly.resolved_at] : []).sort();
    return [{
      key,
      title: corrections[0]?.anomaly.category?.trim() ?? "",
      corrections,
      lessons: [...lessons.values()].sort((a, b) => b.count - a.count || a.text.localeCompare(b.text, locale)),
      sourceCount: new Set(corrections.flatMap((entry) =>
        entry.sourceId ? [`${entry.anomaly.project_id}:${entry.sourceId}`] : [],
      )).size,
      projectCount: new Set(corrections.map((entry) => entry.anomaly.project_id)).size,
      pendingCount: group.filter(({ anomaly }) => anomaly.status === "open" || anomaly.status === "acknowledged").length,
      latest: dates.at(-1),
    }];
  }).sort((a, b) => b.corrections.length - a.corrections.length || a.title.localeCompare(b.title, locale));
}

export function knowledgeCapitalization(entries: KnowledgeEntry[], locale: string) {
  const themes = knowledgeThemes(entries, locale);
  const corrections = themes.flatMap((theme) => theme.corrections);
  const dated = new Map<string, number>();
  for (const { anomaly } of corrections) {
    if (!anomaly.resolved_at) continue;
    const timestamp = Date.parse(anomaly.resolved_at);
    if (!Number.isFinite(timestamp)) continue;
    const day = new Date(timestamp).toISOString().slice(0, 10);
    dated.set(day, (dated.get(day) ?? 0) + 1);
  }
  let cumulative = 0;
  const timeline = [...dated.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([day, added]) => {
    cumulative += added;
    return { day, added, cumulative };
  });
  return {
    correctionCount: corrections.length,
    lessonCount: themes.reduce((count, theme) => count + theme.lessons.length, 0),
    themeCount: themes.length,
    sourceCount: new Set(corrections.flatMap((entry) =>
      entry.sourceId ? [`${entry.anomaly.project_id}:${entry.sourceId}`] : [],
    )).size,
    toFormalize: corrections.filter(({ anomaly }) => !anomaly.suggestion.trim()).length,
    undatedCount: corrections.length - cumulative,
    timeline,
  };
}
