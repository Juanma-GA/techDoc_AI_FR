import { render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title, description, and action", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="Aucun projet"
        description="Créez votre premier projet pour démarrer."
        action={<Button>Nouveau projet</Button>}
      />,
    );

    expect(screen.getByRole("heading", { name: "Aucun projet" })).toBeInTheDocument();
    expect(
      screen.getByText("Créez votre premier projet pour démarrer."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nouveau projet" })).toBeInTheDocument();
  });
});
