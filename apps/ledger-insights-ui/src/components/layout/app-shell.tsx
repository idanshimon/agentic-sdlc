import { ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./topbar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <TopBar />
        <main className="flex-1 px-4 sm:px-6 lg:px-8 pt-6 pb-24 max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
