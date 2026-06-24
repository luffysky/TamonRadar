"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearSession,
  getStoredUser,
  getToken,
  setSession,
  type AuthUser,
} from "@/lib/auth";
import { getMe } from "@/lib/api";

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
    // 跟後端同步最新使用者資料(is_admin / plan 等),修正舊快取
    const token = getToken();
    if (token) {
      getMe()
        .then(({ user: fresh }) => {
          setUser(fresh);
          setSession(token, fresh);
        })
        .catch(() => {});
    }
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
