import type { Metadata } from "next";
import { Google_Sans } from "next/font/google";
import "./globals.css";

const googleSans = Google_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-google-sans"
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
