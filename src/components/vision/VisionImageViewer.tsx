import React, { useCallback, useRef, useState } from 'react';
import { Maximize2, Minimize2, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';

type Props = {
  src?: string | null;
  alt: string;
  className?: string;
};

/** Zoom / pan / fullscreen image viewer for AquaLens workspace. */
export const VisionImageViewer: React.FC<Props> = ({ src, alt, className = '' }) => {
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const last = useRef({ x: 0, y: 0 });
  const frameRef = useRef<HTMLDivElement>(null);

  const reset = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (scale <= 1) return;
      setDragging(true);
      last.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    },
    [offset.x, offset.y, scale],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      setOffset({ x: e.clientX - last.current.x, y: e.clientY - last.current.y });
    },
    [dragging],
  );

  const onPointerUp = () => setDragging(false);

  const toggleFs = async () => {
    const el = frameRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      await el.requestFullscreen?.();
      setFullscreen(true);
    } else {
      await document.exitFullscreen?.();
      setFullscreen(false);
    }
  };

  if (!src) {
    return (
      <div
        className={`flex h-[360px] items-center justify-center rounded-[18px] border border-dashed border-[var(--am-border-strong)] bg-[var(--am-bg-muted)] text-[16px] text-[var(--am-text-secondary)] ${className}`}
      >
        No imagery for this layer
      </div>
    );
  }

  return (
    <div
      ref={frameRef}
      className={`relative overflow-hidden rounded-[18px] border border-[var(--am-border)] bg-[var(--am-bg-muted)] ${className}`}
    >
      <div className="absolute right-3 top-3 z-10 flex gap-1.5">
        <IconBtn label="Zoom in" onClick={() => setScale((s) => Math.min(4, s + 0.25))}>
          <ZoomIn className="h-3.5 w-3.5" />
        </IconBtn>
        <IconBtn label="Zoom out" onClick={() => setScale((s) => Math.max(1, s - 0.25))}>
          <ZoomOut className="h-3.5 w-3.5" />
        </IconBtn>
        <IconBtn label="Reset view" onClick={reset}>
          <RotateCcw className="h-3.5 w-3.5" />
        </IconBtn>
        <IconBtn label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'} onClick={toggleFs}>
          {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
        </IconBtn>
      </div>
      <div
        className="flex h-[420px] cursor-grab items-center justify-center active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        role="img"
        aria-label={alt}
      >
        <img
          src={src}
          alt={alt}
          draggable={false}
          className="max-h-full max-w-full select-none object-contain transition-transform duration-150"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          }}
        />
      </div>
      <p className="border-t border-[var(--am-divider)] px-3 py-2 text-[14px] text-[var(--am-text-tertiary)]">
        Zoom controls · drag to pan when zoomed · {Math.round(scale * 100)}%
      </p>
    </div>
  );
};

function IconBtn({
  children,
  onClick,
  label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="inline-flex h-8 w-8 items-center justify-center rounded-[10px] border border-[var(--am-border-strong)] bg-[var(--am-bg-elevated)] text-[var(--am-text)] shadow-[var(--am-shadow-sm)] transition hover:bg-[var(--am-bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
    >
      {children}
    </button>
  );
}

export default VisionImageViewer;
