import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, JetBrains_Mono, Source_Sans_3 } from "next/font/google";
import { SITE_DESCRIPTION, SITE_URL } from "@/lib/site";
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
  metadataBase: new URL(SITE_URL),
  title: { default: "Highbury", template: "%s · Highbury" },
  description: SITE_DESCRIPTION,
  alternates: {
    canonical: "/",
    // The Markdown copy of the page, for AI agents (index.md/route.ts).
    types: { "text/markdown": "/index.md" },
  },
  // opengraph-image.tsx and twitter-image.tsx add the images.
  openGraph: {
    type: "website",
    siteName: "Highbury",
    title: "Highbury",
    description: SITE_DESCRIPTION,
    url: "/",
    locale: "en_GB",
  },
  twitter: {
    card: "summary_large_image",
    title: "Highbury",
    description: SITE_DESCRIPTION,
  },
  // A short summary that AI agents read; the same text as the description.
  other: { "ai-summary": SITE_DESCRIPTION },
};

// Who runs the site and what the site is, for search engines and AI agents.
// No logo, contact, or social links: the project publishes none.
const JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: "Highbury",
      url: `${SITE_URL}/`,
      description: SITE_DESCRIPTION,
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      name: "Highbury",
      url: `${SITE_URL}/`,
      description: SITE_DESCRIPTION,
      inLanguage: "en-GB",
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
  ],
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
      <body className="min-h-full flex flex-col">
        {/* The browser does not run a JSON-LD script, so the CSP does not apply.
            The escape of < is the one the Next.js JSON-LD guide gives. */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD).replace(/</g, "\\u003c") }}
        />
        {children}
      </body>
    </html>
  );
}
