// Inline error banner for failed actions; dismissible when onDismiss is given.
interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  className?: string;
}

export default function ErrorBanner({
  message,
  onDismiss,
  actionLabel,
  onAction,
  actionDisabled = false,
  className = '',
}: ErrorBannerProps) {
  return (
    <div
      className={`flex items-center justify-between gap-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 ${className}`}
      role="alert"
    >
      <div className="flex min-w-0 items-center gap-2 text-xs text-red-300">
        <i className="fas fa-triangle-exclamation shrink-0 text-red-400" />

        <span className="leading-relaxed">
          {message}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {actionLabel && onAction && (
          <button
            type="button"
            disabled={actionDisabled}
            onClick={onAction}
            className="rounded-md border border-red-500/30 px-3 py-1.5 text-xs font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {actionDisabled && (
              <i className="fas fa-circle-notch fa-spin mr-2" />
            )}

            {actionLabel}
          </button>
        )}

        {onDismiss && (
          <button
            type="button"
            aria-label="Dismiss error"
            onClick={onDismiss}
            className="rounded px-2 py-1 text-red-400 transition-colors hover:bg-red-500/20 hover:text-red-300"
          >
            <i className="fas fa-times" />
          </button>
        )}
      </div>
    </div>
  );
}