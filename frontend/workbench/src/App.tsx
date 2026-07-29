import {
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  APIClient,
  APIError,
  type ConversationSession,
  type ConversationTurn,
  type RetentionPolicy,
  type WorkflowDefinition,
} from "./api";

type ViewState =
  | "loading"
  | "ready"
  | "empty"
  | "closed"
  | "conflict"
  | "not-found"
  | "validation"
  | "unavailable"
  | "server-error";

interface AppProps {
  readonly client: APIClient;
}

function failureState(error: unknown): ViewState {
  if (error instanceof APIError) {
    if (error.status === 409) return "conflict";
    if (error.status === 404) return "not-found";
    if (error.status === 400) return "validation";
    if (error.status >= 500) return "server-error";
  }
  return "unavailable";
}

export function App({ client }: AppProps) {
  const [workflows, setWorkflows] = useState<readonly WorkflowDefinition[]>([]);
  const [sessions, setSessions] = useState<readonly ConversationSession[]>([]);
  const [selected, setSelected] = useState<ConversationSession | null>(null);
  const [turns, setTurns] = useState<readonly ConversationTurn[]>([]);
  const [retention, setRetention] = useState<RetentionPolicy>("30_days");
  const [message, setMessage] = useState("");
  const [state, setState] = useState<ViewState>("loading");
  const [busy, setBusy] = useState(false);
  const mutationActive = useRef(false);

  const refreshSessions = useCallback(async () => {
    const result = await client.sessions();
    setSessions(result.sessions);
    setState(result.sessions.length === 0 ? "empty" : "ready");
  }, [client]);

  const refreshSelected = useCallback(
    async (sessionId: string) => {
      const [sessionResult, turnResult] = await Promise.all([
        client.session(sessionId),
        client.turns(sessionId),
      ]);
      setSelected(sessionResult.session);
      setTurns(turnResult.turns);
      setState(
        sessionResult.session.status === "closed" ? "closed" : "ready",
      );
    },
    [client],
  );

  useEffect(() => {
    let active = true;
    void Promise.all([client.health(), client.workflows(), client.sessions()])
      .then(([, workflowResult, sessionResult]) => {
        if (!active) return;
        setWorkflows(workflowResult.workflows);
        setSessions(sessionResult.sessions);
        setState(sessionResult.sessions.length === 0 ? "empty" : "ready");
      })
      .catch((error: unknown) => {
        if (active) setState(failureState(error));
      });
    return () => {
      active = false;
    };
  }, [client]);

  async function runMutation(operation: () => Promise<void>) {
    if (mutationActive.current) return;
    mutationActive.current = true;
    setBusy(true);
    try {
      await operation();
    } catch (error: unknown) {
      const next = failureState(error);
      setState(next);
      if (next === "conflict") {
        try {
          if (selected !== null) {
            await refreshSelected(selected.session_id);
          } else {
            await refreshSessions();
          }
          setState("conflict");
        } catch {
          setState("unavailable");
        }
      }
    } finally {
      mutationActive.current = false;
      setBusy(false);
    }
  }

  function createSession(event: FormEvent) {
    event.preventDefault();
    void runMutation(async () => {
      const result = await client.createSession(retention);
      await refreshSessions();
      await refreshSelected(result.session.session_id);
    });
  }

  function createTurn(event: FormEvent) {
    event.preventDefault();
    const userMessage = message.trim();
    if (selected === null || userMessage.length === 0) {
      setState("validation");
      return;
    }
    void runMutation(async () => {
      const result = await client.createTurn(selected, userMessage);
      setSelected(result.session);
      setTurns((current) => [...current, result.turn]);
      setMessage("");
      setState("ready");
    });
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Local, offline conversation shell</p>
        <h1>PMQA Workbench</h1>
        <p>
          AI responses and workflow execution are not enabled yet. New turns
          remain pending and are not presented as assistant output.
        </p>
      </header>

      <p className={`status status-${state}`} role="status" aria-live="polite">
        Status: {state}
      </p>

      <section aria-labelledby="workflow-heading">
        <h2 id="workflow-heading">Available workflows</h2>
        {workflows.length === 0 ? (
          <p>No workflows are registered in this offline workbench.</p>
        ) : (
          <ul>
            {workflows.map((workflow) => (
              <li key={`${workflow.workflow_id}:${workflow.workflow_version}`}>
                <strong>{workflow.display_name}</strong>
                <span>{workflow.description}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="sessions-heading">
        <h2 id="sessions-heading">Sessions</h2>
        <form onSubmit={createSession}>
          <label htmlFor="retention">Retention</label>
          <select
            id="retention"
            value={retention}
            onChange={(event) =>
              setRetention(event.target.value as RetentionPolicy)
            }
            disabled={busy}
          >
            <option value="session_only">This session only</option>
            <option value="7_days">7 days</option>
            <option value="30_days">30 days</option>
            <option value="90_days">90 days</option>
          </select>
          <button type="submit" disabled={busy}>
            Create session
          </button>
        </form>
        {sessions.length === 0 ? (
          <p>No sessions yet.</p>
        ) : (
          <ul className="session-list">
            {sessions.map((session) => (
              <li key={session.session_id}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setState("loading");
                    void refreshSelected(session.session_id).catch(
                      (error: unknown) => setState(failureState(error)),
                    );
                  }}
                >
                  Session {session.session_id} — {session.status}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selected !== null && (
        <section aria-labelledby="selected-heading">
          <h2 id="selected-heading">Selected session</h2>
          <dl>
            <dt>Status</dt>
            <dd>{selected.status}</dd>
            <dt>Revision</dt>
            <dd>{selected.revision}</dd>
            <dt>Retention</dt>
            <dd>{selected.retention_policy}</dd>
          </dl>

          <h3>Turns</h3>
          {turns.length === 0 ? (
            <p>No turns in this session.</p>
          ) : (
            <ol>
              {turns.map((turn) => (
                <li key={turn.turn_id}>
                  <p>{turn.user_message}</p>
                  <small>{turn.status}</small>
                </li>
              ))}
            </ol>
          )}

          <form onSubmit={createTurn}>
            <label htmlFor="message">New QA message</label>
            <textarea
              id="message"
              value={message}
              maxLength={32768}
              onChange={(event) => setMessage(event.target.value)}
              disabled={busy || selected.status === "closed"}
              required
            />
            <button
              type="submit"
              disabled={busy || selected.status === "closed"}
            >
              Add pending turn
            </button>
          </form>

          <div className="actions">
            <button
              type="button"
              disabled={busy || selected.status === "closed"}
              onClick={() =>
                void runMutation(async () => {
                  const result = await client.closeSession(selected);
                  setSelected(result.session);
                  await refreshSessions();
                  setState("closed");
                })
              }
            >
              Close session
            </button>
            <button
              className="danger"
              type="button"
              disabled={busy}
              onClick={() => {
                if (!window.confirm("Delete this local PMQA session?")) return;
                void runMutation(async () => {
                  await client.deleteSession(selected.session_id);
                  setSelected(null);
                  setTurns([]);
                  await refreshSessions();
                });
              }}
            >
              Delete session
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
