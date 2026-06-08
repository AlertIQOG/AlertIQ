interface PageHeaderProps {
  title: string;
  badge?: string;
}

export default function PageHeader({ title, badge }: PageHeaderProps) {
  return (
    <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/80 backdrop-blur shrink-0">
      <div className="flex items-center gap-2">
        <h1 className="text-white font-medium text-lg">{title}</h1>
        {badge && (
          <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">
            {badge}
          </span>
        )}
      </div>
    </header>
  );
}