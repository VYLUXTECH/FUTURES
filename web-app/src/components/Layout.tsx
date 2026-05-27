import type { Page } from '../App';
import { useAuth } from '../hooks/useAuth';

interface LayoutProps {
  page: Page;
  navigate: (p: Page) => void;
  children: React.ReactNode;
}

const NAV_ITEMS: { label: string; page: Page }[] = [
  { label: 'Dashboard', page: 'dashboard' },
  { label: 'Copilot', page: 'copilot' },
  { label: 'Trades', page: 'accountability' },
  { label: 'Settings', page: 'settings' },
  { label: 'Support', page: 'support' },
];

export default function Layout({ page, navigate, children }: LayoutProps) {
  const { signOut } = useAuth();

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1 className="app-logo" style={{ cursor: 'pointer' }} onClick={() => navigate('dashboard')}>
          FUTURES
        </h1>
        <nav className="app-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.page}
              className={`nav-btn ${page === item.page ? 'nav-active' : ''}`}
              onClick={() => navigate(item.page)}
            >
              {item.label}
            </button>
          ))}
          <button className="nav-btn nav-logout" onClick={signOut}>Logout</button>
        </nav>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
