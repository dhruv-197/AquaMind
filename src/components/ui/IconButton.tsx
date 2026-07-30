import React from 'react';

export type IconButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  active?: boolean;
};

export const IconButton: React.FC<IconButtonProps> = ({
  label,
  active,
  className = '',
  children,
  type = 'button',
  ...rest
}) => (
  <button
    type={type}
    aria-label={label}
    title={label}
    className={`am-icon-btn relative inline-flex h-9 w-9 items-center justify-center rounded-xl text-[var(--am-text-secondary)] transition-all duration-200 hover:bg-[var(--am-bg-hover)] hover:text-[var(--am-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
      active ? 'bg-[var(--am-accent-soft)] text-[var(--am-accent)]' : ''
    } ${className}`}
    {...rest}
  >
    {children}
  </button>
);

export default IconButton;
