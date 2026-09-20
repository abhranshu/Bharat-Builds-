import { initHeroScrollSequence } from "./heroScrollSequence.js";
import { initAppConsole } from "./app.js";
import "./app.css";
import "../style.css";

document.addEventListener("DOMContentLoaded", () => {
  // Landing page scroll-scrubbed hero (unchanged).
  initHeroScrollSequence();

  // Backend-connected app console below the landing page.
  initAppConsole();
});
