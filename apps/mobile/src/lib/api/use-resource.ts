import { useCallback, useEffect, useRef, useState } from "react";
export function useResource<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const loader = useRef(load); loader.current = load;
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<{ key: string; data?: T; error?: Error; loading: boolean }>({ key, loading: true });
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setState(previous => ({ key, data: previous.key === key ? previous.data : undefined, loading: true }));
    loader.current(controller.signal).then(data => { if (active) setState({ key, data, loading: false }); }, error => { if (active) setState({ key, error, loading: false }); });
    return () => { active = false; controller.abort(); };
  }, [key, version]);
  const refresh = useCallback(() => setVersion(v => v + 1), []);
  return { ...(state.key === key ? state : { key, loading: true }), refresh };
}
