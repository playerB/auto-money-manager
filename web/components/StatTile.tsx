export function StatTile({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="card">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
    </div>
  );
}
