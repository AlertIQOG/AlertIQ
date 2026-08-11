// Inline error banner for failed actions; dismissible when onDismiss is given.
interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
}

export default function ErrorBanner({ message, onDismiss, className = '' }: ErrorBannerProps) {
  return (
    <div className={`flex items-center justify-between gap-3 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 ${className}`}>
      <div className="flex items-center gap-2 text-xs text-red-300">
        <i className="fas fa-triangle-exclamation text-red-400"></i>
        <span>{message}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          aria-label="Dismiss error"
          onClick={onDismiss}
          className="rounded px-2 py-1 text-red-400 transition-colors hover:bg-red-500/20 hover:text-red-300"
        >
          <i className="fas fa-times"></i>
        </button>
      )}
    </div>
  );
}
