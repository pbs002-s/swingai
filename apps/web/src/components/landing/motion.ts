"use client";

import { useEffect } from "react";
import type { RefObject } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";

let registered = false;
function register() {
  if (registered) return;
  gsap.registerPlugin(ScrollTrigger, SplitText);
  registered = true;
}

const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Page motion, all inside `root`:
 *  [data-split]   headline words rise out of a mask once, on load
 *  [data-reveal]  fades up once when it scrolls into view (children stagger with [data-reveal="stagger"])
 *  [data-bar]     grows to its data-bar width (%) when in view
 *  [data-seam]    the stitch line scales with page scroll
 */
export function useLandingMotion(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!root.current || reduced()) return;
    register();
    const ctx = gsap.context(() => {
      document.fonts?.ready.then(() => {
        gsap.utils.toArray<HTMLElement>("[data-split]").forEach((el) => {
          const split = SplitText.create(el, { type: "words", mask: "words" });
          gsap.from(split.words, { yPercent: 110, duration: 1.1, ease: "expo.out", stagger: 0.06, delay: 0.1 });
        });
      });
      gsap.from("[data-hero-fade]", { y: 16, opacity: 0, duration: 1, ease: "expo.out", stagger: 0.08, delay: 0.45 });

      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((el) => {
        const targets = el.dataset.reveal === "stagger" ? Array.from(el.children) : [el];
        gsap.from(targets, {
          y: 24, opacity: 0, duration: 0.9, ease: "expo.out", stagger: 0.08,
          scrollTrigger: { trigger: el, start: "top 82%", once: true },
        });
      });

      gsap.utils.toArray<HTMLElement>("[data-bar]").forEach((el) => {
        gsap.fromTo(el, { width: "0%" }, {
          width: `${el.dataset.bar}%`, duration: 1.2, ease: "expo.out",
          scrollTrigger: { trigger: el, start: "top 90%", once: true },
        });
      });

      const seam = root.current?.querySelector<HTMLElement>("[data-seam]");
      if (seam) {
        gsap.fromTo(seam, { scaleY: 0 }, {
          scaleY: 1, ease: "none",
          scrollTrigger: { trigger: root.current, start: "top top", end: "bottom bottom", scrub: 0.4 },
        });
      }
    }, root);
    return () => ctx.revert();
  }, [root]);
}
