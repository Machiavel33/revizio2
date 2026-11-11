/** Logo Revizio (SVG inline, gradient cyan→violet). */

export default function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Revizio"
    >
      <defs>
        <linearGradient id="rvz-grad" x1="0" y1="0" x2="512" y2="512" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#00E5FF" />
          <stop offset="1" stopColor="#B14EFF" />
        </linearGradient>
        <linearGradient id="rvz-soft" x1="0" y1="0" x2="512" y2="512" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#00E5FF" stopOpacity="0.25" />
          <stop offset="1" stopColor="#B14EFF" stopOpacity="0.25" />
        </linearGradient>
      </defs>
      <rect width="512" height="512" rx="112" fill="#0A0B0F" />
      <rect width="512" height="512" rx="112" fill="url(#rvz-soft)" />
      <g fill="url(#rvz-grad)">
        <rect x="150" y="140" width="34" height="232" rx="17" />
        <path d="M184 140 H300 C352 140 384 172 384 216 C384 260 352 292 300 292 H184 V258 H300 C324 258 340 242 340 216 C340 190 324 174 300 174 H184 V140 Z" />
        <rect x="300" y="270" width="34" height="102" rx="17" transform="rotate(28 300 270)" />
      </g>
      <g fill="url(#rvz-grad)" opacity="0.85">
        <rect x="392" y="196" width="14" height="40" rx="7" />
        <rect x="416" y="176" width="14" height="80" rx="7" />
        <rect x="440" y="206" width="14" height="20" rx="7" />
      </g>
    </svg>
  );
}
