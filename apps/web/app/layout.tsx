import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Self-hosted from apps/web/app/fonts (OFL-licensed) rather than next/font/google so
// `next build` never depends on network access to fonts.googleapis.com/fonts.gstatic.com.
const googleSans = localFont({
  src: "./fonts/GoogleSansFlex.woff2",
  weight: "1 1000",
  variable: "--font-google-sans",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Canopy",
  description: "Turn your source documents into canonical, source-grounded technical courses."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={googleSans.variable}>
      <body>{children}</body>
    </html>
  );
}
