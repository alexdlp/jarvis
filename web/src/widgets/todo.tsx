import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import TodoWidget from "./TodoWidget";
import "../index.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("The todo widget requires a root element.");
}

createRoot(root).render(
  <StrictMode>
    <TodoWidget />
  </StrictMode>,
);
