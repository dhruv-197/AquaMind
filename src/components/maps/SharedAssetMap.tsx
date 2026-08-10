/**
 * SharedAssetMap. National clustered asset layer with per-module basemap variants.
 */
import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { useTheme } from '../../context/ThemeContext';
import { riskMarkerColor, type WaterAsset } from '../../services/geospatial';
import { SkeletonMap } from '../ui/Skeleton';

export type MapVariant =
  | 'dashboard'
  | 'stress'
  | 'reservoir'
  | 'demand'
  | 'leak'
  | 'climate'
  | 'satellite';

type Props = {
  assets: WaterAsset[];
  selectedId?: string | null;
  onSelect?: (asset: WaterAsset) => void;
  height?: number | string;
  className?: string;
  showLegend?: boolean;
  title?: string;
  subtitle?: string;
  lazy?: boolean;
  /** Visual differentiation per module */
  variant?: MapVariant;
};

const TILES: Record<
  MapVariant,
  { light: string; dark: string; attribution: string }
> = {
  dashboard: {
    light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO',
  },
  stress: {
    light: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO',
  },
  reservoir: {
    light: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO',
  },
  demand: {
    light: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO',
  },
  leak: {
    light: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; OpenStreetMap',
  },
  climate: {
    light: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO',
  },
  satellite: {
    light: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    dark: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri',
  },
};

/** Escape untrusted text before it's interpolated into Leaflet's innerHTML-based popup. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function titleCase(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function metadataText(asset: WaterAsset, key: string): string | null {
  const value = asset.meta?.[key];
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function popupRows(asset: WaterAsset): Array<[string, string]> {
  const confidence =
    asset.confidence != null ? `${Math.round(asset.confidence * 100)}%` : null;
  const rows: Array<[string, string | null]> = [
    ['Status', titleCase(asset.risk_level || 'Not assessed')],
  ];

  switch (asset.type) {
    case 'reservoir':
      rows.push(
        [
          'Current storage',
          asset.current_storage_pct != null
            ? `${asset.current_storage_pct.toFixed(1)}%`
            : null,
        ],
        [
          'Predicted storage',
          asset.forecast_storage_pct != null
            ? `${asset.forecast_storage_pct.toFixed(1)}%`
            : null,
        ],
        [
          'Capacity',
          asset.capacity_mcm != null
            ? `${asset.capacity_mcm.toLocaleString()} MCM`
            : null,
        ],
      );
      break;
    case 'groundwater_station': {
      const depth = metadataText(asset, 'depth_to_water_m');
      rows.push(['Depth to water', depth ? `${depth} m` : null]);
      break;
    }
    case 'dam':
      rows.push(['Linked reservoir', metadataText(asset, 'parent_reservoir_id')]);
      break;
    case 'demand_region':
      rows.push([
        'Region type',
        metadataText(asset, 'region_kind')
          ? titleCase(metadataText(asset, 'region_kind')!)
          : null,
      ]);
      break;
    case 'water_stress_region':
      rows.push(['Monitoring layer', 'Water stress']);
      break;
    case 'leak_zone':
      rows.push([
        'Monitoring',
        metadataText(asset, 'monitoring')
          ? titleCase(metadataText(asset, 'monitoring')!)
          : null,
      ]);
      break;
  }

  rows.push(['Confidence', confidence]);

  if (asset.last_updated) {
    const updated = new Date(asset.last_updated);
    rows.push([
      'Updated',
      Number.isNaN(updated.getTime())
        ? asset.last_updated
        : updated.toLocaleDateString(undefined, {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
          }),
    ]);
  }

  return rows.filter((row): row is [string, string] => row[1] != null);
}

function buildPopupHtml(asset: WaterAsset): string {
  const name = escapeHtml(asset.name || '');
  const state = escapeHtml(asset.state || '');
  const type = escapeHtml(titleCase(asset.type));
  const details = popupRows(asset)
    .map(
      ([label, value]) =>
        `<div style="display:flex;justify-content:space-between;gap:16px">
          <span style="color:#8E8E93">${escapeHtml(label)}</span>
          <b style="text-align:right">${escapeHtml(value)}</b>
        </div>`,
    )
    .join('');

  return `<div style="font:12px/1.45 -apple-system,BlinkMacSystemFont,'SF Pro Text',Segoe UI,sans-serif;min-width:210px;color:inherit">
    <strong style="font-size:13px">${name}</strong>
    <div style="margin-top:4px;color:#6E6E73">${state} · ${type}</div>
    <div style="margin-top:8px;display:grid;gap:5px">${details}</div>
  </div>`;
}

function ClusterLayer({
  assets,
  selectedId,
  onSelect,
  variant,
}: {
  assets: WaterAsset[];
  selectedId?: string | null;
  onSelect?: (asset: WaterAsset) => void;
  variant: MapVariant;
}) {
  const map = useMap();
  const onSelectRef = useRef(onSelect);
  const assetsRef = useRef(assets);
  const markersByIdRef = useRef<Map<string, L.CircleMarker>>(new Map());
  const fittedKeyRef = useRef<string>('');

  onSelectRef.current = onSelect;
  assetsRef.current = assets;

  const fittedKey = useMemo(
    () =>
      assets
        .map((a) => a.id)
        .sort()
        .join('|'),
    [assets],
  );

  // Build / rebuild markers only when the asset *set* or basemap variant changes.
  // never when selectedId or onSelect identity changes (that was zooming maps out).
  useEffect(() => {
    const currentAssets = assetsRef.current;
    const ClusterGroup = (L as any).MarkerClusterGroup as
      | (new (opts?: object) => L.LayerGroup & {
          addLayer: (l: L.Layer) => void;
          clearLayers?: () => void;
        })
      | undefined;

    const cluster = ClusterGroup
      ? new ClusterGroup({
          showCoverageOnHover: false,
          maxClusterRadius: variant === 'leak' ? 36 : 48,
          spiderfyOnMaxZoom: true,
          disableClusteringAtZoom: variant === 'reservoir' ? 10 : 11,
          chunkedLoading: true,
        })
      : L.layerGroup();

    const byId = new Map<string, L.CircleMarker>();

    for (const asset of currentAssets) {
      if (!Number.isFinite(asset.lat) || !Number.isFinite(asset.lng)) continue;
      const color = riskMarkerColor(asset.risk_level, false);
      const marker = L.circleMarker([asset.lat, asset.lng], {
        radius: variant === 'demand' ? 9 : 7,
        color,
        fillColor: color,
        fillOpacity: variant === 'stress' ? 0.88 : 0.78,
        weight: 1.5,
      });
      marker.bindPopup(buildPopupHtml(asset), {
        maxWidth: 280,
        autoPan: true,
        autoPanPaddingTopLeft: L.point(24, 24),
        autoPanPaddingBottomRight: L.point(24, 24),
        keepInView: true,
        closeOnClick: false,
        autoClose: false,
      });
      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e as unknown as Event);
        marker.openPopup();
        onSelectRef.current?.(asset);
      });
      cluster.addLayer(marker);
      byId.set(asset.id, marker);
    }

    markersByIdRef.current = byId;
    map.addLayer(cluster as unknown as L.Layer);

    // Fit once when assets first appear. Never again on selection or data refresh
    // (refitting after predict was resetting zoom on Stress / Reservoir / Dashboard).
    const shouldFit =
      !fittedKeyRef.current && Boolean(fittedKey) && currentAssets.length > 0;
    if (shouldFit) {
      fittedKeyRef.current = fittedKey;
      try {
        const bounds = L.latLngBounds(
          currentAssets.map((a) => [a.lat, a.lng] as [number, number]),
        );
        if (bounds.isValid()) {
          map.fitBounds(bounds.pad(0.08), { maxZoom: 7, animate: false });
        }
      } catch {
        /* ignore */
      }
    } else if (fittedKey) {
      fittedKeyRef.current = fittedKey;
    }

    return () => {
      map.removeLayer(cluster as unknown as L.Layer);
      markersByIdRef.current = new Map();
    };
  }, [map, fittedKey, variant]);

  // Soft-highlight selection without tearing down the cluster / resetting zoom.
  // Do not call openPopup here. MarkerCluster zooms to the marker on programmatic
  // openPopup, which felt like the map "breaking" after click. Click handler opens it.
  useEffect(() => {
    const currentAssets = assetsRef.current;
    markersByIdRef.current.forEach((marker, id) => {
      const selected = id === selectedId;
      const asset = currentAssets.find((a) => a.id === id);
      const color = riskMarkerColor(asset?.risk_level, selected);
      marker.setStyle({
        radius: selected ? 11 : variant === 'demand' ? 9 : 7,
        color: selected ? '#007AFF' : color,
        fillColor: color,
        fillOpacity: selected ? 0.95 : variant === 'stress' ? 0.88 : 0.78,
        weight: selected ? 3 : 1.5,
      });
      if (selected) {
        try {
          marker.bringToFront();
        } catch {
          /* ignore */
        }
      }
    });
  }, [selectedId, fittedKey, variant]);

  return null;
}

export const SharedAssetMap: React.FC<Props> = ({
  assets,
  selectedId,
  onSelect,
  height = 420,
  className = '',
  showLegend = true,
  title,
  subtitle,
  lazy = true,
  variant = 'dashboard' as MapVariant,
}) => {
  const { isLight } = useTheme();
  const [ready, setReady] = React.useState(!lazy);
  const tiles = TILES[variant];

  useEffect(() => {
    if (!lazy) return;
    const t = window.setTimeout(() => setReady(true), 30);
    return () => window.clearTimeout(t);
  }, [lazy]);

  return (
    <div
      className={`overflow-hidden rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)] ${className}`}
    >
      {(title || showLegend) && (
        <div className="flex flex-col gap-2 border-b border-[var(--am-divider)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {title ? (
              <h3 className="text-[17px] font-semibold tracking-tight text-[var(--am-text)]">{title}</h3>
            ) : null}
            {subtitle ? (
              <p className="text-[15px] text-[var(--am-text-secondary)]">{subtitle}</p>
            ) : null}
            <p className="mt-0.5 text-[14px] text-[var(--am-text-tertiary)]">
              {assets.length.toLocaleString()} assets · {variant} basemap · clustered
            </p>
          </div>
          {showLegend ? (
            <div className="flex flex-wrap gap-2 text-[14px] text-[var(--am-text-secondary)]" role="list">
              {[
                ['Healthy', '#34C759'],
                ['Moderate', '#FFCC00'],
                ['High Risk', '#FF9500'],
                ['Critical', '#FF3B30'],
                ['Selected', '#007AFF'],
              ].map(([label, color]) => (
                <span key={label} className="inline-flex items-center gap-1.5" role="listitem">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden />
                  {label}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      )}

      <div className="am-map-frame" style={{ height }}>
        {!ready ? (
          <SkeletonMap height={typeof height === 'number' ? height : 380} />
        ) : assets.length === 0 ? (
          <div className="flex h-full items-center justify-center bg-[var(--am-bg-muted)] text-[16px] text-[var(--am-text-secondary)]">
            No geospatial assets for this filter.
          </div>
        ) : (
          <MapContainer
            center={[22.5, 78.5]}
            zoom={5}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom
            preferCanvas
            aria-label={title || 'Water assets map'}
          >
            <TileLayer attribution={tiles.attribution} url={isLight ? tiles.light : tiles.dark} />
            <ClusterLayer
              assets={assets}
              selectedId={selectedId}
              onSelect={onSelect}
              variant={variant}
            />
          </MapContainer>
        )}
      </div>
    </div>
  );
};

export default SharedAssetMap;
