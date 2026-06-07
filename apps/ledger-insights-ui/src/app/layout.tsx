import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { ThemeProvider } from "next-themes";
import { QueryProvider } from "@/lib/query-client";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ledger Insights — agentic-sdlc v0.7",
  description:
    "Operator dashboard for the governed agentic SDLC reference design. Four planes: Standards, Pipeline, Ledger+Doctor, Agent HQ.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
          <QueryProvider>
            <TooltipProvider delayDuration={150}>
              <AppShell>{children}</AppShell>
              <Toaster
                theme="dark"
                position="bottom-right"
                toastOptions={{
                  className:
                    "!bg-[var(--elevated)] !border-[var(--border-default)] !text-[var(--text)]",
                }}
              />
            </TooltipProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
