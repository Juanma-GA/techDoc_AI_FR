import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Pas de logging navigateur (interdit par check_standard.sh). Le backend
    // structlog capture l'incident via X-Request-Id au prochain appel.
    void error;
    void info;
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
          <h1 className="font-display text-xl text-fg">Une erreur est survenue</h1>
          <p className="max-w-md text-fg-dim">{this.state.error.message}</p>
          <button
            type="button"
            onClick={this.reset}
            className="rounded-sm border border-md bg-card px-3 py-2 text-fg hover:bg-card-hover"
          >
            Reessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
