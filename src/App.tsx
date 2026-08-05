import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import ChatPage from "@/pages/ChatPage";
import SearchPage from "@/pages/SearchPage";
import PaperDetailPage from "@/pages/PaperDetailPage";
import CitationPage from "@/pages/CitationPage";
import ResearchGapPage from "@/pages/ResearchGapPage";
import QuestionGeneratorPage from "@/pages/QuestionGeneratorPage";
import CollectionsPage from "@/pages/CollectionsPage";
import ProfilePage from "@/pages/ProfilePage";
import SettingsPage from "@/pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes (no sidebar) */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />

        {/* Authenticated routes (with sidebar + topbar layout) */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/paper/:id" element={<PaperDetailPage />} />
            <Route path="/citations" element={<CitationPage />} />
            <Route path="/gaps" element={<ResearchGapPage />} />
            <Route path="/questions" element={<QuestionGeneratorPage />} />
            <Route path="/collections" element={<CollectionsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
