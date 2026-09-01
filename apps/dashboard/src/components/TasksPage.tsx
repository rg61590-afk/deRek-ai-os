import { FormEvent, useEffect, useState } from "react";
import { ApiError, createTask, listTasks, TaskData, TaskState } from "../lib/api";

const STATE_STYLES: Record<TaskState, string> = {
  Queued: "text-slate-300",
  Planning: "text-amber-300",
  Running: "text-amber-300",
  Waiting: "text-amber-300",
  Completed: "text-emerald-300",
  Failed: "text-rose-300",
  Cancelled: "text-slate-500",
};

/**
 * Task Engine page: create a task via the Task Engine's default
 * in-process executor and list existing tasks (ID, name, state,
 * created time), with a manual refresh button.
 */
export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskData[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [capability, setCapability] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setLoadError(null);
    try {
      setTasks(await listTasks());
    } catch (error) {
      setLoadError(error instanceof ApiError ? error.message : "Could not load tasks.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await createTask({ name, capability });
      setName("");
      setCapability("");
      await refresh();
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Could not create task.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-2xl space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-xl backdrop-blur">
        <h2 className="text-lg font-semibold tracking-tight text-slate-50">Create Task</h2>

        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label htmlFor="task-name" className="block text-sm text-slate-400">
              Name
            </label>
            <input
              id="task-name"
              type="text"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Summarize weekly report"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-slate-500"
            />
          </div>

          <div>
            <label htmlFor="task-capability" className="block text-sm text-slate-400">
              Capability
            </label>
            <input
              id="task-capability"
              type="text"
              required
              pattern="[a-z][a-z0-9_]*"
              title="Lowercase snake_case, e.g. research or image_generation"
              value={capability}
              onChange={(event) => setCapability(event.target.value)}
              placeholder="e.g. research"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-slate-500"
            />
          </div>

          {formError && <p className="text-sm text-rose-300">{formError}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create Task"}
          </button>
        </form>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight text-slate-50">Tasks</h2>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-200 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {loadError && <p className="mt-4 text-sm text-rose-300">{loadError}</p>}

        {!loadError && tasks.length === 0 && (
          <p className="mt-4 text-sm text-slate-400">No tasks yet.</p>
        )}

        {tasks.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-4 font-medium">Task ID</th>
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 font-medium">State</th>
                  <th className="py-2 pr-4 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} className="border-b border-slate-900">
                    <td className="py-2 pr-4 font-mono text-xs text-slate-400" title={task.id}>
                      {task.id.slice(0, 8)}
                    </td>
                    <td className="py-2 pr-4 text-slate-100">{task.name}</td>
                    <td className={`py-2 pr-4 font-medium ${STATE_STYLES[task.state]}`}>
                      {task.state}
                    </td>
                    <td className="py-2 pr-4 text-slate-400">
                      {new Date(task.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
