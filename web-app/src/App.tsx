import { useState, useCallback } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Splash from './pages/Splash';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import Copilot from './pages/Copilot';
import Accountability from './pages/Accountability';
import Settings from './pages/Settings';
import Support from './pages/Support';
import Notifications from './pages/Notifications';
import Legal from './pages/Legal';
import Mt5 from './pages/Mt5';

export type Page =
  | 'splash' | 'login' | 'signup' | 'forgot-password'
  | 'dashboard' | 'copilot' | 'accountability' | 'settings'
  | 'support' | 'notifications' | 'legal' | 'mt5';

export type NavigateFn = (page: Page, opts?: Record<string, string>) => void;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000, refetchOnWindowFocus: true },
  },
});

export default function App() {
  const [page, setPage] = useState<Page>('splash');
  const [navOpts, setNavOpts] = useState<Record<string, string> | null>(null);

  const navigate = useCallback((p: Page, opts?: Record<string, string>) => {
    setNavOpts(opts ?? null);
    setPage(p);
  }, []);

  const appPages: Page[] = [
    'dashboard', 'copilot', 'accountability', 'settings',
    'support', 'notifications', 'legal', 'mt5',
  ];
  const needsLayout = appPages.includes(page);

  function renderPage() {
    switch (page) {
      case 'splash': return <Splash navigate={navigate} />;
      case 'login': return <Login navigate={navigate} />;
      case 'signup': return <Signup navigate={navigate} />;
      case 'forgot-password': return <ForgotPassword navigate={navigate} />;
      case 'dashboard': return <Dashboard navigate={navigate} />;
      case 'copilot': return <Copilot navigate={navigate} />;
      case 'accountability': return <Accountability navigate={navigate} />;
      case 'settings': return <Settings navigate={navigate} />;
      case 'support': return <Support navigate={navigate} />;
      case 'notifications': return <Notifications navigate={navigate} />;
      case 'legal': return <Legal navigate={navigate} tab={(navOpts?.tab as 'terms' | 'risk') || 'terms'} />;
      case 'mt5': return <Mt5 navigate={navigate} />;
    }
  }

  return (
    <QueryClientProvider client={queryClient}>
      {needsLayout ? (
        <Layout page={page} navigate={navigate}>
          {renderPage()}
        </Layout>
      ) : (
        renderPage()
      )}
    </QueryClientProvider>
  );
}
