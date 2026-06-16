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
    <div className="min-h-screen bg-cream">
      {/* ── Navigation ──────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-border glass-heavy" style={{ borderRadius: 0 }}>
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-7 w-7 text-gold" />
            <span className="text-xl font-bold text-navy">
              E.sapiens
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="btn-primary inline-flex items-center gap-2 text-sm"
            >
              Open Dashboard
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden glass-navy-heavy py-24 text-white">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute left-1/4 top-1/4 h-96 w-96 rounded-full bg-gold blur-3xl" />
          <div className="absolute right-1/4 bottom-1/4 h-64 w-64 rounded-full bg-blue-500 blur-3xl" />
        </div>
        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-gold/30 glass-navy px-4 py-1.5 text-sm text-gold">
            <FlaskConical className="h-4 w-4" />
            Academic Bioinformatics IDE
          </div>
          <h1 className="mb-6 text-5xl font-bold leading-tight tracking-tight">
            Reproducible Pipelines,{" "}
            <span className="text-gold">Publication-Ready</span> Results
          </h1>
          <p className="mx-auto mb-10 max-w-2xl text-lg text-navy-200">
            Plan, execute, and document bioinformatics analyses with
            AI-assisted pipeline design. Every container is pinned to an
            immutable SHA256 digest — because science must be reproducible.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/dashboard"
              className="btn-accent inline-flex items-center gap-2 text-base"
            >
              Get Started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="#features"
              className="btn-ghost inline-flex items-center gap-2 text-base text-white hover:bg-navy-700"
            >
              Learn More
            </Link>
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────── */}
      <section id="features" className="mx-auto max-w-7xl px-6 py-24">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-3xl font-bold text-navy">
            Built for Rigorous Research
          </h2>
          <p className="mx-auto max-w-2xl text-muted-foreground">
            E.sapiens combines AI pipeline planning, container execution, and
            automatic documentation into a single academic IDE.
          </p>
        </div>
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="glass group p-6 rounded-xl transition-all hover:shadow-lg hover:-translate-y-0.5"
            >
              <feature.icon className="mb-4 h-8 w-8 text-gold" />
              <h3 className="mb-2 text-lg font-semibold text-navy">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────── */}
      <section className="border-t border-border glass-navy-heavy py-20 text-white">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="mb-4 text-3xl font-bold">
            Ready to make your analyses reproducible?
          </h2>
          <p className="mb-8 text-navy-200">
            Start a research session, let the AI plan your pipeline, and
            export publication-ready methods in minutes.
          </p>
          <Link
            href="/dashboard"
            className="btn-accent inline-flex items-center gap-2 text-lg"
          >
            Launch E.sapiens
            <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer className="border-t border-border glass-heavy py-8">
        <div className="mx-auto max-w-7xl px-6 text-center text-sm text-muted-foreground">
          © {new Date().getFullYear()} E.sapiens — Reproducible
          bioinformatics for academic research
        </div>
      </footer>
    </div>
  );
}