import { useCallback, useEffect, useState } from 'react';
import {
  fetchWaterAssets,
  type GeospatialQuery,
  type WaterAsset,
  type WaterAssetsResponse,
} from '../services/geospatial';

type Options = GeospatialQuery & {
  enabled?: boolean;
};

export function useWaterAssets(options: Options = {}) {
  const { enabled = true, types, state, risk_level, q, limit, offset } = options;
  const [assets, setAssets] = useState<WaterAsset[]>([]);
  const [meta, setMeta] = useState<Pick<WaterAssetsResponse, 'version' | 'updated_at' | 'counts' | 'total'> | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const typesKey = Array.isArray(types) ? types.join(',') : types || '';

  const reload = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetchWaterAssets({
        types,
        state,
        risk_level,
        q,
        limit,
        offset,
      });
      setAssets(res.assets || []);
      setMeta({
        version: res.version,
        updated_at: res.updated_at,
        counts: res.counts,
        total: res.total,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load geospatial assets');
      setAssets([]);
    } finally {
      setLoading(false);
    }
  }, [enabled, typesKey, state, risk_level, q, limit, offset]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { assets, meta, loading, error, reload };
}
