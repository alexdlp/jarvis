import { useState } from "react";
import { useApp } from "@modelcontextprotocol/ext-apps/react";

import TodoList from "../components/TodoList";
import type { CaptureWorkItemResult } from "../types/work-items";

function ConnectedTodoList() {
  const [result, setResult] = useState<CaptureWorkItemResult | null>(null);
  const [toolError, setToolError] = useState<string | null>(null);

  const { error } = useApp({
    appInfo: {
      name: "Jarvis tasks",
      version: "0.1.0",
    },
    capabilities: {},

    onAppCreated(app) {
      // Register the handler before connecting to the MCP host.
      app.ontoolresult = (response) => {
        if (response.isError || !response.structuredContent) {
          setToolError("No se pudo obtener el resultado de la operación.");
          return;
        }

        // Describe the expected output of our capture_workitem tool.
        const data = response.structuredContent as CaptureWorkItemResult;

        setResult(data);
        setToolError(null);
      };
    },
  });

  if (error || toolError) {
    return <p role="alert">No se pudo cargar la lista de tareas.</p>;
  }

  if (result === null) {
    return <p role="status">Esperando las tareas…</p>;
  }

  if (result.list_error || result.items === null) {
    return (
      <p role="alert">
        El elemento se guardó, pero no se pudo recuperar la colección.
      </p>
    );
  }

  return <TodoList items={result.items} />;
}

export default function TodoWidget() {
  // Keep the empty-state preview available in the standalone browser.
  if (window.parent === window) {
    return <TodoList items={[]} />;
  }

  return <ConnectedTodoList />;
}

