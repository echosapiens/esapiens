"use client";

import Link from "next/link";
import {
  Dna,
  FlaskConical,
  FileCode2,
  ShieldCheck,
  ArrowRight,
  Activity,
  Beaker,
  BookOpen,
} from "lucide-react";
import { Reveal } from "@/components/ui/Reveal";

const features = [
  {
    icon: Dna,
    title: "AI-Powered Pipeline Design",
    description:
      "Describe your analysis goal in natural language. E.sapiens plans a reproducible DAG of containerized bioinformatics tools — each step pinned to an immutable SHA256 digest.",
  },
  {
    icon: FileCode2,
    title: "Interactive Parameter Editor",
    description:
      "Review and modify every command-line flag before execution. Diff highlighting shows exactly what you changed from the agent's recommendation.",
  },
  {
    icon: Activity,
    title: "Real-Time Execution Monitoring",
    description:
      "Watch your pipeline run live. Gantt chart tracks step progress, logs stream in real time, and metrics update continuously via WebSocket.",
  },
  {
    icon: ShieldCheck,
    title: "Provenance & Reproducibility",
    description:
      "Every run records exact container digests, CLI parameters, and timestamps. Export publication-ready Methods sections with one click.",
  },
  {
    icon: Beaker,
    title: "Grant & Budget Tracking",
    description:
      "Track compute spending against research grants. Get alerts when budgets approach exhaustion. Full cost attribution per session and pipeline.",
  },
  {
    icon: BookOpen,
    title: "Publication-Ready Outputs",
    description:
      "Auto-generate Methods text citing exact tool versions, container digests, and parameter values. Download as .txt or copy to clipboard for your manuscript.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen" style={{ background: "var(--mac-window-bg)" }}>
      {/* ── macOS-style Navigation ─────────────────────────────────── */}
      <nav
        className="sticky top-0 z-50 border-b backdrop-blur-2xl"
        style={{
          background: "var(--mac-toolbar-bg)",
          borderColor: "var(--mac-toolbar-separator)",
        }}
      >
        <div className="mx-auto flex h-10 max-w-7xl items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="mac-traffic-lights">
              <div className="mac-traffic-light mac-traffic-close" />
              <div className="mac-traffic-light mac-traffic-minimize" />
              <div className="mac-traffic-light mac-traffic-zoom" />
            </div>
            <FlaskConical className="h-4 w-4 ml-2" style={{ color: "var(--brand-gold)" }} />
            <span className="text-sm font-semibold" style={{ color: "var(--mac-label)" }}>
              E.sapiens
            </span>
          </div>
          <Link
            href="/dashboard"
            className="mac-btn mac-btn-primary text-xs"
          >
            Open Dashboard
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </nav>

      {/* ── macOS-style Hero ───────────────────────────────────────── */}
      <section className="relative overflow-hidden py-20" style={{ background: "var(--mac-sidebar-bg)" }}>
        <div className="absolute inset-0 opacity-[0.07]">
          <div className="absolute left-1/4 top-1/4 h-96 w-96 rounded-full" style={{ background: "var(--brand-gold)" }} />
          <div className="absolute right-1/4 bottom-1/4 h-64 w-64 rounded-full bg-system-blue" />
        </div>
        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <Reveal>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs"
              style={{ background: "rgba(201, 168, 76, 0.1)", color: "var(--brand-gold)", border: "1px solid rgba(201, 168, 76, 0.2)" }}
            >
              <FlaskConical className="h-3.5 w-3.5" />
              Academic Bioinformatics IDE
            </div>
          </Reveal>
          <Reveal delay={100}>
            <h1 className="mb-4 text-4xl font-bold leading-tight tracking-tight text-white">
              Reproducible Pipelines,{" "}
              <span style={{ color: "var(--brand-gold)" }}>Publication-Ready</span> Results
            </h1>
          </Reveal>
          <Reveal delay={200}>
            <p className="mx-auto mb-8 max-w-2xl text-sm" style={{ color: "rgba(255,255,255,0.6)" }}>
              Plan, execute, and document bioinformatics analyses with
              AI-assisted pipeline design. Every container is pinned to an
              immutable SHA256 digest — because science must be reproducible.
            </p>
          </Reveal>
          <Reveal delay={300}>
            <div className="flex items-center justify-center gap-3">
              <Link
                href="/dashboard"
                className="mac-btn mac-btn-accent"
              >
                Get Started
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                href="#features"
                className="mac-btn mac-btn-ghost text-white/80 hover:text-white hover:bg-white/10"
              >
                Learn More
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── macOS-style Features ─────────────────────────────────── */}
      <section id="features" className="mx-auto max-w-7xl px-6 py-16">
        <Reveal className="mb-12 text-center">
          <h2 className="mb-2 text-2xl font-bold" style={{ color: "var(--mac-label)" }}>
            Built for Rigorous Research
          </h2>
          <p className="mx-auto max-w-2xl text-sm" style={{ color: "var(--mac-secondary-label)" }}>
            E.sapiens combines AI pipeline planning, container execution, and
            automatic documentation into a single academic IDE.
          </p>
        </Reveal>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <Reveal key={feature.title} delay={i * 80}>
              <div className="mac-card mac-card-interactive h-full p-4">
                <feature.icon className="mb-3 h-6 w-6" style={{ color: "var(--brand-gold)" }} />
                <h3 className="mb-1 text-sm font-semibold" style={{ color: "var(--mac-label)" }}>
                  {feature.title}
                </h3>
                <p className="text-xs leading-relaxed" style={{ color: "var(--mac-secondary-label)" }}>
                  {feature.description}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── macOS-style CTA ──────────────────────────────────────── */}
      <Reveal>
        <section className="py-16" style={{ background: "var(--mac-sidebar-bg)" }}>
          <div className="mx-auto max-w-3xl px-6 text-center">
            <h2 className="mb-2 text-2xl font-bold text-white">
              Ready to make your analyses reproducible?
            </h2>
            <p className="mb-6 text-sm" style={{ color: "rgba(255,255,255,0.6)" }}>
              Start a research session, let the AI plan your pipeline, and
              export publication-ready methods in minutes.
            </p>
            <Link
              href="/dashboard"
              className="mac-btn mac-btn-accent"
            >
              Launch E.sapiens
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </Reveal>

      {/* ── macOS-style Footer ────────────────────────────────────── */}
      <footer
        className="py-6 text-center text-xs border-t"
        style={{
          background: "var(--mac-toolbar-bg)",
          borderColor: "var(--mac-toolbar-separator)",
          color: "var(--mac-tertiary-label)",
        }}
      >
        © {new Date().getFullYear()} E.sapiens — Reproducible bioinformatics for academic research
      </footer>
    </div>
  );
}