import { Component, type ErrorInfo, type ReactNode } from "react";

import i18n from "../i18n";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Pas de logging navigateur (regle #2). structlog cote backend capture
    // l'incident via X-Request-Id au prochain appel.
    void error;
    void info;
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  override render(): ReactNode {
    if (!this.state.error) return this.props.children;

    return (
      <div
        role="alert"
        style={{
          display: "flex",
          height: "100vh",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          padding: 32,
          textAlign: "center",
        }}
      >
        <h1 style={{ fontFamily: '"Orbitron", sans-serif', fontSize: "1.5rem", margin: 0 }}>
          {i18n.t("errors.boundary.title")}
        </h1>
        <p className="hint" style={{ maxWidth: "28rem" }}>
          {i18n.t("errors.boundary.description")}
        </p>
        {this.state.error.message ? (
          <pre
            className="error"
            style={{
              maxWidth: "40rem",
              maxHeight: "12rem",
              overflow: "auto",
              textAlign: "left",
              whiteSpace: "pre-wrap",
            }}
          >
            {this.state.error.message}
          </pre>
        ) : null}
        <button type="button" className="btn primary" onClick={this.handleReload}>
          {i18n.t("errors.boundary.reload")}
        </button>
      </div>
    );
  }
}
