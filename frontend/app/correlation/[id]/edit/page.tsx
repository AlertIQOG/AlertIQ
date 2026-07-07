"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

export default function EditCorrelationRulePage() {
  const params = useParams();
  const ruleId = params.id as string;

  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      <header className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-900/80 backdrop-blur shrink-0 gap-4">
        <Link
          href="/correlation"
          className="text-slate-400 hover:text-white transition text-xs font-medium flex items-center gap-2"
        >
          <i className="fas fa-arrow-left"></i> BACK
        </Link>

        <div className="h-4 w-px bg-slate-700"></div>

        <h1 className="text-white font-bold text-lg">Edit Correlation Rule</h1>
      </header>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full text-center">
          <div className="text-white font-bold mb-2">Edit page is ready</div>
          <div className="text-xs text-slate-400 mb-4">
            Rule ID: {ruleId}
          </div>
          <div className="text-xs text-slate-500">
            Next step: connect this page to the existing rule form and PATCH API.
          </div>
        </div>
      </div>
    </main>
  );
}