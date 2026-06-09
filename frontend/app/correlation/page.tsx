// app/correlation/page.tsx
import PageHeader from '../components/PageHeader';

export default function CorrelationPage() {
  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      <PageHeader title="Correlation Rules" badge="Library" />
      
      <div className="flex-1 overflow-y-auto p-6">
        <p className="text-slate-400">Correlation rules go here...</p>
      </div>
    </main>
  );
}