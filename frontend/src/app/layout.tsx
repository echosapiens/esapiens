import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "E.sapiens -- Split-Runtime Bio-Orchestrator",
  description:
    "Describe your bioinformatics analysis in natural language. E.sapiens handles research, contract generation, and execution.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full`}
    >
      <body className="h-full bg-slate-950 text-slate-100 font-sans antialiased flex flex-col">
        {/* Navigation */}
        <nav className="border-b border-slate-800">
          <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
            <a href="/" className="text-lg font-bold text-slate-100 tracking-tight">
              <span className="text-cyan-400">E.</span>sapiens
            </a>
            <div className="flex items-center gap-4 text-sm">
              <a
                href="/"
                className="text-slate-400 hover:text-slate-200 transition-colors"
              >
                Home
              </a>
              <a
                href="/dashboard"
                className="text-slate-400 hover:text-slate-200 transition-colors"
              >
                Dashboard
              </a>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}