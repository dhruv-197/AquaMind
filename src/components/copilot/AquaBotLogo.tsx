import React, { useId } from 'react';

type AquaBotLogoProps = {
  className?: string;
  /** Visual size of the mark in pixels */
  size?: number;
};

/** Custom AquaAI mark: luminous water drop with a soft wave + friendly bot eyes. */
export const AquaBotLogo: React.FC<AquaBotLogoProps> = ({ className = '', size = 32 }) => {
  const uid = useId().replace(/:/g, '');
  const dropId = `aquabotDrop-${uid}`;
  const sheenId = `aquabotSheen-${uid}`;
  const glowId = `aquabotGlow-${uid}`;

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center ${className}`}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="0 0 64 64" width={size} height={size} fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id={dropId} x1="12" y1="4" x2="52" y2="60" gradientUnits="userSpaceOnUse">
            <stop stopColor="#38bdf8" />
            <stop offset="0.45" stopColor="#14b8a6" />
            <stop offset="1" stopColor="#0ea5e9" />
          </linearGradient>
          <linearGradient id={sheenId} x1="22" y1="10" x2="30" y2="28" gradientUnits="userSpaceOnUse">
            <stop stopColor="#ffffff" stopOpacity="0.85" />
            <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
          <filter id={glowId} x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#0ea5e9" floodOpacity="0.35" />
          </filter>
        </defs>

        <circle cx="32" cy="34" r="28" fill="#e0f2fe" opacity="0.9" />

        <path
          d="M32 8C32 8 14 28 14 40.5C14 50.165 22.059 58 32 58C41.941 58 50 50.165 50 40.5C50 28 32 8 32 8Z"
          fill={`url(#${dropId})`}
          filter={`url(#${glowId})`}
        />

        <path
          d="M24 22C25.5 18.5 28.5 15.5 32 12.5C28.8 18 26.5 22.5 25.2 28.2C24.7 26 24.2 24 24 22Z"
          fill={`url(#${sheenId})`}
        />

        <path
          d="M20 42.5C23.5 39.5 27 39.5 30.5 42.5C34 45.5 37.5 45.5 41 42.5C43.2 40.6 45.2 40.2 47 40.5"
          stroke="#ecfeff"
          strokeWidth="2.4"
          strokeLinecap="round"
          opacity="0.95"
        />
        <path
          d="M21 47.5C24.2 45.2 27.2 45.2 30.5 47.5C33.8 49.8 36.8 49.8 40 47.5"
          stroke="#ccfbf1"
          strokeWidth="1.8"
          strokeLinecap="round"
          opacity="0.8"
        />

        <circle cx="26.5" cy="34" r="2.6" fill="#f0fdfa" />
        <circle cx="37.5" cy="34" r="2.6" fill="#f0fdfa" />
        <circle cx="27.1" cy="33.5" r="1.1" fill="#0f766e" />
        <circle cx="38.1" cy="33.5" r="1.1" fill="#0f766e" />
      </svg>
    </span>
  );
};
