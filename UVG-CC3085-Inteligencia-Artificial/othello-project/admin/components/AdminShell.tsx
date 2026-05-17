"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { PropsWithChildren, useEffect } from "react";
import { BarChart3, Grid2x2, Home, LogOut, Shield, Trophy, Users } from "lucide-react";

import { ConnectionStatus } from "@/components/ConnectionStatus";
import { Button } from "@/components/ui/button";
import { clearAuthToken, getAuthToken } from "@/lib/auth";
import { adminWsClient } from "@/lib/ws";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/tournaments", label: "Tournaments", icon: Trophy },
  { href: "/players", label: "Players", icon: Users },
  { href: "/standings", label: "Standings", icon: BarChart3 },
  { href: "/live-games", label: "Live Games", icon: Grid2x2 },
];

export function AdminShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/login";

  useEffect(() => {
    const token = getAuthToken();
    if (!token && !isLogin) {
      router.replace("/login");
      return;
    }
    if (token && isLogin) {
      router.replace("/");
      return;
    }
    if (token) {
      adminWsClient.connect();
    }
  }, [isLogin, router]);

  if (isLogin) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-72 shrink-0 border-r bg-card/70 p-6 backdrop-blur lg:block">
          <div className="mb-8 flex items-center gap-3">
            <div className="rounded-xl bg-primary p-2 text-primary-foreground">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <div className="font-semibold">Tournament Admin</div>
              <div className="text-sm text-muted-foreground">Othello control room</div>
            </div>
          </div>
          <nav className="space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-colors",
                    pathname === item.href ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>
        <main className="flex-1 p-4 md:p-6">
          <header className="mb-6 flex flex-col gap-4 rounded-2xl border bg-card/80 p-4 shadow-panel md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-lg font-semibold">Admin Portal</div>
              <div className="text-sm text-muted-foreground">Live tournament operations, standings, and game supervision.</div>
            </div>
            <div className="flex items-center gap-3">
              <ConnectionStatus />
              <Button
                variant="outline"
                onClick={() => {
                  clearAuthToken();
                  adminWsClient.disconnect();
                  router.replace("/login");
                }}
              >
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </Button>
            </div>
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}
