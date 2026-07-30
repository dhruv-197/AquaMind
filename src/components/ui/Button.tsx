import React from 'react';
import { Loader2 } from 'lucide-react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'tertiary';
type Size = 'sm' | 'md' | 'lg';

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: React.ReactNode;
  loading?: boolean;
};

const sizeClass: Record<Size, string> = {
  sm: 'h-9 px-3.5 text-[15px] gap-1.5 rounded-[10px]',
  md: 'h-10 px-4 text-[16px] gap-2 rounded-xl',
  lg: 'h-12 px-5 text-[17px] gap-2 rounded-[14px]',
};

const variantClass: Record<Variant, string> = {
  primary:
    'bg-[var(--am-accent)] text-white shadow-[var(--am-shadow-sm)] hover:bg-[var(--am-accent-hover)] active:scale-[0.98]',
  secondary:
    'bg-[var(--am-bg-elevated)] text-[var(--am-text)] border border-[var(--am-border-strong)] shadow-[var(--am-shadow-sm)] hover:bg-[var(--am-bg-hover)]',
  tertiary:
    'bg-[var(--am-bg-muted)] text-[var(--am-text)] hover:bg-[var(--am-bg-hover)]',
  ghost: 'bg-transparent text-[var(--am-text-secondary)] hover:bg-[var(--am-bg-hover)] hover:text-[var(--am-text)]',
  danger: 'bg-[var(--am-danger)] text-white shadow-[var(--am-shadow-sm)] hover:opacity-90 active:scale-[0.98]',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  icon,
  loading,
  className = '',
  children,
  type = 'button',
  disabled,
  ...rest
}) => (
  <button
    type={type}
    disabled={disabled || loading}
    aria-busy={loading || undefined}
    className={`am-btn inline-flex items-center justify-center font-semibold tracking-tight transition-all duration-200 ease-[cubic-bezier(0.25,0.1,0.25,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--am-bg)] disabled:opacity-45 disabled:pointer-events-none ${sizeClass[size]} ${variantClass[variant]} ${className}`}
    {...rest}
  >
    {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
    {children}
  </button>
);

export default Button;
