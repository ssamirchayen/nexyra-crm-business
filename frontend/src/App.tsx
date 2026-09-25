import { useEffect } from "react";
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { AuthLoadingPage } from "./components/auth/AuthLoadingPage";
import { AppShell } from "./components/layout/AppShell";
import { useAuth } from "./contexts/AuthContext";
import { ActivitiesPage } from "./pages/ActivitiesPage";
import { AuditPage } from "./pages/AuditPage";
import { CadencesPage } from "./pages/CadencesPage";
import { CommunicationPage } from "./pages/CommunicationPage";
import { ForcePasswordChangePage } from "./pages/ForcePasswordChangePage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { InboxPage } from "./pages/InboxPage";
import { LeadsPage } from "./pages/LeadsPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { OperationalDashboardPage } from "./pages/OperationalDashboardPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PipelinePage } from "./pages/PipelinePage";
import { RecommendationsPage } from "./pages/RecommendationsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SecurityPage } from "./pages/SecurityPage";
import { ServiceQueuePage } from "./pages/ServiceQueuePage";
import { SettingsPage } from "./pages/SettingsPage";
import { TeamPage } from "./pages/TeamPage";

const titles: Record<string, string> = {
  "/overview": "Visão geral",
  "/operational-dashboard": "Dashboard operacional",
  "/leads": "Leads",
  "/service-queue": "Fila inteligente",
  "/cadences": "Cadências",
  "/communication": "Comunicação",
  "/pipeline": "Pipeline",
  "/opportunities": "Oportunidades",
  "/activities": "Atividades",
  "/inbox": "Caixa de entrada",
  "/team": "Equipe",
  "/recommendations": "Recomendações",
  "/reports": "Relatórios",
  "/audit": "Auditoria",
  "/settings": "Configurações",
  "/security": "Segurança",
};

function RequireAuth() {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === "loading") {
    return <AuthLoadingPage />;
  }

  if (auth.status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (auth.user?.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  return <Outlet />;
}

function LoginRoute() {
  const auth = useAuth();

  if (auth.status === "loading") {
    return <AuthLoadingPage />;
  }

  if (auth.status === "authenticated") {
    return (
      <Navigate
        to={auth.user?.must_change_password ? "/change-password" : "/overview"}
        replace
      />
    );
  }

  return <LoginPage />;
}

export function App() {
  const location = useLocation();

  useEffect(() => {
    if (["/login", "/forgot-password", "/reset-password"].includes(location.pathname)) {
      return;
    }
    document.title = `${titles[location.pathname] ?? "Nexyra CRM"} · Nexyra CRM`;
  }, [location.pathname]);

  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route element={<RequireAuth />}>
        <Route path="/change-password" element={<ForcePasswordChangePage />} />
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/operational-dashboard" element={<OperationalDashboardPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/service-queue" element={<ServiceQueuePage />} />
          <Route path="/cadences" element={<CadencesPage />} />
          <Route path="/communication" element={<CommunicationPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/opportunities" element={<OpportunitiesPage />} />
          <Route path="/activities" element={<ActivitiesPage />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
