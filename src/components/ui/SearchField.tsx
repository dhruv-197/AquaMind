import React from 'react';
import { Search } from 'lucide-react';

export type SearchFieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  onSubmitSearch?: (value: string) => void;
};

export const SearchField: React.FC<SearchFieldProps> = ({
  className = '',
  onSubmitSearch,
  ...rest
}) => (
  <label
    className={`am-search group relative flex h-9 w-full max-w-xs items-center gap-2 rounded-xl bg-[var(--am-bg-muted)] px-3 transition-colors duration-200 focus-within:bg-[var(--am-bg-elevated)] focus-within:ring-2 focus-within:ring-[var(--am-accent)] ${className}`}
  >
    <Search className="h-4 w-4 shrink-0 text-[var(--am-text-tertiary)]" strokeWidth={2} />
    <input
      type="search"
      className="w-full bg-transparent text-[16px] text-[var(--am-text)] placeholder:text-[var(--am-text-tertiary)] outline-none border-0 p-0 shadow-none"
      onKeyDown={(e) => {
        if (e.key === 'Enter' && onSubmitSearch) {
          onSubmitSearch((e.target as HTMLInputElement).value);
        }
      }}
      {...rest}
    />
  </label>
);

export default SearchField;
