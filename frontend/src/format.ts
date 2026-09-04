/** ISO8601 → 올해면 MM.DD, 아니면 YYYY.MM.DD */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;

  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return d.getFullYear() === new Date().getFullYear()
    ? `${month}.${day}`
    : `${d.getFullYear()}.${month}.${day}`;
}
