import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { statusLabel } from "../format";
import { useLive } from "../store";

export function Badge({ status, label }: { status: string; label?: string }) {
  return <span className={`badge s-${status}`}>{label ?? statusLabel(status)}</span>;
}

export function Progress({ value }: { value: number | null | undefined }) {
  return (
    <div className="progress" aria-label="progreso">
      <div style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
    </div>
  );
}

export function PageHead({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="row">{children}</div>
    </div>
  );
}

/** Carga datos de la API y los refresca cuando llegan eventos reales (o cada `pollMs`). */
export function useApi<T>(path: string | null, opts: { live?: boolean; pollMs?: number } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const revision = useLive((s) => (opts.live ? s.revision : 0));
  const load = useCallback(async () => {
    if (!path) return;
    try {
      setData(await api.get<T>(path));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [path]);
  useEffect(() => {
    void load();
  }, [load, revision]);
  useEffect(() => {
    if (!opts.pollMs) return;
    const t = setInterval(() => void load(), opts.pollMs);
    return () => clearInterval(t);
  }, [load, opts.pollMs]);
  return { data, error, reload: load, setData };
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="alert err">{error}</div> : null;
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run };
}
