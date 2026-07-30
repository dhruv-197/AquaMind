import React from 'react';
import { SharedAssetMap, type MapVariant } from './SharedAssetMap';
import { useWaterAssets } from '../../hooks/useWaterAssets';
import type { WaterAssetType } from '../../services/geospatial';
import { SkeletonMap } from '../ui/Skeleton';

type Props = {
  types: WaterAssetType | WaterAssetType[];
  title: string;
  subtitle?: string;
  height?: number;
  onSelect?: (id: string) => void;
  selectedId?: string | null;
  variant?: MapVariant;
};

/** Thin wrapper: loads shared catalogue with a type filter and renders SharedAssetMap. */
export const FilteredAssetMap: React.FC<Props> = ({
  types,
  title,
  subtitle,
  height = 300,
  onSelect,
  selectedId,
  variant = 'dashboard',
}) => {
  const { assets, loading, error } = useWaterAssets({ types });

  if (error) {
    return (
      <div className="rounded-[20px] border border-[var(--am-danger)]/20 bg-[var(--am-danger-soft)] p-4 text-[16px] text-[var(--am-danger)]">
        {error}
      </div>
    );
  }

  if (loading && !assets.length) {
    return <SkeletonMap height={height} />;
  }

  return (
    <SharedAssetMap
      assets={assets}
      selectedId={selectedId}
      onSelect={(a) => onSelect?.(a.id)}
      height={height}
      title={title}
      subtitle={subtitle}
      variant={variant}
    />
  );
};
