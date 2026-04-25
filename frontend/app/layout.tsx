import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlertIQ",
  description: "Unified alert management platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" />
      </head>
      <body className="flex h-screen overflow-hidden text-sm font-sans selection:bg-primary-500/30">
        {children}
      </body>
    </html>
  );
}