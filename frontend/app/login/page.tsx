'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { login, loginWithGoogle } from '../services/authApi';
import { GoogleLogin } from '@react-oauth/google';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const user = await login(username, password);
    setSubmitting(false);
    if (user) {
      router.replace('/');
    } else {
      setError('Incorrect username or password');
    }
  };

    const handleGoogleSuccess = async (
    credentialResponse: { credential?: string },
  ) => {
    if (!credentialResponse.credential) {
      setError('Google did not return a valid credential');
      return;
    }

    setError(null);
    setGoogleSubmitting(true);

    const user = await loginWithGoogle(credentialResponse.credential);

    setGoogleSubmitting(false);

    if (user) {
      router.replace('/');
    } else {
      setError('Could not sign in with Google. Please try again.');
    }
  };

  return (
    <main className="flex-1 flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center mb-8">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mr-3 shadow-lg shadow-purple-500/20">
            <i className="fas fa-bolt text-white text-sm"></i>
          </div>
          <span className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">AlertIQ</span>
        </div>

        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
          <h1 className="text-white font-bold text-lg">Sign in</h1>

          <div>
            <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase" htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-[10px] font-bold text-slate-500 uppercase" htmlFor="password">Password</label>
              <Link href="/forgot-password" className="text-[10px] font-medium text-indigo-400 hover:text-indigo-300 transition">
                Forgot password?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
            />
          </div>

          {error && (
            <div className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              <i className="fas fa-circle-exclamation mr-1.5"></i>{error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !username || !password}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2"
          >
            <i className={`fas ${submitting ? 'fa-spinner fa-spin' : 'fa-arrow-right-to-bracket'} text-xs`}></i>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-slate-800" />
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600">
              Or continue with
            </span>
            <div className="h-px flex-1 bg-slate-800" />
          </div>

          <div className="flex justify-center">
            {googleSubmitting ? (
              <div className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-950 py-2.5 text-sm text-slate-300">
                <i className="fas fa-spinner fa-spin text-xs" />
                Connecting to Google…
              </div>
            ) : (
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => {
                  setError('Google sign-in was cancelled or failed.');
                }}
                theme="filled_black"
                size="large"
                shape="rectangular"
                text="continue_with"
                width="302"
              />
            )}
          </div>
          <p className="text-center text-xs text-slate-500">
            Don&apos;t have an account?{' '}
            <Link href="/signup" className="text-indigo-400 hover:text-indigo-300 transition">
              Sign up
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
