import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/lib/providers/QueryProvider";
import { AuthProvider } from "@/lib/auth/authContext";
import { Header } from "@/components/layout/Header";

export const metadata: Metadata = {
  title: "VoiceClone - Story Narrator",
  description: "AI-powered story generation and narration with voice cloning",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          <QueryProvider>
            <Header />
            {children}
          </QueryProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
