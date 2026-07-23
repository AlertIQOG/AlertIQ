'use client';

import { useState } from 'react';
import Link from 'next/link';
import { requestPasswordReset } from '../services/authApi';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    await requestPasswordReset(email);
    setSubmitting(false);
    setSent(true);
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

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          {sent ? (
            <div className="space-y-4 text-center">
              <div className="w-12 h-12 mx-auto rounded-full bg-green-500/10 border border-green-500/30 flex items-center justify-center">
                <i className="fas fa-envelope-circle-check text-green-400 text-lg"></i>
              </div>
              <h1 className="text-white font-bold text-lg">Check your email</h1>
              <p className="text-sm text-slate-400">
                If an account exists for <span className="text-slate-200">{email}</span>, we&apos;ve sent a link to reset your password. It expires in 30 minutes.
              </p>
              <Link href="/login" className="inline-block text-xs text-indigo-400 hover:text-indigo-300 transition">
                <i className="fas fa-arrow-left mr-1.5"></i>Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <h1 className="text-white font-bold text-lg">Forgot password?</h1>
                <p className="text-xs text-slate-500 mt-1">
                  Enter your account email and we&apos;ll send you a reset link.
                </p>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-500 mb-1.5 uppercase" htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
                />
              </div>

              <button
                type="submit"
                disabled={submitting || !email}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2"
              >
                <i className={`fas ${submitting ? 'fa-spinner fa-spin' : 'fa-paper-plane'} text-xs`}></i>
                {submitting ? 'Sending…' : 'Send reset link'}
              </button>

              <p className="text-center text-xs text-slate-500">
                <Link href="/login" className="text-indigo-400 hover:text-indigo-300 transition">
                  <i className="fas fa-arrow-left mr-1.5"></i>Back to sign in
                </Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
