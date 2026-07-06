'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { AuthUser, getStoredUser, getToken } from '../services/apiClient';
import { logout } from '../services/authApi';

/**
 * Client-side shell: renders the persistent sidebar for authenticated
 * users and redirects to /login when no token is stored.
 *
 * This guard is a UX convenience only — the real enforcement is the
 * backend returning 401 on every protected endpoint.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  // Read localStorage only after mount to avoid the hydration mismatch
  // that would fire the redirect effect before the real token is known.
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mounted, setMounted] = useState(false);

  // Re-read the stored session on every navigation. AppShell lives in the
  // root layout, so it never remounts — without re-reading on `pathname`
  // change, a same-tab login (which writes localStorage then navigates)
  // would leave `token` stale at null and bounce the user back to /login.
  // The `storage` event only covers *other* tabs, so it can't cover this.
  useEffect(() => {
    setToken(getToken());
    setUser(getStoredUser());
    setMounted(true);

    // Keep state in sync when another tab logs out / logs in.
    const sync = () => {
      setToken(getToken());
      setUser(getStoredUser());
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, [pathname]);

  const isPublicPage = pathname === '/login' || pathname === '/signup';

  // Read the token fresh from localStorage rather than the `token` state:
  // right after a same-tab login the state update is still queued, so the
  // state would be a stale null and bounce the just-authenticated user
  // back to /login. getToken() reflects what login() already wrote.
  useEffect(() => {
    if (!mounted) return;
    if (!isPublicPage && !getToken()) {
      router.replace('/login');
    }
  }, [mounted, isPublicPage, pathname, router]);

  if (isPublicPage) {
    return <>{children}</>;
  }

  // Don't render until we've checked localStorage — prevents a flash of
  // the unauthenticated state before the redirect fires.
  if (!mounted || !token) {
    return null;
  }

  const initials = (user?.full_name || user?.username || '?')
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <>
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 z-20">
        <div>
          <div className="h-16 flex items-center px-6 border-b border-slate-800 mb-6">
            <Link href="/" aria-label="Go to Alerts Feed" className="flex items-center transition-opacity hover:opacity-80">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mr-3 shadow-lg shadow-purple-500/20">
                <i className="fas fa-bolt text-white text-xs"></i>
              </div>
              <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">AlertIQ</span>
            </Link>
          </div>
          <nav className="px-3 space-y-2">
            <Link href="/" className="nav-btn w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
              <i className="fas fa-satellite-dish w-5 text-center mr-2 group-hover:text-white"></i>
              <span className="font-medium">Alerts Feed</span>
            </Link>
            <Link href="/incidents" className="nav-btn w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
              <i className="fas fa-briefcase-medical w-5 text-center mr-2 group-hover:text-white"></i>
              <span className="font-medium">Incidents Management</span>
            </Link>
            <Link href="/correlation" className="nav-btn w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
              <i className="fas fa-code-branch w-5 text-center mr-2 group-hover:text-white"></i>
              <span className="font-medium">Correlation Rules</span>
            </Link>
          </nav>
        </div>

        {/* User Profile Area */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-xs font-bold text-white border border-slate-600 shadow-sm">{initials}</div>
              <div className="overflow-hidden">
                <div className="text-sm font-medium text-white truncate">{user?.full_name || user?.username || 'Unknown'}</div>
                <div className="text-[10px] text-slate-500">{user?.role || ''}</div>
              </div>
            </div>
            <button
              onClick={logout}
              className="text-slate-400 hover:text-white transition p-2 rounded-full hover:bg-slate-800"
              title="Log out"
            >
              <i className="fas fa-right-from-bracket text-lg"></i>
            </button>
          </div>
        </div>
      </aside>

      {children}
    </>
  );
}
