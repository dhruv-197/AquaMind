import React from 'react';

export const Table: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <div className={`am-table-wrap overflow-auto rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)] ${className}`}>
    <table className="am-table w-full border-collapse text-left text-[16px]">{children}</table>
  </div>
);

export const THead: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <thead className="sticky top-0 z-10 bg-[var(--am-bg-elevated)]/95 backdrop-blur-sm">
    {children}
  </thead>
);

export const Th: React.FC<React.ThHTMLAttributes<HTMLTableCellElement>> = ({
  className = '',
  children,
  ...rest
}) => (
  <th
    className={`border-b border-[var(--am-divider)] px-4 py-3 text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)] ${className}`}
    {...rest}
  >
    {children}
  </th>
);

export const Td: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  className = '',
  children,
  ...rest
}) => (
  <td className={`border-b border-[var(--am-divider)] px-4 py-3 text-[var(--am-text)] tabular-nums ${className}`} {...rest}>
    {children}
  </td>
);

export const Tr: React.FC<React.HTMLAttributes<HTMLTableRowElement>> = ({
  className = '',
  children,
  ...rest
}) => (
  <tr className={`transition-colors duration-150 hover:bg-[var(--am-bg-muted)] ${className}`} {...rest}>
    {children}
  </tr>
);

export default Table;
