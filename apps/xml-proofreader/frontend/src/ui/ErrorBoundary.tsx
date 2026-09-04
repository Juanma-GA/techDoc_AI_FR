import { Component, type ErrorInfo, type PropsWithChildren, type ReactNode } from "react";

// Local ErrorBoundary matching this app's own plain-CSS theme (no Tailwind
// pipeline here — @internal/ui's ErrorBoundary relies on Tailwind utility
// classes that would render unstyled in this app, see H-NEW-17). Same
// behavior as the shared component: catches render errors, shows a fallback
// with a refresh action, logs to console (+ optional onError callback).
type Props = PropsWithChildren<{ onError?: (error: Error, errorInfo: ErrorInfo) => void }>;
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 16,
          background: "var(--bg)",
          color: "var(--ink)",
        }}
      >
        <div
          style={{
            maxWidth: 420,
            background: "var(--panel)",
            border: "1px solid var(--line)",
            borderRadius: 14,
            padding: 20,
            boxShadow: "0 24px 70px rgba(0,0,0,.3)",
          }}
        >
          <h3 style={{ margin: "0 0 8px", fontSize: 15 }}>Application Error</h3>
          <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--muted)" }}>
            An unexpected error occurred. Please refresh the page or contact support.
          </p>
          {import.meta.env.DEV && (
            <details style={{ marginBottom: 12 }}>
              <summary style={{ cursor: "pointer", fontSize: 11, color: "var(--muted)" }}>
                Error details (dev only)
              </summary>
              <pre
                style={{
                  background: "var(--surface-1, var(--bg))",
                  color: "var(--text-secondary, var(--fg))",
                  borderRadius: 8,
                  padding: 12,
                  fontFamily: "var(--mono)",
                  fontSize: "11.5px",
                  overflow: "auto",
                  maxHeight: "40vh",
                  whiteSpace: "pre-wrap",
                }}
              >
                {error.toString()}
              </pre>
            </details>
          )}
          <button className="btn primary" onClick={() => window.location.reload()}>
            Refresh Page
          </button>
        </div>
      </div>
    );
  }
}
