import { useAppStore } from '../stores/app-store'
import { Loader2 } from 'lucide-react'
import clsx from 'clsx'

export function ProgressPanel() {
  const { currentProgress, progressMessages } = useAppStore()

  const progress = currentProgress?.progress ?? -1
  const hasProgress = progress >= 0 && progress <= 100

  return (
    <div className="bg-sidebar-bg border-b border-border px-4 py-2">
      {/* Progress bar */}
      <div className="flex items-center gap-3 mb-2">
        <Loader2 size={16} className="animate-spin text-accent" />
        <div className="flex-1">
          <div className="h-2 bg-border rounded-full overflow-hidden">
            <div
              className={clsx(
                'h-full bg-accent transition-all duration-300',
                !hasProgress && 'animate-pulse w-full'
              )}
              style={hasProgress ? { width: `${progress}%` } : undefined}
            />
          </div>
        </div>
        {hasProgress && (
          <span className="text-sm text-text-secondary w-12 text-right">
            {progress}%
          </span>
        )}
      </div>

      {/* Current status */}
      {currentProgress && (
        <div className="text-sm text-text-secondary">
          <span className="text-accent">[{currentProgress.stage}]</span>{' '}
          {currentProgress.message}
        </div>
      )}

      {/* Recent messages (collapsible) */}
      {progressMessages.length > 1 && (
        <details className="mt-2">
          <summary className="text-xs text-text-secondary cursor-pointer hover:text-text-primary">
            Show {progressMessages.length} messages
          </summary>
          <div className="mt-1 max-h-24 overflow-y-auto text-xs font-mono bg-editor-bg p-2 rounded">
            {progressMessages.slice(-20).map((msg, i) => (
              <div key={i} className="text-text-secondary">
                {msg}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
