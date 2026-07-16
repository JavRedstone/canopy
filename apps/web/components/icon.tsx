export function Icon({ name, className }: { name: string; className?: string }) {
  return (
    <span className={`material-symbol${className ? ` ${className}` : ""}`} aria-hidden="true">
      {name}
    </span>
  );
}
