import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LUSIA",
  description: "AI Agent hỗ trợ học tập cho học sinh khiếm thị",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // lang="vi" để trình đọc màn hình dùng giọng tiếng Việt
    <html lang="vi" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
