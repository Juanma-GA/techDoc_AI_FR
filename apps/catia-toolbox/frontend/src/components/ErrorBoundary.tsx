import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Pas de logging navigateur (interdit par check_standard.sh). Le backend
    // structlog capture l'incident via X-Request-Id au prochain appel.
    void error;
    void info;
  }

  reset = () => this.setState({ error: null });

  override render() {
    if (this.state.error) {
      return (
        <div
          style={{
            display: "flex",
            height: "100vh",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            padding: "1.5rem",
            textAlign: "center",
          }}
        >
          <h1 style={{ fontFamily: '"Orbitron", sans-serif' }}>Une erreur est survenue</h1>
          <p className="hint">{this.state.error.message}</p>
          <button type="button" className="btn primary" onClick={this.reset}>
            Reessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
