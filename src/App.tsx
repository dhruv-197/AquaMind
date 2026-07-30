/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import { PageLayout } from './components/layout/PageLayout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';

const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const LeakDetectionPage = lazy(() => import('./pages/LeakDetectionPage').then(m => ({ default: m.LeakDetectionPage })));
const WaterDemandForecastPage = lazy(() => import('./pages/WaterDemandForecastPage').then(m => ({ default: m.WaterDemandForecastPage })));
const ReservoirForecastPage = lazy(() => import('./pages/ReservoirForecastPage').then(m => ({ default: m.ReservoirForecastPage })));
const DecisionIntelligencePage = lazy(() => import('./pages/DecisionIntelligencePage').then(m => ({ default: m.DecisionIntelligencePage })));
const AlertsPage = lazy(() => import('./pages/AlertsPage').then(m => ({ default: m.AlertsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const ProfilePage = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })));
const VisionAnalysis = lazy(() => import('./pages/VisionAnalysis').then(m => ({ default: m.VisionAnalysis })));
const ClimateRiskPage = lazy(() => import('./pages/ClimateRiskPage').then(m => ({ default: m.ClimateRiskPage })));
const WaterStressPage = lazy(() => import('./pages/WaterStressPage').then(m => ({ default: m.WaterStressPage })));
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })));
const SignupPage = lazy(() => import('./pages/SignupPage').then(m => ({ default: m.SignupPage })));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then(m => ({ default: m.ForgotPasswordPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));
const AboutPage = lazy(() => import('./pages/AboutPage').then(m => ({ default: m.AboutPage })));
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center space-y-4">
          <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-[14px] text-slate-400">Preparing your water intelligence workspace…</p>
        </div>
      }>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          <Route path="/about" element={<ProtectedRoute><PageLayout><AboutPage /></PageLayout></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><PageLayout><DashboardPage /></PageLayout></ProtectedRoute>} />
          <Route path="/water-stress" element={<ProtectedRoute><PageLayout><WaterStressPage /></PageLayout></ProtectedRoute>} />
          <Route path="/leak-detection" element={<ProtectedRoute><PageLayout><LeakDetectionPage /></PageLayout></ProtectedRoute>} />
          <Route path="/demand" element={<ProtectedRoute><PageLayout><WaterDemandForecastPage /></PageLayout></ProtectedRoute>} />
          <Route path="/reservoir-forecast" element={<ProtectedRoute><PageLayout><ReservoirForecastPage /></PageLayout></ProtectedRoute>} />
          <Route path="/decision-intelligence" element={<ProtectedRoute><PageLayout><DecisionIntelligencePage /></PageLayout></ProtectedRoute>} />
          <Route path="/climate-risk" element={<ProtectedRoute><PageLayout><ClimateRiskPage /></PageLayout></ProtectedRoute>} />
          <Route path="/vision-analysis" element={<ProtectedRoute><PageLayout><VisionAnalysis /></PageLayout></ProtectedRoute>} />
          <Route path="/alerts" element={<ProtectedRoute><PageLayout><AlertsPage /></PageLayout></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><PageLayout><SettingsPage /></PageLayout></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><PageLayout><ProfilePage /></PageLayout></ProtectedRoute>} />

          {/* Removed legacy pages. Keep redirects for old bookmarks */}
          <Route path="/shortage" element={<Navigate to="/reservoir-forecast" replace />} />
          <Route path="/groundwater" element={<Navigate to="/water-stress" replace />} />
          <Route path="/reservoir" element={<Navigate to="/reservoir-forecast" replace />} />
          <Route path="/map" element={<Navigate to="/dashboard" replace />} />
          <Route path="/reports" element={<Navigate to="/dashboard" replace />} />
          <Route path="/ai-recommendations" element={<Navigate to="/decision-intelligence" replace />} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
