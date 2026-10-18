/**
 * "Month X" of an orthodontic case, counted from its start date (1-based),
 * frozen at `finished_at` for closed cases. Controls are not a proxy:
 * transfer patients start mid-treatment and skipped months still count.
 */
export function orthoMonth(startDate: string, until: Date = new Date()): number {
  const [y = 0, m = 1, d = 1] = startDate.slice(0, 10).split('-').map(Number)
  let months = (until.getFullYear() - y) * 12 + (until.getMonth() + 1 - m)
  if (until.getDate() < d) months -= 1
  return Math.max(1, months + 1)
}
