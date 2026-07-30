import React from 'react';
import { motion } from 'framer-motion';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  hoverEffect?: boolean;
}

/** Premium surface card (legacy name kept for compatibility). */
export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  glow = false,
  hoverEffect = true,
}) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
    whileHover={
      hoverEffect
        ? {
            y: -2,
            boxShadow: 'var(--am-shadow-hover)',
            transition: { duration: 0.2 },
          }
        : undefined
    }
    className={`glass-card-theme relative rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-6 shadow-[var(--am-shadow-md)] transition-shadow duration-200 ${
      glow ? 'ring-1 ring-[var(--am-accent)]/20' : ''
    } ${className}`}
  >
    {children}
  </motion.div>
);

export default GlassCard;
