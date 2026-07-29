export interface RuntimeCredentials {
  readonly sessionToken: string;
  readonly csrfToken: string;
}

const BOOTSTRAP_PATTERN =
  /^#session_token=([A-Za-z0-9_-]{43,128})&csrf_token=([A-Za-z0-9_-]{43,128})$/;

export function consumeRuntimeFragment(
  location: Pick<Location, "hash" | "pathname" | "search">,
  history: Pick<History, "replaceState">,
): RuntimeCredentials | null {
  const match = BOOTSTRAP_PATTERN.exec(location.hash);
  history.replaceState(null, "", `${location.pathname}${location.search}`);
  if (match === null || match[1] === match[2]) {
    return null;
  }
  return {
    sessionToken: match[1],
    csrfToken: match[2],
  };
}
