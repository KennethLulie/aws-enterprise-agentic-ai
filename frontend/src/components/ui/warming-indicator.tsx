'use client';

import * as React from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface WarmingIndicatorProps extends React.ComponentProps<"div"> {
  /** Whether the warming indicator is visible */
  isVisible: boolean;
  /** Estimated time in seconds (default: 30) */
  estimatedTime?: number;
  /** Whether to show elapsed time counter */
  showElapsed?: boolean;
}

/**
 * WarmingIndicator displays a banner when the server is warming up (cold start).
 * Features animated gradient background, pulsing spinner, and optional elapsed timer.
 */
function WarmingIndicator({
  isVisible,
  estimatedTime = 30,
  showElapsed = false,
  className,
  ...props
}: WarmingIndicatorProps) {
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);

  // Reset and track elapsed time when visible
  React.useEffect(() => {
    if (!isVisible) {
      setElapsedSeconds(0);
      return;
    }

    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [isVisible]);

  if (!isVisible) {
    return null;
  }

  return (
    <div
      data-slot="warming-indicator"
      role="status"
      aria-live="polite"
      aria-label="Server is warming up"
      className={cn(
        // Base styles
        "flex items-center gap-3 px-6 py-3",
        // Animated gradient background
        "bg-gradient-to-r from-amber-50 via-orange-50 to-amber-50 bg-[length:200%_100%] animate-gradient-x",
        // Border styling
        "border-b border-amber-200 dark:border-amber-800",
        // Dark mode background
        "dark:from-amber-950/40 dark:via-orange-950/40 dark:to-amber-950/40",
        // Fade-in animation
        "animate-in fade-in slide-in-from-top-2 duration-300",
        className
      )}
      {...props}
    >
      {/* Pulsing spinner */}
      <div className="relative">
        <Loader2
          className="h-5 w-5 animate-spin text-amber-600 dark:text-amber-400"
          aria-hidden="true"
        />
        {/* Pulse ring effect */}
        <div className="absolute inset-0 h-5 w-5 animate-ping rounded-full bg-amber-400/30" />
      </div>

      {/* Text content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
          Warming up the server...
        </p>
        <p className="text-xs text-amber-600 dark:text-amber-400">
          {showElapsed && elapsedSeconds > 0 ? (
            <>
              {elapsedSeconds}s elapsed — This may take up to {estimatedTime} seconds
            </>
          ) : (
            <>This may take up to {estimatedTime} seconds</>
          )}
        </p>
      </div>

      {/* Optional progress indicator */}
      {showElapsed && (
        <div className="hidden sm:flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
          <div className="h-1.5 w-16 rounded-full bg-amber-200 dark:bg-amber-800 overflow-hidden">
            <div
              className="h-full bg-amber-500 dark:bg-amber-400 transition-all duration-1000 ease-linear"
              style={{
                width: `${Math.min((elapsedSeconds / estimatedTime) * 100, 100)}%`,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export { WarmingIndicator };
export type { WarmingIndicatorProps };
