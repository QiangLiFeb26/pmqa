import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { APIClient } from "./api";

function clientFixture() {
  return {
    health: vi.fn().mockResolvedValue({ readiness: "ready" }),
    workflows: vi.fn().mockResolvedValue({
      workflows: [
        {
          schema_version: "1",
          workflow_id: "workflow.safe",
          workflow_version: "1",
          display_name: "<b>Untrusted workflow</b>",
          description: "<script>unsafe()</script>",
        },
      ],
    }),
    sessions: vi.fn().mockResolvedValue({ sessions: [] }),
    createSession: vi.fn(),
  };
}

describe("PMQA workbench", () => {
  it("renders untrusted catalog text without interpreting HTML", async () => {
    const fixture = clientFixture();
    const { container } = render(
      <App client={fixture as unknown as APIClient} />,
    );

    expect(
      await screen.findByText("<b>Untrusted workflow</b>"),
    ).toBeInTheDocument();
    expect(screen.getByText("<script>unsafe()</script>")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/AI responses and workflow execution/)).toBeTruthy();
  });

  it("prevents duplicate session submission while pending", async () => {
    let resolveCreation: ((value: unknown) => void) | undefined;
    const fixture = clientFixture();
    fixture.createSession.mockReturnValue(
      new Promise((resolve) => {
        resolveCreation = resolve;
      }),
    );
    render(<App client={fixture as unknown as APIClient} />);
    await screen.findByText("No sessions yet.");

    const button = screen.getByRole("button", { name: "Create session" });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(fixture.createSession).toHaveBeenCalledOnce();
    expect(button).toBeDisabled();
    resolveCreation?.({ session: { session_id: "conversation.session.1" } });
    await waitFor(() => expect(button).not.toBeDisabled());
  });
});
