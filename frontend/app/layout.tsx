import './globals.css';
import Link from 'next/link';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet" />
      </head>
      <body className="flex h-screen overflow-hidden text-sm font-sans selection:bg-indigo-500/30 bg-slate-950 text-slate-300">
        
        {/* Sidebar - עכשיו הוא גלובלי */}
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
              <Link href="/rules" className="nav-btn w-full flex items-center px-4 py-3 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors text-left group">
                <i className="fas fa-code-branch w-5 text-center mr-2 group-hover:text-white"></i>
                <span className="font-medium">Correlation Rules</span>
              </Link>
            </nav>
          </div>

          {/* User Profile Area */}
          <div className="p-4 border-t border-slate-800 bg-slate-900/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-xs font-bold text-white border border-slate-600 shadow-sm">DG</div>
                <div className="overflow-hidden">
                  <div className="text-sm font-medium text-white truncate">Dana G.</div>
                  <div className="text-[10px] text-slate-500">Admin</div>
                </div>
              </div>
              <button className="text-slate-400 hover:text-white transition p-2 rounded-full hover:bg-slate-800">
                <i className="fas fa-cog text-lg"></i>
              </button>
            </div>
          </div>
        </aside>

        {/* Dynamic Content - כאן ירונדר התוכן של כל עמוד (למשל ה-Feed או ה-Rules) */}
        {children}

      </body>
    </html>
  );
}