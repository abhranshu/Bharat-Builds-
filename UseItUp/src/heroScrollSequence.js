import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

// Register the plugin globally
gsap.registerPlugin(ScrollTrigger);

// ============================================
// FRAME CONFIGURATION
// ============================================

const frameCount = 192;

const CLOUDFRONT_BASE =
  "https://d21m7w28iod98m.cloudfront.net/frames/v1";

const frameGroups = [
  { prefix: "c1",  count: 48 },
  { prefix: "c2",  count: 48 },
  { prefix: "c3a", count: 48 },
  { prefix: "c3b", count: 48 },
];

const images = [];
let loadedCount = 0;

const seq = {
  frame: 0,
};


// ============================================
// FRAME URL GENERATOR
// ============================================

function currentFrameURL(index) {

  let offset = index;

  for (const group of frameGroups) {

    if (offset < group.count) {
      const frameNumber =
        String(offset + 1).padStart(3, "0");
      return `${CLOUDFRONT_BASE}/${group.prefix}_${frameNumber}.jpg`;
    }

    offset -= group.count;
  }

  return null;
}


// ============================================
// DOM REFERENCES
// ============================================

let canvas, ctx;
let loader, loaderText, loaderBar;
let ctaOverlay;
let heroSection;
let heroLines = [];


// ============================================
// CANVAS RESIZE
// ============================================

function resizeCanvas() {
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;

  // Redraw current frame after resize
  if (images.length > 0 && images[seq.frame]) {
    render();
  }
}


// ============================================
// RENDER — cover-fit mathematics
// ============================================

function render() {

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const img = images[seq.frame];

  if (!img || !img.complete || !img.naturalWidth) {
    return;
  }

  const canvasRatio = canvas.width  / canvas.height;
  const imgRatio    = img.naturalWidth / img.naturalHeight;

  let drawWidth, drawHeight, offsetX, offsetY;

  if (imgRatio > canvasRatio) {
    // Image is wider than canvas — fit by height, crop sides
    drawHeight = canvas.height;
    drawWidth  = drawHeight * imgRatio;
    offsetX    = (canvas.width - drawWidth) / 2;
    offsetY    = 0;
  } else {
    // Image is taller than canvas — fit by width, crop top/bottom
    drawWidth  = canvas.width;
    drawHeight = drawWidth / imgRatio;
    offsetX    = 0;
    offsetY    = (canvas.height - drawHeight) / 2;
  }

  ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
}


// ============================================
// CTA VISIBILITY — driven by ScrollTrigger progress
// ============================================

function updateCTA(progress) {

  if (!ctaOverlay) return;

  if (progress >= 0.95) {
    ctaOverlay.classList.add("visible");
  } else {
    ctaOverlay.classList.remove("visible");
  }
}


// ============================================
// TEXT OVERLAY — fade lines based on scroll progress
// ============================================

function updateTextOverlay(progress) {

  const pct = progress * 100;

  for (const line of heroLines) {

    const show    = line.dataset.showFrom;
    const hide    = line.dataset.showUntil;
    const visible = pct >= show && pct <= hide;

    if (visible) {
      line.element.classList.add("active");
    } else {
      line.element.classList.remove("active");
    }
  }
}


// ============================================
// GSAP SCROLLTRIGGER SETUP
// ============================================

function initScrollAnimation() {

  gsap.to(seq, {

    frame: frameCount - 1,
    snap: "frame",
    ease: "none",

    scrollTrigger: {
      trigger: heroSection,
      start: "top top",
      end: "+=4000",
      scrub: 0.5,
      pin: true,
      onUpdate: (self) => {
        render();
        updateCTA(self.progress);
        updateTextOverlay(self.progress);
      },
    },
  });
}


// ============================================
// PRELOAD ALL IMAGES
// ============================================

function preloadImages(onComplete) {

  for (let i = 0; i < frameCount; i++) {

    const img = new Image();

    img.onload = () => {

      loadedCount++;

      const pct = Math.round((loadedCount / frameCount) * 100);

      if (loaderText) {
        loaderText.textContent = `Loading ${pct}%`;
      }
      if (loaderBar) {
        loaderBar.style.width = `${pct}%`;
      }

      if (loadedCount === frameCount) {
        onComplete();
      }
    };

    img.onerror = () => {
      console.error("Failed to load frame:", currentFrameURL(i));

      // Still count errored frames so loading finishes
      loadedCount++;
      if (loadedCount === frameCount) {
        onComplete();
      }
    };

    img.src = currentFrameURL(i);
    images[i] = img;
  }
}


// ============================================
// INIT — exported entry point
// ============================================

export function initHeroScrollSequence() {

  // Grab DOM elements
  canvas      = document.getElementById("hero-canvas");
  ctx         = canvas.getContext("2d");
  loader      = document.getElementById("loader");
  loaderText  = document.getElementById("loader-text");
  loaderBar   = document.getElementById("loader-bar");
  ctaOverlay  = document.getElementById("cta-overlay");
  heroSection = document.getElementById("hero-section");

  // Parse hero text lines from DOM
  heroLines = Array.from(
    document.querySelectorAll(".hero-line")
  ).map((el) => ({
    element: el,
    dataset: {
      showFrom: Number(el.dataset.showFrom),
      showUntil: Number(el.dataset.showUntil),
    },
  }));

  // Set canvas to full viewport resolution
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  // Start preloading
  preloadImages(() => {

    // Fade out loader
    if (loader) {
      loader.classList.add("hidden");
    }

    // Restore scrolling
    document.body.classList.remove("loading");

    // Render first frame
    render();

    // Initialize scroll animation only after all frames loaded
    initScrollAnimation();
  });
}
