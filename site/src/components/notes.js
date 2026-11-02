// Explainer with margin notes (D33): a short description beside handwritten-style factoids, each
// tied to the text by a pencil-drawn arrow that draws itself in when the block scrolls into view.
// The notes sit in the empty right-hand gutter on wide screens and stack under the text on narrow
// ones (arrows hidden). No colours here: strokes use currentColor and the theme's muted text colour
// (style.css), so light and dark modes need nothing extra. Reduced motion skips the animation.

import {html, svg} from "npm:htl@0.3.1";

// Three hand-drawn arrows pointing left, from the note toward the text, so neighbours don't look
// stamped. Each is a wobbly shaft and a two-stroke head; viewBox 0 0 96 48.
const ARROWS = [
  {shaft: "M92 30 C 74 34, 56 12, 34 20 S 12 26, 6 22", head: ["M6 22 L 15 14", "M6 22 L 16 28"]},
  {shaft: "M92 14 C 70 8, 60 36, 38 30 S 14 22, 6 26", head: ["M6 26 L 14 18", "M6 26 L 15 33"]},
  {shaft: "M92 26 C 76 20, 58 28, 40 24 C 26 21, 16 25, 6 24", head: ["M6 24 L 14 16", "M6 24 L 14 31"]}
];

let filters = 0;

/** A pencil arrow: each path drawn twice (a firm line and a faint offset one) through a grain filter.
 *  Built with htl's svg template so the paths are SVG elements and keep `pathLength`'s case. */
function arrow(i, filterId) {
  const {shaft, head} = ARROWS[i % ARROWS.length];
  const strokes = (d, part) => svg.fragment`<path class=${`nrm-pencil-line ${part}`} d=${d} pathLength="1"
    filter=${`url(#${filterId})`}></path><path class=${`nrm-pencil-ghost ${part}`} d=${d} pathLength="1"
    transform="translate(0.7 0.9)"></path>`;
  return svg`<svg class="nrm-arrow" viewBox="0 0 96 48" aria-hidden="true">${strokes(shaft, "nrm-shaft")}${head.map((d) => strokes(d, "nrm-head"))}</svg>`;
}

/**
 * explainer({title, body, notes}): a titled description with margin notes.
 *   title   heading text
 *   body    an html fragment or string: the description (no digits in page prose; pass figures from JSON)
 *   notes   array of html fragments or strings: the factoids, three at most reads best
 */
export function explainer({title, body, notes = []}) {
  const filterId = `nrm-pencil-${++filters}`;
  const root = html`<section class="nrm-explainer-wrap">
    <svg width="0" height="0" style="position:absolute" aria-hidden="true"><filter id=${filterId}>
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed=${filters} result="grain"></feTurbulence>
      <feDisplacementMap in="SourceGraphic" in2="grain" scale="1.4"></feDisplacementMap>
    </filter></svg>
    <div class="nrm-explainer">
      <div class="nrm-explainer-body"><h2>${title}</h2>${body}</div>
      <ul class="nrm-margin-notes" aria-label="Good to know">
        ${notes.map((note, i) => html`<li class="nrm-margin-note" style=${`--i: ${i}`}>${arrow(i, filterId)}<span>${note}</span></li>`)}
      </ul>
    </div>
  </section>`;
  // Draw the arrows once the block is on screen (immediately where IntersectionObserver is missing).
  if (typeof IntersectionObserver === "undefined") root.classList.add("nrm-drawn");
  else {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        root.classList.add("nrm-drawn");
        observer.disconnect();
      }
    }, {threshold: 0.35});
    observer.observe(root);
  }
  return root;
}
