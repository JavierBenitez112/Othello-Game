import type { ReactNode } from "react";
import type { Metadata } from "next";

import "@/app/globals.css";
import { AdminShell } from "@/components/AdminShell";
import { Providers } from "@/app/providers";

export const metadata: Metadata = {
  title: "Othello Admin Portal",
  description: "Administrative dashboard for Othello/Reversi tournaments",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AdminShell>{children}</AdminShell>
        </Providers>
      </body>
    </html>
  );
}
