// ============================================
// CANVAS SETUP
// ============================================

const canvas = document.getElementById("hero-canvas");
const ctx = canvas.getContext("2d");


// ============================================
// FRAME CONFIGURATION
// ============================================

const frameCount = 192;

const CLOUDFRONT_BASE =
  "https://d21m7w28iod98m.cloudfront.net/frames/v1";

const frameGroups = [
  { prefix: "c1", count: 48 },
  { prefix: "c2", count: 48 },
  { prefix: "c3a", count: 48 },
  { prefix: "c3b", count: 48 }
];

const images = [];
let loadedCount = 0;

const seq = {
  frame: 0
};


// ============================================
// CANVAS RESIZE
// ============================================

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  // Redraw current frame after resize
  if (images.length > 0 && images[seq.frame]) {
    render();
  }
}

window.addEventListener("resize", resizeCanvas);


// ============================================
// FRAME URL GENERATOR
// ============================================

function currentFrameURL(index) {

  let offset = index;

  for (const group of frameGroups) {

    if (offset < group.count) {

      const frameNumber = String(offset + 1).padStart(3, "0");

      return `${CLOUDFRONT_BASE}/${group.prefix}_${frameNumber}.jpg`;
    }

    offset -= group.count;
  }

  return null;
}


// ============================================
// PRELOAD ALL IMAGES
// ============================================

function preloadImages(onComplete) {

  for (let i = 0; i < frameCount; i++) {

    const img = new Image();

    img.onload = () => {

      loadedCount++;

      const pct = Math.round(
        (loadedCount / frameCount) * 100
      );

      const loaderText =
        document.getElementById("loader-text");

      if (loaderText) {
        loaderText.textContent = `Loading ${pct}%`;
      }

      if (loadedCount === frameCount) {

        if (onComplete) {
          onComplete();
        }
      }
    };

    img.onerror = () => {

      console.error(
        "Failed to load frame:",
        currentFrameURL(i)
      );

    };

    img.src = currentFrameURL(i);

    images[i] = img;
  }
}


// ============================================
// RENDER FRAME
// ============================================

function render() {

  ctx.clearRect(
    0,
    0,
    canvas.width,
    canvas.height
  );

  const img = images[seq.frame];

  if (
    !img ||
    !img.complete ||
    !img.naturalWidth
  ) {
    return;
  }

  const canvasRatio =
    canvas.width / canvas.height;

  const imgRatio =
    img.naturalWidth / img.naturalHeight;

  let drawWidth;
  let drawHeight;
  let offsetX;
  let offsetY;


  // ==========================================
  // COVER IMAGE
  // ==========================================

  if (imgRatio > canvasRatio) {

    // Image is wider than canvas

    drawHeight = canvas.height;

    drawWidth =
      drawHeight * imgRatio;

    offsetX =
      (canvas.width - drawWidth) / 2;

    offsetY = 0;

  } else {

    // Image is taller than canvas

    drawWidth = canvas.width;

    drawHeight =
      drawWidth / imgRatio;

    offsetX = 0;

    offsetY =
      (canvas.height - drawHeight) / 2;
  }


  // ==========================================
  // DRAW IMAGE
  // ==========================================

  ctx.drawImage(
    img,
    offsetX,
    offsetY,
    drawWidth,
    drawHeight
  );
}


// ============================================
// SCROLL ANIMATION
// ============================================

function initScrollAnimation() {

  // Register ScrollTrigger
  gsap.registerPlugin(ScrollTrigger);


  gsap.to(seq, {

    // Animate from frame 0 → frame 191
    frame: frameCount - 1,

    // Only show whole frames
    snap: "frame",

    // Linear frame progression
    ease: "none",

    scrollTrigger: {

      trigger: "#hero-section",

      start: "top top",

      // Scroll distance
      end: "+=4000",

      // Smooth scrubbing
      scrub: 0.5,

      // Pin hero section while scrolling
      pin: true
    },

    // Render whenever frame changes
    onUpdate: render
  });
}


// ============================================
// LOADING STATE
// ============================================

document.body.classList.add("loading");


// ============================================
// INITIALIZE
// ============================================

preloadImages(() => {

  const loader =
    document.getElementById("loader");

  if (loader) {
    loader.style.display = "none";
  }

  document.body.classList.remove("loading");


  // Set canvas size after images load
  resizeCanvas();


  // Show first frame
  render();


  // Start scroll animation
  initScrollAnimation();
});