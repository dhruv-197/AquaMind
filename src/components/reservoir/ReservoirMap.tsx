import React, { useCallback } from 'react';
import { SharedAssetMap } from '../maps/SharedAssetMap';
import type { WaterAsset } from '../../services/geospatial';
import { SkeletonMap } from '../ui/Skeleton';

type Props = {
  assets: WaterAsset[];
  selectedId?: string | null;
  onSelect: (assetId: string) => void;
  loading?: boolean;
};

export const ReservoirMap: React.FC<Props> = ({ assets, selectedId, onSelect, loading }) => {
  const handleSelect = useCallback(
    (asset: WaterAsset) => {
      onSelect(asset.id);
    },
    [onSelect],
  );

  if (loading && !assets.length) return <SkeletonMap height={440} />;

  return (
    <SharedAssetMap
      assets={assets}
      selectedId={selectedId}
      onSelect={handleSelect}
      height={440}
      title="National reservoir network"
      subtitle="Indian CWC-scale assets · hover for storage, forecast, risk, confidence, capacity"
      variant="reservoir"
    />
  );
};
