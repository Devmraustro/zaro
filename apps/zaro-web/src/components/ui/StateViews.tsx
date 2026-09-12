export function EmptyState({
  title,
  description,
  className = "",
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center px-6 py-20 text-center ${className}`}
      data-testid="empty-state"
    >
      <span className="h-px w-12 bg-zaro-bronze" aria-hidden="true" />
      <h2 className="mt-6 font-serif text-2xl font-medium text-zaro-black">{title}</h2>
      {description ? <p className="mt-3 max-w-md text-sm leading-relaxed text-zaro-steel">{description}</p> : null}
    </div>
  );
}

export function LoadingState({ label = "Loading collection" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center px-6 py-20" data-testid="loading-state">
      <span className="relative flex size-8 items-center justify-center">
        <span aria-hidden="true" className="absolute inset-0 animate-spin rounded-full border border-zaro-graphite/15 border-t-zaro-bronze" />
      </span>
      <p className="mt-4 text-xs uppercase tracking-[0.2em] text-zaro-steel">{label}…</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-20 text-center" role="alert" data-testid="error-state">
      <span className="h-px w-12 bg-zaro-bronze" aria-hidden="true" />
      <h2 className="mt-6 font-serif text-2xl font-medium text-zaro-black">We couldn&apos;t load this</h2>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-zaro-steel">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 border border-zaro-graphite/20 px-6 py-2.5 text-[0.7rem] uppercase tracking-[0.18em] text-zaro-graphite transition-colors hover:border-zaro-graphite hover:bg-zaro-graphite hover:text-zaro-ivory"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}