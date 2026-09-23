import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  API_BASE_URL,
  ApiError,
  createApiClient,
  type ApiClient,
} from "../api/client";
import type { DemoIdentity } from "../api/types";

const STORAGE_KEY = "ai-sana.demo-identity";

type LoadingState = "loading" | "ready" | "error";

interface DemoSessionValue {
  api: ApiClient;
  identities: DemoIdentity[];
  selectedIdentity: DemoIdentity | null;
  state: LoadingState;
  error: string | null;
  selectIdentity: (identityId: string) => void;
  reload: () => void;
}

const DemoSessionContext = createContext<DemoSessionValue | null>(null);

export function DemoSessionProvider({ children }: PropsWithChildren) {
  const [identities, setIdentities] = useState<DemoIdentity[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [state, setState] = useState<LoadingState>("loading");
  const [error, setError] = useState<string | null>(null);

  const bootstrapApi = useMemo(
    () => createApiClient({ baseUrl: API_BASE_URL }),
    [],
  );

  const loadIdentities = useCallback(() => {
    setState("loading");
    setError(null);

    void bootstrapApi
      .demoIdentities()
      .then((items) => {
        setIdentities(items);
        const storedId = window.localStorage.getItem(STORAGE_KEY);
        const nextIdentity =
          items.find((item) => item.id === storedId) ?? items[0] ?? null;
        setSelectedId(nextIdentity?.id ?? null);
        if (nextIdentity) {
          window.localStorage.setItem(STORAGE_KEY, nextIdentity.id);
        } else {
          window.localStorage.removeItem(STORAGE_KEY);
        }
        setState("ready");
      })
      .catch((reason: unknown) => {
        setIdentities([]);
        setSelectedId(null);
        setError(
          reason instanceof ApiError
            ? reason.message
            : "Не удалось загрузить демопользователей",
        );
        setState("error");
      });
  }, [bootstrapApi]);

  useEffect(() => {
    loadIdentities();
  }, [loadIdentities]);

  const selectedIdentity =
    identities.find((identity) => identity.id === selectedId) ?? null;

  const api = useMemo(
    () =>
      createApiClient({
        baseUrl: API_BASE_URL,
        getIdentityId: () => selectedId,
      }),
    [selectedId],
  );

  const selectIdentity = useCallback(
    (identityId: string) => {
      if (!identities.some((identity) => identity.id === identityId)) return;
      setSelectedId(identityId);
      window.localStorage.setItem(STORAGE_KEY, identityId);
    },
    [identities],
  );

  const value = useMemo<DemoSessionValue>(
    () => ({
      api,
      identities,
      selectedIdentity,
      state,
      error,
      selectIdentity,
      reload: loadIdentities,
    }),
    [api, identities, selectedIdentity, state, error, selectIdentity, loadIdentities],
  );

  return (
    <DemoSessionContext.Provider value={value}>
      {children}
    </DemoSessionContext.Provider>
  );
}

export function useDemoSession(): DemoSessionValue {
  const value = useContext(DemoSessionContext);
  if (!value) {
    throw new Error("useDemoSession must be used inside DemoSessionProvider");
  }
  return value;
}
