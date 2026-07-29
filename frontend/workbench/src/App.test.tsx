import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import {
  APIError,
  type APIClient,
  type ConversationSession,
  type ConversationTurn,
} from "./api";

const activeSession: ConversationSession = {
  schema_version: "1",
  session_id: "conversation.session.1",
  revision: 1,
  status: "active",
  retention_policy: "30_days",
  connection_context_id: null,
  turn_ids: [],
  created_at: "2026-07-29T12:00:00Z",
  updated_at: "2026-07-29T12:00:00Z",
  expires_at: "2026-08-28T12:00:00Z",
};
const closedSession: ConversationSession = {
  ...activeSession,
  revision: 2,
  status: "closed",
  updated_at: "2026-07-29T12:01:00Z",
  expires_at: "2026-08-28T12:01:00Z",
};
const pendingTurn: ConversationTurn = {
  schema_version: "1",
  turn_id: "conversation.turn.1",
  session_id: activeSession.session_id,
  sequence_number: 1,
  status: "pending",
  user_message: "Analyze the login flow.",
  assistant_response: null,
  error_code: null,
  error_message: null,
  created_at: "2026-07-29T12:01:00Z",
  completed_at: null,
};
const sessionWithTurn: ConversationSession = {
  ...activeSession,
  revision: 2,
  turn_ids: [pendingTurn.turn_id],
  updated_at: pendingTurn.created_at,
  expires_at: "2026-08-28T12:01:00Z",
};

function clientFixture() {
  return {
    health: vi.fn().mockResolvedValue({ readiness: "ready" }),
    workflows: vi.fn().mockResolvedValue({ workflows: [] }),
    sessions: vi.fn().mockResolvedValue({ sessions: [activeSession] }),
    session: vi.fn().mockResolvedValue({ session: activeSession }),
    turns: vi.fn().mockResolvedValue({ turns: [] }),
    createSession: vi.fn().mockResolvedValue({ session: activeSession }),
    createTurn: vi.fn().mockResolvedValue({
      session: sessionWithTurn,
      turn: pendingTurn,
    }),
    closeSession: vi.fn().mockResolvedValue({ session: closedSession }),
    deleteSession: vi.fn().mockResolvedValue({ deleted: true }),
  };
}

async function selectSession() {
  fireEvent.click(
    await screen.findByRole("button", {
      name: /Session conversation\.session\.1/,
    }),
  );
  await screen.findByRole("heading", { name: "Selected session" });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PMQA workbench", () => {
  it("renders untrusted catalog text without interpreting HTML", async () => {
    const fixture = clientFixture();
    fixture.sessions.mockResolvedValue({ sessions: [] });
    fixture.workflows.mockResolvedValue({
      workflows: [
        {
          schema_version: "1",
          workflow_id: "workflow.safe",
          workflow_version: "1",
          display_name: "<b>Untrusted workflow</b>",
          description: "<script>unsafe()</script>",
        },
      ],
    });
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
    let resolveCreation:
      | ((value: { session: ConversationSession }) => void)
      | undefined;
    const fixture = clientFixture();
    fixture.sessions.mockResolvedValue({ sessions: [] });
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
    resolveCreation?.({ session: activeSession });
    await waitFor(() => expect(button).not.toBeDisabled());
  });

  it("selects one session and renders its bounded turns", async () => {
    const fixture = clientFixture();
    fixture.turns.mockResolvedValue({ turns: [pendingTurn] });
    render(<App client={fixture as unknown as APIClient} />);

    await selectSession();

    expect(screen.getByText(pendingTurn.user_message)).toBeInTheDocument();
    expect(fixture.session).toHaveBeenCalledOnce();
    expect(fixture.turns).toHaveBeenCalledOnce();
    expect(fixture.turns).toHaveBeenCalledWith(activeSession.session_id);
  });

  it("adds one pending user turn without fabricating assistant output", async () => {
    const fixture = clientFixture();
    render(<App client={fixture as unknown as APIClient} />);
    await selectSession();

    fireEvent.change(screen.getByLabelText("New QA message"), {
      target: { value: pendingTurn.user_message },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add pending turn" }),
    );

    expect(
      await screen.findByText(pendingTurn.user_message),
    ).toBeInTheDocument();
    expect(fixture.createTurn).toHaveBeenCalledOnce();
    expect(fixture.createTurn).toHaveBeenCalledWith(
      activeSession,
      pendingTurn.user_message,
    );
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(
      screen.queryByText("fabricated assistant response"),
    ).not.toBeInTheDocument();
  });

  it("closes the selected session exactly once", async () => {
    const fixture = clientFixture();
    fixture.sessions
      .mockResolvedValueOnce({ sessions: [activeSession] })
      .mockResolvedValue({ sessions: [closedSession] });
    render(<App client={fixture as unknown as APIClient} />);
    await selectSession();

    fireEvent.click(screen.getByRole("button", { name: "Close session" }));

    expect(await screen.findByText("Status: closed")).toBeInTheDocument();
    expect(fixture.closeSession).toHaveBeenCalledOnce();
    expect(fixture.closeSession).toHaveBeenCalledWith(activeSession);
  });

  it("does not delete when explicit confirmation is cancelled", async () => {
    const fixture = clientFixture();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<App client={fixture as unknown as APIClient} />);
    await selectSession();

    fireEvent.click(screen.getByRole("button", { name: "Delete session" }));

    expect(window.confirm).toHaveBeenCalledOnce();
    expect(fixture.deleteSession).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Selected session" }),
    ).toBeInTheDocument();
  });

  it("deletes only after confirmation and clears the selection", async () => {
    const fixture = clientFixture();
    fixture.sessions
      .mockResolvedValueOnce({ sessions: [activeSession] })
      .mockResolvedValue({ sessions: [] });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<App client={fixture as unknown as APIClient} />);
    await selectSession();

    fireEvent.click(screen.getByRole("button", { name: "Delete session" }));

    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Selected session" }),
      ).not.toBeInTheDocument(),
    );
    expect(fixture.deleteSession).toHaveBeenCalledOnce();
    expect(fixture.deleteSession).toHaveBeenCalledWith(
      activeSession.session_id,
    );
  });

  it("refreshes once and never retries a conflicting mutation", async () => {
    const fixture = clientFixture();
    fixture.createTurn.mockRejectedValue(
      new APIError("conversation_failed", 409),
    );
    render(<App client={fixture as unknown as APIClient} />);
    await selectSession();

    fireEvent.change(screen.getByLabelText("New QA message"), {
      target: { value: pendingTurn.user_message },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add pending turn" }),
    );

    expect(await screen.findByText("Status: conflict")).toBeInTheDocument();
    expect(fixture.createTurn).toHaveBeenCalledOnce();
    expect(fixture.session).toHaveBeenCalledTimes(2);
    expect(fixture.turns).toHaveBeenCalledTimes(2);
  });

  it("renders a not-found state for a missing selected session", async () => {
    const fixture = clientFixture();
    fixture.session.mockRejectedValue(
      new APIError("resource_not_found", 404),
    );
    render(<App client={fixture as unknown as APIClient} />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: /Session conversation\.session\.1/,
      }),
    );

    expect(await screen.findByText("Status: not-found")).toBeInTheDocument();
  });

  it("renders unavailable without exposing dependency details", async () => {
    const fixture = clientFixture();
    fixture.health.mockRejectedValue(
      new TypeError("runtime-secret-marker /tmp/private"),
    );
    render(<App client={fixture as unknown as APIClient} />);

    expect(await screen.findByText("Status: unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/runtime-secret-marker/)).not.toBeInTheDocument();
    expect(screen.queryByText(/private/)).not.toBeInTheDocument();
  });

  it("renders fixed-safe server-error state without raw detail", async () => {
    const fixture = clientFixture();
    fixture.health.mockRejectedValue(new APIError("internal_failed", 500));
    render(<App client={fixture as unknown as APIClient} />);

    expect(
      await screen.findByText("Status: server-error"),
    ).toBeInTheDocument();
    expect(screen.queryByText("internal_failed")).not.toBeInTheDocument();
  });
});
