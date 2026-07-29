import { createRoot } from "react-dom/client";

import { APIClient } from "./api";
import { App } from "./App";
import { consumeRuntimeFragment } from "./bootstrap";
import "./styles.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("PMQA workbench root is unavailable");
}

const credentials = consumeRuntimeFragment(window.location, window.history);
const root = createRoot(rootElement);
if (credentials === null) {
  root.render(
    <main>
      <h1>PMQA Workbench unavailable</h1>
      <p role="alert">
        Secure browser bootstrap failed. Close this tab and run pmqa web again.
      </p>
    </main>,
  );
} else {
  root.render(<App client={new APIClient(credentials)} />);
}
