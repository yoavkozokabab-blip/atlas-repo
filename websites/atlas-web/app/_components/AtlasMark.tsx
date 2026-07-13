/** Atlas mark — a small faceted node-lattice (nodes bound to a core) echoing
 *  the constellation. Inherits currentColor; accent core. */
export default function AtlasMark({
  size = 26,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
    >
      <g stroke="#2C6F66" strokeWidth="1.1">
        <line x1="16" y1="16" x2="6" y2="7" />
        <line x1="16" y1="16" x2="26" y2="8" />
        <line x1="16" y1="16" x2="7" y2="25" />
        <line x1="16" y1="16" x2="25" y2="24" />
        <line x1="6" y1="7" x2="26" y2="8" />
        <line x1="7" y1="25" x2="25" y2="24" />
      </g>
      <g fill="#5FD3BE">
        <circle cx="6" cy="7" r="2" />
        <circle cx="26" cy="8" r="2" />
        <circle cx="7" cy="25" r="2" />
        <circle cx="25" cy="24" r="2" />
      </g>
      <circle cx="16" cy="16" r="4.4" fill="#0c1613" stroke="#8CF0DC" strokeWidth="1.2" />
      <circle cx="16" cy="16" r="1.6" fill="#8CF0DC" />
    </svg>
  );
}
