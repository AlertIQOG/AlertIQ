import PageHeader from "../components/PageHeader";

export default function IncidentsPage() {
  return (
    <main className="flex-1 relative flex flex-col h-full overflow-hidden bg-slate-950">
      <PageHeader title="Incidents Management" badge="Active Work" />
      
      <div className="flex-1 overflow-y-auto p-6">
        <p className="text-slate-400">Incidents management table goes here...</p>
      </div>
    </main>
  );
}