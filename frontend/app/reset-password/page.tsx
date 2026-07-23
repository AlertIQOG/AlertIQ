'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { resetPassword } from '../services/authApi';

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSubmitting(true);
    const result = await resetPassword(token, password);
    setSubmitting(false);

    if (typeof result === 'string') {
      setError(result);
    } else {
      router.replace('/');
    }
  };

  if (!token) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl text-center space-y-4">
        <div className="w-12 h-12 mx-auto rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
          <i className="fas fa-link-slash text-red-400 text-lg"></i>
        </div>
        <h1 className="text-white font-bold text-lg">Invalid reset link</h1>
        <p className="text-sm text-slate-400">This link is missing its token. Request a new one.</p>
        <Link href="/forgot-password" className="inline-block text-xs text-indigo-400 hover:text-indigo-300 transition">
          Request a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-4">
      <div>
        <h1 className="text-white font-bold text-lg">Set a new password</h1>
        <p className="text-xs text-slate-500 mt-1">Choose a new password for your account.</p>
      </div>

      <div>
        <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase" htmlFor="password">New password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          required
          minLength={8}
          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
        />
        <p className="text-[10px] text-slate-600 mt-1">Minimum 8 characters</p>
      </div>

      <div>
        <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase" htmlFor="confirmPassword">Confirm password</label>
        <input
          id="confirmPassword"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          autoComplete="new-password"
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
        disabled={submitting || !password || !confirmPassword}
        className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2"
      >
        <i className={`fas ${submitting ? 'fa-spinner fa-spin' : 'fa-key'} text-xs`}></i>
        {submitting ? 'Updating…' : 'Reset password'}
      </button>

      <p className="text-center text-xs text-slate-500">
        <Link href="/login" className="text-indigo-400 hover:text-indigo-300 transition">
          <i className="fas fa-arrow-left mr-1.5"></i>Back to sign in
        </Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="flex-1 flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center mb-8">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mr-3 shadow-lg shadow-purple-500/20">
            <i className="fas fa-bolt text-white text-sm"></i>
          </div>
          <span className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">AlertIQ</span>
        </div>
        <Suspense fallback={<div className="text-center text-slate-500 text-sm">Loading…</div>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </main>
  );
}
