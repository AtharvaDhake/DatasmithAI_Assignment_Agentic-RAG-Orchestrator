import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataSmith AI Agent",
  description: "Multi-modal agentic AI — text, images, PDFs, and audio",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
