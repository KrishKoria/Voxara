import "~/styles/globals.css";

import { type Metadata } from "next";
import { Geist } from "next/font/google";
import { Toaster } from "~/components/ui/sonner";
import { Providers } from "~/components/providers";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "~/components/ui/sidebar";
import { AppSidebar } from "~/components/app-sidebar";

export const metadata: Metadata = {
  title: "Voxara",
  description: "Photo to Video app, for the new generation",
  icons: [{ rel: "icon", url: "/favicon.ico" }],
};

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geist.variable}`}>
      <body className="flex min-h-svh flex-col items-center justify-center antialiased">
        <Providers>
          <Toaster />
          <SidebarProvider defaultOpen={false}>
            <AppSidebar />
            <SidebarInset className="flex h-screen flex-col">
              <header className="bg-background sticky-top z-10 border-b px-4 py-2">
                <SidebarTrigger />
              </header>
              <main className="flex-1 overflow-y-auto">{children}</main>
            </SidebarInset>
          </SidebarProvider>
        </Providers>
      </body>
    </html>
  );
}
