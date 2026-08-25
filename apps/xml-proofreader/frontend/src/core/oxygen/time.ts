// Oxygen XML Author timestamp format: yyyyMMdd'T'HHmmssZ, e.g. 20260612T101500+0000

export function toOxygenTime(epochMillis: number): string {
  const d = new Date(epochMillis);
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    d.getUTCFullYear().toString() +
    p(d.getUTCMonth() + 1) +
    p(d.getUTCDate()) +
    "T" +
    p(d.getUTCHours()) +
    p(d.getUTCMinutes()) +
    p(d.getUTCSeconds()) +
    "+0000"
  );
}

export function fromOxygenTime(s: string): number {
  const m = s.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})([+-]\d{4})?/);
  if (!m) return Date.now();
  const [, y, mo, da, h, mi, se, tz] = m;
  let ms = Date.UTC(+y, +mo - 1, +da, +h, +mi, +se);
  if (tz && tz !== "+0000") {
    const sign = tz[0] === "-" ? -1 : 1;
    const offMin = sign * (parseInt(tz.slice(1, 3), 10) * 60 + parseInt(tz.slice(3, 5), 10));
    ms -= offMin * 60_000;
  }
  return ms;
}
