import type { WorkItemSummary } from "../types/work-items";

type TodoListProps = {
  items: WorkItemSummary[];
};

const statusLabels = {
  inbox: "Por revisar",
  active: "Activa",
  parked: "Aparcada",
  done: "Completada",
  cancelled: "Cancelada",
};

export default function TodoList({ items }: TodoListProps) {
  // Select tasks independently of their lifecycle status.
  const tasks = items.filter((item) => item.kind === "task");

  const completedCount = tasks.filter(
    (task) => task.status === "done",
  ).length;

  return (
    <section className="todo-card" aria-label="Lista de tareas">
      <header className="todo-header">
        <div>
          <p className="todo-eyebrow">JARVIS</p>
          <h2>Mis tareas</h2>
        </div>

        <span className="todo-counter">
          {completedCount}/{tasks.length}
        </span>
      </header>

      <progress
        className="todo-progress"
        value={completedCount}
        max={tasks.length || 1}
        aria-label="Tareas completadas"
      />

      {tasks.length === 0 ? (
        <p className="todo-empty">Todavía no hay tareas.</p>
      ) : (
        <ul className="todo-items">
          {tasks.map((task) => (
            <li
              key={task.id}
              className="todo-item"
              data-status={task.status}
            >
              <label className="todo-label">
                {/* Display persisted status until updates are connected. */}
                <input
                  type="checkbox"
                  checked={task.status === "done"}
                  disabled
                />

                <span className="todo-task-content">
                  <span className="todo-task-title">{task.title}</span>
                  <span className="todo-task-status">
                    {statusLabels[task.status]}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}

      <footer className="todo-footer">
        {completedCount} de {tasks.length} completadas
      </footer>
    </section>
  );
}