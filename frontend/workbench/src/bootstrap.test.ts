import { describe, expect, it, vi } from "vitest";

import { consumeRuntimeFragment } from "./bootstrap";

const sessionToken = "a".repeat(43);
const csrfToken = "b".repeat(43);

describe("secure runtime bootstrap", () => {
  it("copies exact tokens and removes the fragment synchronously", () => {
    const replaceState = vi.fn();

    const credentials = consumeRuntimeFragment(
      {
        hash: `#session_token=${sessionToken}&csrf_token=${csrfToken}`,
        pathname: "/",
        search: "",
      },
      { replaceState },
    );

    expect(credentials).toEqual({ sessionToken, csrfToken });
    expect(replaceState).toHaveBeenCalledOnce();
    expect(replaceState).toHaveBeenCalledWith(null, "", "/");
  });

  it.each([
    "",
    `#csrf_token=${csrfToken}&session_token=${sessionToken}`,
    `#session_token=${sessionToken}&csrf_token=${csrfToken}&extra=x`,
    `#session_token=${sessionToken}&csrf_token=${sessionToken}`,
    `#session_token=short&csrf_token=${csrfToken}`,
  ])("fails closed for an invalid fragment", (hash) => {
    const replaceState = vi.fn();

    expect(
      consumeRuntimeFragment(
        { hash, pathname: "/", search: "" },
        { replaceState },
      ),
    ).toBeNull();
    expect(replaceState).toHaveBeenCalledOnce();
  });
});
