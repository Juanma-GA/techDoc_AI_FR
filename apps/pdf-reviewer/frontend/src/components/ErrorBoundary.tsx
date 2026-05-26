import { Component, type ErrorInfo, type ReactNode } from "react";

import i18n from "../i18n";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      console.error("[ErrorBoundary]", error, info);
    }
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.error) return this.props.children;

    return (
      <div
        role="alert"
        className="flex h-screen flex-col items-center justify-center gap-4 bg-bg p-8 text-center text-fg"
      >
        <h1 className="font-display text-2xl">{i18n.t("errors.boundary.title")}</h1>
        <p className="max-w-md text-fg-dim">{i18n.t("errors.boundary.description")}</p>
        <button
          type="button"
          onClick={this.handleReload}
          className="rounded-lg bg-brand px-4 py-2 text-fg shadow-card transition-colors hover:bg-brand-blue-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue-light"
        >
          {i18n.t("errors.boundary.reload")}
        </button>
      </div>
    );
  }
}
