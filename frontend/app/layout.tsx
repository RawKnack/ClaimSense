import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClaimSense",
  description: "AI-powered OPD claim submission and adjudication engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <header className="header">
            <a href="/">ClaimSense</a>
          </header>
          <main className="main">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
