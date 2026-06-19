import { Component, type ErrorInfo, type ReactNode } from "react";

import i18n from "../i18n";

type Props = { children: ReactNode };
type State = { error: Error | null };

// ErrorBoundary au niveau App (regle CLAUDE.md #9). Style via preview-skin.css
// (ecart standard assume du POC, cf. styles/preview-skin.css).
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Pas de logging navigateur (regle #2). Le backend structlog capture
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
      <div className="dw">
        <div
          role="alert"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            height: "100vh",
            padding: 32,
            textAlign: "center",
          }}
        >
          <h1 className="brand" style={{ fontSize: "1.5rem" }}>
            {i18n.t("errors.boundary.title")}
          </h1>
          <p style={{ color: "var(--fg-dim)", maxWidth: 460 }}>
            {i18n.t("errors.boundary.description")}
          </p>
          <button type="button" className="btn primary" onClick={this.handleReload}>
            {i18n.t("errors.boundary.reload")}
          </button>
        </div>
      </div>
    );
  }
}
