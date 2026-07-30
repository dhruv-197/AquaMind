import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Satellite, AlertCircle, Layers, Image as ImageIcon, Cpu } from 'lucide-react';
import { ImageUploader } from '../components/vision/ImageUploader';
import { VisionResultCard } from '../components/vision/VisionResultCard';
import { apiUpload } from '../services/apiClient';

/** Procedural sample reservoir scene for quick product demos. */
function buildSampleReservoirFile() {
  const canvas = document.createElement('canvas');
  canvas.width = 640;
  canvas.height = 420;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas unavailable');

  const sky = ctx.createLinearGradient(0, 0, 0, 180);
  sky.addColorStop(0, '#0ea5e9');
  sky.addColorStop(1, '#e0f2fe');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, 640, 180);

  ctx.fillStyle = '#166534';
  ctx.beginPath();
  ctx.moveTo(0, 160);
  ctx.quadraticCurveTo(160, 90, 320, 150);
  ctx.quadraticCurveTo(480, 210, 640, 130);
  ctx.lineTo(640, 280);
  ctx.lineTo(0, 280);
  ctx.fill();

  ctx.fillStyle = '#854d0e';
  ctx.fillRect(0, 250, 640, 50);

  const water = ctx.createLinearGradient(0, 270, 0, 420);
  water.addColorStop(0, '#0369a1');
  water.addColorStop(1, '#0c4a6e');
  ctx.fillStyle = water;
  ctx.beginPath();
  ctx.moveTo(40, 290);
  ctx.quadraticCurveTo(320, 250, 600, 300);
  ctx.lineTo(620, 420);
  ctx.lineTo(20, 420);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = 'rgba(125, 211, 252, 0.35)';
  ctx.beginPath();
  ctx.ellipse(300, 340, 140, 28, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#a3e635';
  for (let i = 0; i < 18; i += 1) {
    ctx.fillRect(30 + i * 34, 220 + (i % 3) * 8, 16, 22);
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('Could not build sample image'));
        return;
      }
      resolve(new File([blob], 'aquavision-sample-reservoir.png', { type: 'image/png' }));
    }, 'image/png');
  });
}

/**
 * Sample flood scene: dark permanent river (left) + brown muddy inundation over fields (right).
 * Helps demo permanent-water vs flood-inundation separation.
 */
function buildSampleFloodFile() {
  const canvas = document.createElement('canvas');
  canvas.width = 640;
  canvas.height = 420;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas unavailable');

  // Fields / dry land background
  ctx.fillStyle = '#4d7c0f';
  ctx.fillRect(0, 0, 640, 420);
  ctx.fillStyle = '#a16207';
  for (let y = 40; y < 420; y += 28) {
    ctx.fillRect(220, y, 420, 14);
  }

  // Permanent river channel (clearer blue)
  const river = ctx.createLinearGradient(0, 0, 180, 0);
  river.addColorStop(0, '#0c4a6e');
  river.addColorStop(0.5, '#0284c7');
  river.addColorStop(1, '#0c4a6e');
  ctx.fillStyle = river;
  ctx.beginPath();
  ctx.moveTo(0, 40);
  ctx.bezierCurveTo(80, 120, 60, 220, 40, 420);
  ctx.lineTo(160, 420);
  ctx.bezierCurveTo(180, 240, 200, 100, 120, 0);
  ctx.closePath();
  ctx.fill();

  // Muddy flood inundation over fields (not the river)
  ctx.fillStyle = 'rgba(120, 53, 15, 0.85)';
  ctx.beginPath();
  ctx.ellipse(420, 240, 170, 110, -0.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = 'rgba(69, 26, 3, 0.7)';
  ctx.beginPath();
  ctx.ellipse(480, 300, 90, 60, 0.3, 0, Math.PI * 2);
  ctx.fill();

  // Roads / structures hints
  ctx.fillStyle = '#78716c';
  ctx.fillRect(300, 80, 200, 8);
  ctx.fillRect(520, 60, 18, 80);

  ctx.fillStyle = '#f8fafc';
  ctx.font = '12px sans-serif';
  ctx.fillText('permanent river', 20, 30);
  ctx.fillText('flood over fields', 380, 200);

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('Could not build flood sample'));
        return;
      }
      resolve(new File([blob], 'aquavision-sample-flood.png', { type: 'image/png' }));
    }, 'image/png');
  });
}

export const VisionAnalysis = () => {
  const [visionMode, setVisionMode] = useState('reservoir'); // reservoir | flood
  const [assetLabel, setAssetLabel] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [stage, setStage] = useState('idle');

  const handleImageSelect = (file) => {
    setSelectedFile(file);
    setResult(null);
    setError('');
    setStage('ready');
    const reader = new FileReader();
    reader.onloadend = () => setImagePreview(reader.result);
    reader.readAsDataURL(file);
  };

  const handleClearImage = () => {
    setSelectedFile(null);
    setImagePreview(null);
    setResult(null);
    setError('');
    setStage('idle');
  };

  const handleLoadSample = async () => {
    try {
      const file =
        visionMode === 'flood' ? await buildSampleFloodFile() : await buildSampleReservoirFile();
      handleImageSelect(file);
    } catch (err) {
      setError(err.message || 'Could not create sample scene.');
    }
  };

  const handleModeChange = (mode) => {
    setVisionMode(mode);
    setResult(null);
    setError('');
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;
    setIsLoading(true);
    setError('');
    setResult(null);
    setStage('uploading');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('mode', visionMode);
      if (assetLabel.trim()) formData.append('asset_label', assetLabel.trim());
      setStage('inferring');

      const resData = await apiUpload('/api/vision/analyze', formData);
      if (resData?.success) {
        setResult(resData);
        setStage('done');
      } else {
        throw new Error(resData?.detail || resData?.message || 'Vision AI analysis returned no data.');
      }
    } catch (err) {
      console.error('Vision analysis error:', err);
      setStage('error');
      setError(
        err.message ||
          'Could not analyze this image. Please try again in a moment.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const isFlood = visionMode === 'flood';

  return (
    <div className="space-y-6 pb-12">
      <section className="am-soft-card p-5 sm:p-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="rounded-[14px] bg-[var(--am-accent-soft)] p-2.5 text-[var(--am-accent)]">
                <Satellite className="h-5 w-5" strokeWidth={2.25} />
              </div>
              <div>
                <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">AquaLens</h1>
                <p className="text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)]">
                  {isFlood ? 'Flood inundation vs permanent water' : 'Visual water intelligence'}
                </p>
              </div>
            </div>
            <p className="max-w-2xl text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
              {isFlood
                ? 'Upload flood imagery to separate permanent water bodies from flood water over land.'
                : 'Upload satellite or drone imagery to measure reservoir conditions and highlight water, vegetation, shoreline, sediment, and structures.'}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-start gap-2 md:items-end">
            <div className="inline-flex items-center gap-2 rounded-[12px] border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3.5 py-1.5 text-[15px] text-[var(--am-text)]">
              <Cpu className="h-4 w-4 text-[var(--am-accent)]" />
              Mode: <strong>{isFlood ? 'Flood mapping' : 'Reservoir insight'}</strong>
            </div>
            <button
              type="button"
              onClick={handleLoadSample}
              className="inline-flex items-center gap-2 rounded-[12px] border border-[var(--am-border-strong)] bg-[var(--am-bg-elevated)] px-3 py-1.5 text-[15px] font-semibold text-[var(--am-accent)] transition hover:bg-[var(--am-bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
            >
              <ImageIcon className="h-3.5 w-3.5" />
              {isFlood ? 'Load sample flood scene' : 'Load sample reservoir scene'}
            </button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Vision mode">
          <button
            type="button"
            role="tab"
            aria-selected={!isFlood}
            onClick={() => handleModeChange('reservoir')}
            className={`rounded-[12px] px-3 py-2 text-[15px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
              !isFlood
                ? 'bg-[var(--am-accent-soft)] text-[var(--am-accent)]'
                : 'bg-[var(--am-bg-muted)] text-[var(--am-text-tertiary)]'
            }`}
          >
            Reservoir health
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isFlood}
            onClick={() => handleModeChange('flood')}
            className={`rounded-[12px] px-3 py-2 text-[15px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
              isFlood
                ? 'bg-[var(--am-danger-soft)] text-[var(--am-danger)]'
                : 'bg-[var(--am-bg-muted)] text-[var(--am-text-tertiary)]'
            }`}
          >
            Flood inundation map
          </button>
        </div>

        <div className="mt-4">
          <label htmlFor="aqualens-asset-label" className="mb-1.5 block text-[14px] font-semibold uppercase tracking-[0.05em] text-[var(--am-text-tertiary)]">
            Site / reservoir name (optional)
          </label>
          <input
            id="aqualens-asset-label"
            type="text"
            value={assetLabel}
            onChange={(e) => setAssetLabel(e.target.value)}
            placeholder="e.g. Sardar Sarovar Reservoir"
            maxLength={255}
            className="w-full max-w-md rounded-[12px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-3.5 py-2 text-[16px] text-[var(--am-text)] focus:border-[var(--am-accent)] focus:outline-none"
          />
          <p className="mt-1 text-[14px] text-[var(--am-text-tertiary)]">
            Tag scans with the same name to track health trends and before/after changes for that site over time.
          </p>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            { id: 'ready', label: '1. Image ready' },
            { id: 'uploading', label: '2. Upload' },
            { id: 'inferring', label: '3. Infer' },
            { id: 'done', label: '4. Insights' },
          ].map((step) => {
            const active =
              stage === step.id ||
              (step.id === 'ready' &&
                (stage === 'ready' || stage === 'uploading' || stage === 'inferring' || stage === 'done')) ||
              (step.id === 'uploading' && (stage === 'uploading' || stage === 'inferring' || stage === 'done')) ||
              (step.id === 'inferring' && (stage === 'inferring' || stage === 'done')) ||
              (step.id === 'done' && stage === 'done');
            return (
              <div
                key={step.id}
                className={`rounded-[14px] border px-3 py-2 text-[14px] font-medium ${
                  active
                    ? 'border-[var(--am-accent)]/30 bg-[var(--am-accent-soft)] text-[var(--am-accent)]'
                    : 'border-[var(--am-border)] bg-[var(--am-bg-muted)] text-[var(--am-text-tertiary)]'
                }`}
              >
                <Layers className="mb-1 h-3.5 w-3.5" />
                {step.label}
              </div>
            );
          })}
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-[16px] border border-[var(--am-danger)]/25 bg-[var(--am-danger-soft)] p-4 text-[16px] text-[var(--am-danger)]" role="alert">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">Analysis failed</p>
            <p className="mt-1 text-[15px] opacity-90">{error}</p>
          </div>
        </div>
      )}

      <ImageUploader
        onImageSelect={handleImageSelect}
        selectedFile={selectedFile}
        imagePreview={imagePreview}
        onClearImage={handleClearImage}
        onAnalyze={handleAnalyze}
        isLoading={isLoading}
        onLoadSample={handleLoadSample}
      />

      {result && <VisionResultCard result={result} originalPreview={imagePreview} />}

      <section className="rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/50 p-4 text-[15px] text-[var(--am-text-secondary)]">
        Continue with{' '}
        <Link className="font-semibold text-[var(--am-accent)] hover:underline" to="/climate-risk">
          Climate Risk Overview
        </Link>{' '}
        or{' '}
        <Link className="font-semibold text-[var(--am-accent)] hover:underline" to="/dashboard">
          Operations Dashboard
        </Link>{' '}
        after visual triage.
      </section>
    </div>
  );
};

export default VisionAnalysis;
