import Link from "next/link";
import { copy } from "../../lib/content/facts";

/** Splits a phrase into mask-reveal words with a staggered delay. */
function Reveal({ text, live, base = 0 }: { text: string; live?: boolean; base?: number }) {
  return (
    <>
      {text.split(" ").map((word, i) => (
        <span className="rvl" key={`${word}-${i}`}>
          <span
            className={live ? "live" : undefined}
            style={{ animationDelay: `${base + i * 0.08}s` }}
          >
            {word}
          </span>
          {i < text.split(" ").length - 1 ? " " : ""}
        </span>
      ))}
    </>
  );
}

export default function HeroCine() {
  return (
    <section className="hero-cine" id="top">
      <div className="hero-cine-inner">
        <h1>
          <Reveal text="Your codebase," base={0.15} />
          <br />
          <Reveal text="remembered." live base={0.35} />
        </h1>

        <p className="hero-support fade-seq" style={{ animationDelay: "0.6s" }}>
          {copy.support}
        </p>

        <div className="hero-cta fade-seq" style={{ animationDelay: "0.75s" }}>
          <Link className="btn-mag" href="/download" data-evt="download_click">
            Download Atlas <span className="arw" aria-hidden>→</span>
          </Link>
          <Link className="btn-line" href="/how-it-works">
            See how it works
          </Link>
        </div>

        <p className="hero-note fade-seq" style={{ animationDelay: "0.9s" }}>
          {copy.heroNote}
        </p>
      </div>

      <div className="hero-scroll" aria-hidden="true">
        <span className="line" />
        Scroll
      </div>
    </section>
  );
}
