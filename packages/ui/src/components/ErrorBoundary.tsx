import { AlertCircle } from "lucide-react";
import { Component, ErrorInfo, PropsWithChildren, ReactNode } from "react";

import { cn } from "../lib/utils";

export type ErrorBoundaryProps = PropsWithChildren<{
  /** Optional class name for the container. */
  className?: string;
  /** Callback fired when an error is caught. Useful for logging. */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}>;

type ErrorBoundaryState = {
  hasError: boolean;
  error: Error | null;
};

/**
 * ErrorBoundary catches React render errors and displays a graceful fallback UI.
 * Place once at the app root level (main.tsx) to protect the entire application.
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary onError={(err, info) => console.error(err, info)}>
 *   <App />
 * </ErrorBoundary>
 * ```
 *
 * Limitations:
 * - Does NOT catch errors in event handlers (use try/catch)
 * - Does NOT catch errors in async code (use .catch())
 * - Does NOT catch server-side rendering errors
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error for debugging (structlog on backend + console here)
    console.error("ErrorBoundary caught:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className={cn(
            "flex min-h-screen items-center justify-center bg-background p-4",
            this.props.className
          )}
        >
          <div className="max-w-md rounded-lg border border-destructive/50 bg-destructive/5 p-6 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-1 h-5 w-5 flex-shrink-0 text-destructive" />
              <div className="space-y-2">
                <h2 className="font-semibold text-foreground">Application Error</h2>
                <p className="text-sm text-muted-foreground">
                  An unexpected error occurred. Please refresh the page or contact support.
                </p>
                {process.env.NODE_ENV === "development" && this.state.error && (
                  <details className="mt-3 space-y-2">
                    <summary className="cursor-pointer text-xs font-mono text-muted-foreground hover:text-foreground">
                      Error details (dev only)
                    </summary>
                    <pre className="overflow-auto rounded bg-muted p-2 text-xs">
                      {this.state.error.toString()}
                    </pre>
                  </details>
                )}
                <button
                  onClick={() => window.location.reload()}
                  className="mt-4 rounded bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Refresh Page
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
