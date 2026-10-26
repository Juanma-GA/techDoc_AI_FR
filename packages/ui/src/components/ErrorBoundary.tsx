import { AlertCircle } from "lucide-react";
import { Component } from "react";
import type { ErrorInfo, PropsWithChildren, ReactNode } from "react";

import { cn } from "../lib/utils";
import "./error-boundary.css";

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

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error for debugging (structlog on backend + console here)
    console.error("ErrorBoundary caught:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          className={cn(
            "ui-error-boundary",
            this.props.className
          )}
        >
          <div className="ui-error-card">
            <div className="ui-error-content">
              <AlertCircle className="ui-error-icon" aria-hidden="true" />
              <div className="ui-error-copy">
                <h2 className="ui-error-title">Application Error</h2>
                <p className="ui-error-message">
                  An unexpected error occurred. Please refresh the page or contact support.
                </p>
                {process.env.NODE_ENV === "development" && this.state.error && (
                  <details className="ui-error-details">
                    <summary>
                      Error details (dev only)
                    </summary>
                    <pre>
                      {this.state.error.toString()}
                    </pre>
                  </details>
                )}
                <button
                  onClick={() => window.location.reload()}
                  className="ui-error-refresh"
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
