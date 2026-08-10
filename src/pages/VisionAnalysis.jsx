import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Satellite, AlertCircle, Layers, Cpu } from 'lucide-react';
import { ImageUploader } from '../components/vision/ImageUploader';
import { VisionResultCard } from '../components/vision/VisionResultCard';
import { VisionHistoryTimeline } from '../components/vision/VisionHistoryTimeline';
import { isTimeoutError } from '../services/apiClient';
import { analyzeVisionImage, fetchVisionHistory } from '../services/visionAnalysis';

/**
 * Upload deadline. Comfortably above the backend's own vision budget (provider
 * chain 75s + optional CLIPSeg overlay 60s) so it only fires when the request
 * is genuinely stuck rather than merely slow.
 */
const VISION_TIMEOUT_MS = 150_000;

export const VisionAnalysis = () => {
  const [visionMode, setVisionMode] = useState('reservoir'); // reservoir | flood
  const [selectedFile, setSelectedFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [errorTitle, setErrorTitle] = useState('Analysis failed');
  const [stage, setStage] = useState('idle');
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');

  const refreshHistory = async (mode) => {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const res = await fetchVisionHistory({
        vision_mode: mode,
        limit: 12,
        force_refresh: true,
      });
      setHistory(res.history || []);
    } catch (err) {
      setHistory([]);
      setHistoryError(err?.message || 'Could not load scan history.');
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    void refreshHistory(visionMode);
  }, [visionMode]);

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
      setStage('inferring');

      const resData = await analyzeVisionImage(formData, {
        timeoutMs: VISION_TIMEOUT_MS,
      });
      if (resData?.success) {
        setResult(resData);
        setStage('done');
        void refreshHistory(visionMode);
      } else {
        throw new Error(resData?.detail || resData?.message || 'Vision AI analysis returned no data.');
      }
    } catch (err) {
      console.error('Vision analysis error:', err);
      setStage('error');
      setErrorTitle(err?.status === 503 ? 'Vision service unavailable' : 'Analysis failed');
      setError(
        isTimeoutError(err)
          ? 'The analysis took too long to come back. Check the connection and try the upload again.'
          : err.message || 'Could not analyze this image. Please try again in a moment.',
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
          <div className="inline-flex items-center gap-2 rounded-[12px] border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3.5 py-1.5 text-[15px] text-[var(--am-text)]">
            <Cpu className="h-4 w-4 text-[var(--am-accent)]" />
            Mode: <strong>{isFlood ? 'Flood mapping' : 'Reservoir insight'}</strong>
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
        <div
          className="flex items-start gap-3 rounded-[16px] border border-[var(--am-danger)]/25 bg-[var(--am-danger-soft)] p-4 text-[16px] text-[var(--am-danger)]"
          role="alert"
        >
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">{errorTitle}</p>
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
      />

      {result && <VisionResultCard result={result} originalPreview={imagePreview} />}

      <VisionHistoryTimeline
        assetLabel={null}
        visionMode={visionMode}
        history={history}
        loading={historyLoading}
        error={historyError}
        showAllScans
      />

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
