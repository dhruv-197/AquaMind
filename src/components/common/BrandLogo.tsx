import React from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';

export const BRAND_MOTTO = 'Monitoring Every Drop';

export const BRAND_LOGO_SRC = '/logo-mark.png';

type BrandLogoProps = {
  to?: string | null;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  stacked?: boolean;
  showIconBox?: boolean;
  forceDark?: boolean;
};

export const BrandLogo: React.FC<BrandLogoProps> = ({
  to = '/',
  className = '',
  size = 'md',
  stacked = false,
  showIconBox = true,
  forceDark = false,
}) => {
  const { isLight: themeLight } = useTheme();
  const isLight = forceDark ? false : themeLight;

  const imgSize = size === 'lg' ? 'h-11 w-11' : size === 'sm' ? 'h-8 w-8' : 'h-9 w-9';
  const titleSize = size === 'lg' ? 'text-[22px]' : size === 'sm' ? 'text-[14px]' : 'text-[15px]';
  const mottoSize = size === 'lg' ? 'text-[12px]' : 'text-[10px]';

  const mark = (
    <img
      src={BRAND_LOGO_SRC}
      alt=""
      width={size === 'lg' ? 44 : size === 'sm' ? 32 : 36}
      height={size === 'lg' ? 44 : size === 'sm' ? 32 : 36}
      className={`${imgSize} shrink-0 object-contain ${showIconBox ? 'rounded-xl' : ''}`}
      decoding="async"
    />
  );

  const content = (
    <>
      {showIconBox ? (
        <span className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-xl" aria-hidden>
          {mark}
        </span>
      ) : (
        mark
      )}
      <div className={stacked ? 'text-center' : 'min-w-0'}>
        <div
          className={`${titleSize} font-bold tracking-[-0.02em] leading-tight ${
            isLight ? 'text-[var(--am-text)]' : 'text-[#F5F5F7]'
          }`}
        >
          AquaMind AI
        </div>
        <p
          className={`${mottoSize} mt-0.5 font-medium tracking-wide ${
            isLight ? 'text-[var(--am-text-secondary)]' : 'text-[#98989D]'
          }`}
        >
          {BRAND_MOTTO}
        </p>
      </div>
    </>
  );

  const layout = stacked
    ? `inline-flex flex-col items-center gap-3 ${className}`
    : `inline-flex items-center gap-3 ${className}`;

  if (to) {
    return (
      <Link to={to} className={layout} aria-label="AquaMind AI home">
        {content}
      </Link>
    );
  }

  return <div className={layout}>{content}</div>;
};

export default BrandLogo;
