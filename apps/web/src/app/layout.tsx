import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, JetBrains_Mono, Source_Sans_3 } from "next/font/google";
import "./globals.css";

// Barlow Condensed is not a variable font, so each weight is named. The
// headlines of the landing screen have words in italic. Without the italic
// files the browser slants the upright letters, which looks wrong.
const barlowCondensed = Barlow_Condensed({
  variable: "--font-barlow-condensed",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  style: ["normal", "italic"],
});

const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Highbury",
  description:
    "An AI football analyst for Arsenal's 2003-04 and 2025-26 seasons. Unofficial fan project.",
};

export const viewport: Viewport = {
  // --background of globals.css. A meta tag cannot read a CSS variable.
  themeColor: "#0A120E",
  colorScheme: "dark",
  // The page goes under the home indicator, so the sticky bar can pad itself
  // clear of it. The body pads the sides clear of a notch in landscape.
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The page has one dark theme. The class makes the dark: variants of shadcn match it.
    <html
      lang="en"
      className={`${barlowCondensed.variable} ${sourceSans.variable} ${jetbrainsMono.variable} dark h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
