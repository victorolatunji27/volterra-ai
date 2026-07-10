import type { Metadata } from "next";
import { Archivo, Newsreader, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";
import { ToastProvider } from "@/components/toast";
import PostHogTracker from "@/components/PostHogTracker";

const archivo = Archivo({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-archivo",
});
const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "VolterraAI — Options flow intelligence",
  description:
    "VolterraAI scans the options market every weekday morning, detects unusual activity, and uses Claude to turn raw flow into plain-English setups.",
  icons: { icon: "/assets/volterra-icon.png" },
};

// Runs synchronously before anything else in <body> parses, so the correct
// theme/accent attributes are on <html> before first paint — no flash of the
// wrong theme. Keys mirror context/ThemeContext.tsx.
const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('vt-theme') || 'light';
    var a = localStorage.getItem('vt-accent') || 'aurora';
    document.documentElement.setAttribute('data-theme', t);
    document.documentElement.setAttribute('data-accent', a);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${archivo.variable} ${newsreader.variable} ${plexMono.variable}`}>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <PostHogTracker />
        <ThemeProvider>
          <ToastProvider>{children}</ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
