import React from 'react';
import { motion } from 'framer-motion';

export type CardProps = {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
};

const padClass = {
  none: 'p-0',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
} as const;

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = 'md',
  hover = false,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
    whileHover={
      hover
        ? {
            y: -2,
            boxShadow: 'var(--am-shadow-hover)',
            transition: { duration: 0.2 },
          }
        : undefined
    }
    className={`am-card rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)] ${padClass[padding]} ${className}`}
  >
    {children}
  </motion.div>
);

export default Card;
