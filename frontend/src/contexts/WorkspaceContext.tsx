import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { Workspace } from "../types/dashboard";
import { useAuth } from "./AuthContext";

const STORAGE_KEY = "nexyra-workspace";

type WorkspaceContextValue = {
  workspaces: Workspace[];
  workspace: Workspace | null;
  loading: boolean;
  error: string | null;
  selectWorkspace: (publicId: string) => void;
  refreshWorkspaces: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: PropsWithChildren) {
  const auth = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEY),
  );

  const workspaces = useMemo<Workspace[]>(
    () =>
      auth.workspaces.map((item) => ({
        public_id: item.public_id,
        name: item.name,
        slug: item.slug,
        segment: item.segment,
        active: true,
      })),
    [auth.workspaces],
  );

  useEffect(() => {
    if (auth.status !== "authenticated") {
      return;
    }

    setSelectedId((current) => {
      if (workspaces.some((item) => item.public_id === current)) {
        return current;
      }

      const next = workspaces[0]?.public_id ?? null;
      if (next) {
        localStorage.setItem(STORAGE_KEY, next);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
      return next;
    });
  }, [auth.status, workspaces]);

  const selectWorkspace = useCallback(
    (publicId: string) => {
      if (!workspaces.some((item) => item.public_id === publicId)) {
        return;
      }

      setSelectedId(publicId);
      localStorage.setItem(STORAGE_KEY, publicId);
    },
    [workspaces],
  );

  const refreshWorkspaces = useCallback(async () => {
    await auth.refreshSession();
  }, [auth]);

  const workspace = useMemo(
    () => workspaces.find((item) => item.public_id === selectedId) ?? null,
    [selectedId, workspaces],
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspaces,
      workspace,
      loading: auth.status === "loading",
      error: null,
      selectWorkspace,
      refreshWorkspaces,
    }),
    [auth.status, refreshWorkspaces, selectWorkspace, workspace, workspaces],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);

  if (!context) {
    throw new Error(
      "useWorkspace precisa ser usado dentro de WorkspaceProvider.",
    );
  }

  return context;
}
