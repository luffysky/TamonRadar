"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearSession,
  getStoredUser,
  setSession,
  type AuthUser,
} from "@/lib/auth";

interface AuthCtx {
  user: AuthUser | null;
  ready: boolean;
  signIn: (token: string, user: AuthUser) => void;
  signOut: () => void;
}

const Ctx = createContext<AuthCtx>({
  user: null,
  ready: false,
  signIn: () => {},
  signOut: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setUser(getStoredUser());
    setReady(true);
  }, []);

  function signIn(token: string, u: AuthUser) {
    setSession(token, u);
    setUser(u);
  }

  function signOut() {
    clearSession();
    setUser(null);
    router.push("/login");
  }

  return <Ctx.Provider value={{ user, ready, signIn, signOut }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  return useContext(Ctx);
}

/** 在需要登入的頁面呼叫:沒登入就導去 /login。回傳 ready 讓頁面決定是否先顯示骨架。 */
export function useRequireAuth(): AuthCtx {
  const ctx = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ctx.ready && !ctx.user) router.replace("/login");
  }, [ctx.ready, ctx.user, router]);
  return ctx;
}
