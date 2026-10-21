import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ListChecks, RotateCcw, ShieldCheck } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ProjectProvider } from './context/ProjectContext';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';

// Pages
import { SignInPage } from './pages/auth/SignInPage';
import { SignUpPage } from './pages/auth/SignUpPage';
import { AdminDashboard } from './pages/admin/AdminDashboard';
import { UsersPage } from './pages/admin/UsersPage';
import { UserDashboard } from './pages/user/UserDashboard';
import { ProjectsListPage } from './pages/projects/ProjectsListPage';
import { ProjectFormPage } from './pages/projects/ProjectFormPage';
import { ProjectDetailPage } from './pages/projects/ProjectDetailPage';
import { ModelSelectionPage } from './pages/shared/ModelSelectionPage';
import { ProfilePage } from './pages/shared/ProfilePage';
import { SettingsPage } from './pages/shared/SettingsPage';
import { EmptyComponentPage } from './pages/shared/EmptyComponentPage';
import { ToolCallCorrectnessPage } from './pages/c1/ToolCallCorrectnessPage';
import { AccessDeniedPage } from './pages/AccessDeniedPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { StateAwareWorkflowPage } from './features/c2/pages/StateAwareWorkflowPage';

// Role-aware root redirect component
const RootRedirect = () => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/sign-in" replace />;
  }

  return <Navigate to={user.role === 'ADMIN' ? '/admin/dashboard' : '/app/dashboard'} replace />;
};

export const App = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProjectProvider>
          <BrowserRouter>
            <Routes>
              {/* Role-aware Root Redirect */}
              <Route path="/" element={<RootRedirect />} />

              {/* Public Auth Routes */}
              <Route path="/sign-in" element={<SignInPage />} />
              <Route path="/sign-up" element={<SignUpPage />} />

              {/* Administrator Routes */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute requiredRole="ADMIN">
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/admin/dashboard" replace />} />
                <Route path="dashboard" element={<AdminDashboard />} />
                <Route path="users" element={<UsersPage />} />

                {/* Shared Projects Workspace */}
                <Route path="projects" element={<ProjectsListPage />} />
                <Route path="projects/new" element={<ProjectFormPage />} />
                <Route path="projects/:projectId" element={<ProjectDetailPage />} />
                <Route path="projects/:projectId/edit" element={<ProjectFormPage />} />

                {/* Component 1: Explainable Tool-Call Correctness Testing */}
                <Route
                  path="tool-call-correctness"
                  element={<ToolCallCorrectnessPage />}
                />
                {/* State-Aware Multi-Step Workflow Testing */}
                <Route
                  path="workflow-testing"
                  element={<StateAwareWorkflowPage />}
                />
                <Route
                  path="robustness-recovery"
                  element={
                    <EmptyComponentPage
                      title="Robustness and Failure Recovery Testing"
                      icon={RotateCcw}
                    />
                  }
                />
                <Route
                  path="policy-safety"
                  element={
                    <EmptyComponentPage
                      title="Policy-Aware Safety and Prompt-Injection Testing"
                      icon={ShieldCheck}
                    />
                  }
                />
                <Route path="model-selection" element={<ModelSelectionPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              {/* User Routes */}
              <Route
                path="/app"
                element={
                  <ProtectedRoute requiredRole="USER">
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/app/dashboard" replace />} />
                <Route path="dashboard" element={<UserDashboard />} />

                {/* Shared Projects Workspace */}
                <Route path="projects" element={<ProjectsListPage />} />
                <Route path="projects/new" element={<ProjectFormPage />} />
                <Route path="projects/:projectId" element={<ProjectDetailPage />} />
                <Route path="projects/:projectId/edit" element={<ProjectFormPage />} />

                {/* Component 1: Explainable Tool-Call Correctness Testing */}
                <Route
                  path="tool-call-correctness"
                  element={<ToolCallCorrectnessPage />}
                />
                {/* State-Aware Multi-Step Workflow Testing */}
                <Route
                  path="workflow-testing"
                  element={<StateAwareWorkflowPage />}
                />
                <Route
                  path="robustness-recovery"
                  element={
                    <EmptyComponentPage
                      title="Robustness and Failure Recovery Testing"
                      icon={RotateCcw}
                    />
                  }
                />
                <Route
                  path="policy-safety"
                  element={
                    <EmptyComponentPage
                      title="Policy-Aware Safety and Prompt-Injection Testing"
                      icon={ShieldCheck}
                    />
                  }
                />
                <Route path="model-selection" element={<ModelSelectionPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              {/* Standalone Access Denied & 404 */}
              <Route path="/access-denied" element={<AccessDeniedPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </BrowserRouter>
        </ProjectProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
