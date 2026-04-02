import type { ReactNode } from "react";

export function SectionCard({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="section-card">
      {title ? <h3>{title}</h3> : null}
      {children}
    </section>
  );
}
