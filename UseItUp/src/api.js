/**
 * UseItUp API client.
 *
 * Thin wrapper over the serverless backend (API Gateway + Lambda).
 * Endpoints:
 *   POST /upload-url        -> presigned S3 PUT URL
 *   GET  /inventory         -> household ingredients
 *   POST /recipes/generate  -> AI recipes constrained to inventory
 *   POST /cooked            -> mark a recipe cooked, deduct inventory
 *   GET  /nutrition         -> daily macro summary
 *   PUT  /profile           -> household profile
 */

const STORAGE_KEYS = {
  apiBase: "useitup.apiBase",
  householdId: "useitup.householdId",
};

/** Vite injects VITE_API_BASE_URL at build time (see .env.example). */
const DEFAULT_API_BASE = (import.meta.env?.VITE_API_BASE_URL || "").trim();

export const DEFAULT_HOUSEHOLD_ID = "hh-demo";

export class ApiError extends Error {
  constructor(message, { status = 0, detail = "" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/* ============================================
   PERSISTED CONNECTION SETTINGS
   ============================================ */

function readStorage(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage may be unavailable (private mode) — ignore */
  }
}

export function getApiBase() {
  return (readStorage(STORAGE_KEYS.apiBase) || DEFAULT_API_BASE || "").replace(
    /\/+$/,
    ""
  );
}

export function setApiBase(value) {
  writeStorage(STORAGE_KEYS.apiBase, (value || "").trim().replace(/\/+$/, ""));
}

export function getHouseholdId() {
  return readStorage(STORAGE_KEYS.householdId) || DEFAULT_HOUSEHOLD_ID;
}

export function setHouseholdId(value) {
  writeStorage(STORAGE_KEYS.householdId, (value || "").trim());
}

/* ============================================
   CORE REQUEST HELPER
   ============================================ */

async function request(path, { method = "GET", body, timeoutMs = 60000 } = {}) {
  const base = getApiBase();

  if (!base) {
    throw new ApiError(
      "No API base URL configured. Paste your API Gateway endpoint above and press Save."
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(`${base}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    if (error.name === "AbortError") {
      throw new ApiError("The request timed out. Check the API URL and try again.");
    }
    throw new ApiError(
      "Could not reach the API. Confirm the URL is correct and CORS is enabled."
    );
  }
  clearTimeout(timer);

  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = { raw };
    }
  }

  if (!response.ok) {
    throw new ApiError(
      data?.error || `Request failed (HTTP ${response.status})`,
      { status: response.status, detail: data?.detail || "" }
    );
  }

  return data;
}

/* ============================================
   ENDPOINTS
   ============================================ */

/**
 * Get a presigned S3 PUT URL and the UPLOAD# tracking ID.
 * @param {"bill"|"fridge_photo"} uploadType
 */
export function requestUploadUrl(householdId, uploadType) {
  return request("/upload-url", {
    method: "POST",
    body: { household_id: householdId, upload_type: uploadType },
  });
}

/**
 * PUT the image bytes straight to S3 using the presigned URL.
 *
 * The URL is signed for `Content-Type: image/jpeg`, so that header must match
 * exactly or S3 rejects the upload with SignatureDoesNotMatch.
 */
export async function uploadImageToS3(uploadUrl, file) {
  let response;
  try {
    response = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": "image/jpeg" },
      body: file,
    });
  } catch {
    throw new ApiError(
      "Upload to S3 failed. The bucket needs a CORS rule allowing PUT from this origin."
    );
  }

  if (!response.ok) {
    throw new ApiError(`Upload to S3 failed (HTTP ${response.status}).`);
  }
  return true;
}

export function getInventory(householdId) {
  return request(`/inventory?household_id=${encodeURIComponent(householdId)}`);
}

export function generateRecipes({
  householdId,
  mealType = "lunch",
  prepTimePreference = 30,
}) {
  return request("/recipes/generate", {
    method: "POST",
    body: {
      household_id: householdId,
      meal_type: mealType,
      prep_time_preference: prepTimePreference,
    },
    timeoutMs: 90000, // Bedrock generation is slower than the other routes
  });
}

export function markCooked({ householdId, recipe, servingsCooked = 2 }) {
  return request("/cooked", {
    method: "POST",
    body: {
      household_id: householdId,
      recipe,
      servings_cooked: servingsCooked,
    },
  });
}

export function getNutritionSummary(householdId) {
  return request(`/nutrition?household_id=${encodeURIComponent(householdId)}`);
}

export function addInventoryItem(householdId, ingredientId, quantityG) {
  return request("/inventory", {
    method: "POST",
    body: {
      household_id: householdId,
      ingredient_id: ingredientId,
      quantity_g: quantityG,
    },
  });
}

export function updateProfile(householdId, fields) {
  return request("/profile", {
    method: "PUT",
    body: { household_id: householdId, ...fields },
  });
}
