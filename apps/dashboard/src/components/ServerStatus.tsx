import { useEffect, useState } from "react";
import { ApiError, getHealth, getVersion } from "../lib/api";

type ConnectionState = "checking" | "online" | "offline";

interface DashboardData {
  appName: string | null;
  version: string | null;
  environment: string | null;
  connection: ConnectionState;
}

const POLL_INTERVAL_MS = 15_000;

/**
 * Displays the deRek AI OS name, version, and live server status by
 * polling the /health and /version endpoints of the API.
 */
export default function ServerStatus() {
  const [data, setData] = useState<DashboardData>({
    appName: null,
    version: null,
    environment: null,
    connection: "checking",
  });

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    async function fetchStatus() {
      try {
        const [health, version] = await Promise.all([
          getHealth(controller.signal),
          getVersion(controller.signal),
        ]);

        if (!isMounted) return;

        setData({
          appName: version.name,
          version: version.version,
          environment: version.environment,
          connection: health.status === "ok" ? "online" : "offline",
        });
      } catch (error) {
        if (!isMounted) return;
        if (error instanceof ApiError || error instanceof TypeError) {
          setData((previous) => ({ ...previous, connection: "offline" }));
        }
      }
    }

    fetchStatus();
    const intervalId = window.setInterval(fetchStatus, POLL_INTERVAL_MS);

    return () => {
      isMounted = false;
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, []);

  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-xl backdrop-blur">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
        {data.appName ?? "deRek AI OS"}
      </h1>

      <dl className="mt-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <dt className="text-sm text-slate-400">Version</dt>
          <dd className="font-mono text-sm text-slate-200">
            {data.version ?? "—"}
          </dd>
        </div>

        <div className="flex items-center justify-between">
          <dt className="text-sm text-slate-400">Server Status</dt>
          <dd>
            <StatusBadge connection={data.connection} />
          </dd>
        </div>
      </dl>
    </div>
  );
}

function StatusBadge({ connection }: { connection: ConnectionState }) {
  const config: Record<ConnectionState, { label: string; dot: string; text: string }> = {
    checking: { label: "Checking…", dot: "bg-amber-400", text: "text-amber-300" },
    online: { label: "Online", dot: "bg-emerald-400", text: "text-emerald-300" },
    offline: { label: "Offline", dot: "bg-rose-500", text: "text-rose-300" },
  };

  const { label, dot, text } = config[connection];

  return (
    <span className={`inline-flex items-center gap-2 text-sm font-medium ${text}`}>
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
