import { ReactNode, useState } from "react";
import ServerStatus from "./components/ServerStatus";
import TasksPage from "./components/TasksPage";

type View = "status" | "tasks";

export default function App() {
  const [view, setView] = useState<View>("status");

  return (
    <main className="flex min-h-screen flex-col items-center gap-6 px-4 py-12">
      <nav className="flex gap-1 rounded-full border border-slate-800 bg-slate-900/60 p-1">
        <TabButton active={view === "status"} onClick={() => setView("status")}>
          Status
        </TabButton>
        <TabButton active={view === "tasks"} onClick={() => setView("tasks")}>
          Tasks
        </TabButton>
      </nav>

      {view === "status" ? <ServerStatus /> : <TasksPage />}
    </main>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
        active ? "bg-slate-100 text-slate-900" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}
