import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "مدیریت دفتر املاک",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
