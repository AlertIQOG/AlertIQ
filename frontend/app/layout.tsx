import type { Metadata } from 'next';

import './globals.css';

import AppShell from './components/AppShell';
import GoogleAuthProvider from './components/GoogleAuthProvider';

export const metadata: Metadata = {
  title: 'AlertIQ',
  description:
    'AlertIQ — alert ingestion, correlation, and incident management',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
          rel="stylesheet"
        />
      </head>

      <body className="flex h-screen overflow-hidden text-sm font-sans selection:bg-indigo-500/30 bg-slate-950 text-slate-300">
        <GoogleAuthProvider>
          <AppShell>{children}</AppShell>
        </GoogleAuthProvider>
      </body>
    </html>
  );
}