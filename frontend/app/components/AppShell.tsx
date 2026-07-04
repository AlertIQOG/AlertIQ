'use client';

import { useEffect, useMemo, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  AuthUser,
  getStoredUserRaw,
  getToken,
  subscribeToSession,
} from '../services/apiClient';
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

  // localStorage-backed session state; the server snapshot is null so the
  // first client render after hydration picks up the real values.
  const token = useSyncExternalStore(subscribeToSession, getToken, () => null);
  const userRaw = useSyncExternalStore(subscribeToSession, getStoredUserRaw, () => null);
  const user = useMemo<AuthUser | null>(() => {
    if (!userRaw) return null;
    try {
      return JSON.parse(userRaw) as AuthUser;
    } catch {
      return null;
    }
  }, [userRaw]);

  const isLoginPage = pathname === '/login';

  useEffect(() => {
    if (!isLoginPage && !token) {
      router.replace('/login');
    }
  }, [isLoginPage, token, router]);

  if (isLoginPage) {
    return <>{children}</>;
  }

  if (!token) {
    // No session (or still redirecting) — don't flash the protected UI.
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
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mr-3 shadow-lg shadow-purple-500/20">
              <i className="fas fa-bolt text-white text-xs"></i>
            </div>
            <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">AlertIQ</span>
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
