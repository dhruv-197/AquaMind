import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, Image as ImageIcon, X, Eye, RefreshCw, ShieldAlert, Cpu } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

export const ImageUploader = ({
  onImageSelect,
  selectedFile,
  imagePreview,
  onClearImage,
  onAnalyze,
  isLoading,
  onLoadSample,
}) => {
  const { isLight } = useTheme();
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith('image/')) {
        onImageSelect(file);
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.type.startsWith('image/')) {
        onImageSelect(file);
      }
    }
  };

  return (
    <div className="w-full space-y-6">
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />

      {/* Main Drag & Drop / Preview Box */}
      <div className="relative">
        {!imagePreview ? (
          /* 1. Drag & Drop Area & 2. Upload Image */
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative group cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-8 sm:p-12 transition-all duration-300 text-center flex flex-col items-center justify-center min-h-[320px] ${
              isDragOver
                ? 'border-cyan-400 bg-cyan-950/30 shadow-[0_0_30px_rgba(6,182,212,0.2)] scale-[1.01]'
                : 'border-slate-800 bg-slate-900/40 hover:border-cyan-500/50 hover:bg-slate-900/80'
            }`}
          >
            {/* Background Glow Effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-transparent to-blue-600/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

            <div className="relative z-10 flex flex-col items-center space-y-4">
              <motion.div
                whileHover={{ scale: 1.1, rotate: 3 }}
                transition={{ type: 'spring', stiffness: 400 }}
                className="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500/20 via-blue-600/20 to-slate-900 border border-cyan-500/30 flex items-center justify-center shadow-lg shadow-cyan-500/10 group-hover:border-cyan-400"
              >
                <UploadCloud className="w-10 h-10 text-cyan-400 group-hover:scale-110 transition-transform duration-300" />
              </motion.div>

              <div className="space-y-1">
                <h3 className="text-lg font-bold text-white tracking-tight">
                  Upload Satellite or Drone Imagery
                </h3>
                <p className="text-[14px] text-slate-400 max-w-sm mx-auto">
                  Drag and drop high-resolution satellite or drone aerial captures here, or click to browse files
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  className="px-5 py-2.5 rounded-xl text-[14px] font-semibold text-slate-950 bg-gradient-to-r from-cyan-400 to-blue-400 hover:from-cyan-300 hover:to-blue-300 shadow-md shadow-cyan-500/20 transition-all duration-200 active:scale-95"
                >
                  Browse Image
                </button>
                {onLoadSample && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onLoadSample();
                    }}
                    className="px-5 py-2.5 rounded-xl text-[14px] font-semibold text-cyan-200 border border-cyan-500/40 bg-cyan-500/10 hover:bg-cyan-500/20"
                  >
                    Load sample reservoir scene
                  </button>
                )}
                <span className="text-[14px] font-mono text-slate-500">JPG, PNG, WEBP up to 20MB</span>
              </div>
            </div>
          </div>
        ) : (
          /* 3. Preview Image View & 5. Loading Animation Overlay */
          <div className="relative rounded-2xl border border-cyan-500/30 bg-slate-900/60 overflow-hidden shadow-2xl backdrop-blur-xl">
            {/* Top Toolbar */}
            <div className="px-5 py-3 border-b border-slate-800/80 bg-slate-950/80 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-cyan-400" />
                <span className="text-[14px] font-semibold text-slate-200 truncate max-w-[220px] sm:max-w-md">
                  {selectedFile ? selectedFile.name : 'Uploaded Reservoir Image'}
                </span>
                {selectedFile && (
                  <span className="px-2 py-0.5 text-[16px] font-mono rounded bg-slate-800 text-slate-400">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                  </span>
                )}
              </div>

              <button
                type="button"
                onClick={onClearImage}
                disabled={isLoading}
                className="p-1.5 rounded-lg bg-slate-800/80 text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors disabled:opacity-40"
                title="Remove image"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Image Preview Container */}
            <div className="relative aspect-video sm:aspect-[21/9] w-full bg-slate-950 flex items-center justify-center overflow-hidden">
              <img
                src={imagePreview}
                alt="Reservoir Satellite Preview"
                className="w-full h-full object-cover object-center"
              />

              {/* 5. Loading Scanning Animation Overlay.
                  pointer-events-none always applied (not just post-fade): AnimatePresence's
                  exit transition sometimes leaves this node mounted at opacity:0 instead of
                  unmounting it (a framer-motion timing quirk when a sibling. The result card
                  below. Mounts in the same render pass). Without this, the invisible leftover
                  layer sat at z-20 over the image with pointer-events:auto, silently eating
                  clicks on the image indefinitely after the first analysis. */}
              <AnimatePresence>
                {isLoading && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className={`aquavision-scan-overlay pointer-events-none absolute inset-0 dark-panel backdrop-blur-md flex flex-col items-center justify-center z-20 space-y-4 p-6 ${
                      isLight ? 'bg-slate-900/92' : 'bg-slate-950/90'
                    }`}
                    style={{ backgroundColor: 'rgba(15, 23, 42, 0.94)' }}
                  >
                    <div className="relative w-24 h-24 flex items-center justify-center">
                      <div className="absolute inset-0 rounded-full border-2 border-cyan-500/20 animate-ping opacity-75" />
                      <div className="absolute inset-0 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                      <div className="w-16 h-16 rounded-full bg-cyan-500/10 border border-cyan-400/40 flex items-center justify-center">
                        <Cpu className="w-8 h-8 text-cyan-300 animate-pulse" />
                      </div>
                    </div>

                    <div className="text-center space-y-1">
                      <p className="text-[15px] font-bold text-white">
                        AquaLens analyzing imagery...
                      </p>
                      <p className="text-[14px] text-cyan-200 animate-pulse">
                        Mapping water features in your image...
                      </p>
                    </div>

                    <div className="w-48 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
                        animate={{ x: ['-100%', '100%'] }}
                        transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Overlay Badge */}
              {!isLoading && (
                <div className="absolute bottom-3 left-3 bg-slate-950/80 backdrop-blur-md border border-cyan-500/30 px-3 py-1.5 rounded-lg flex items-center gap-2 text-[14px]">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-slate-200 font-medium">Satellite Capture Loaded</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 4. Analyze Button */}
      {imagePreview && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onAnalyze}
            disabled={isLoading}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl text-[15px] font-bold text-slate-950 bg-gradient-to-r from-cyan-400 via-sky-300 to-blue-400 hover:from-cyan-300 hover:to-white shadow-[0_0_25px_rgba(6,182,212,0.4)] transition-all duration-300 active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                <span>Running AquaLens Analysis...</span>
              </>
            ) : (
              <>
                <Eye className="w-4 h-4 text-slate-950" />
                <span>Analyze Satellite Imagery</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};

export default ImageUploader;
