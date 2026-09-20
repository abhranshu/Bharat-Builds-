/**
 * UseItUp app console.
 *
 * Wires the buttons in <section id="app-console"> to the backend API.
 * This module is independent of the landing page scroll sequence — it never
 * touches the hero canvas, GSAP timeline, or loader.
 */

import {
  ApiError,
  addInventoryItem,
  deleteInventoryItem,
  getApiBase,
  getHouseholdId,
  getInventory,
  getNutritionSummary,
  generateRecipes,
  markCooked,
  requestUploadUrl,
  setApiBase,
  setHouseholdId,
  updateProfile,
  uploadImageToS3,
} from "./api.js";

/* ============================================
   SMALL DOM HELPERS
   ============================================ */

const $ = (id) => document.getElementById(id);

/** Create an element safely (textContent only — never innerHTML). */
function el(tag, { className, text, attrs, children } = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value !== undefined && value !== null) node.setAttribute(key, value);
    }
  }
  if (children) {
    for (const child of children) {
      if (child) node.appendChild(child);
    }
  }
  return node;
}

function clear(node) {
  if (node) node.replaceChildren();
}

function formatDate(iso) {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Days between today and an ISO date (negative = already expired). */
function daysUntil(iso) {
  if (!iso) return null;
  const target = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target - today) / 86400000);
}

function expiryBadge(iso) {
  const days = daysUntil(iso);
  if (days === null) return { label: "unknown", tone: "muted" };
  if (days < 0) return { label: `expired ${Math.abs(days)}d ago`, tone: "danger" };
  if (days === 0) return { label: "expires today", tone: "danger" };
  if (days <= 4) return { label: `${days}d left`, tone: "warn" };
  return { label: `${days}d left`, tone: "good" };
}

function num(value, digits = 1) {
  if (value === undefined || value === null || value === "") return "0";
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return "0";
  return parsed.toFixed(digits).replace(/\.0$/, "");
}

const state = {
  busy: false,
  inventory: null,
};

/* ============================================
   ACTIVITY LOG
   ============================================ */

function log(message, level = "info") {
  const output = $("console-log-output");
  if (!output) return;

  const line = el("div", {
    className: `log-line log-${level}`,
    children: [
      el("span", {
        className: "log-time",
        text: new Date().toLocaleTimeString(),
      }),
      el("span", { className: "log-msg", text: message }),
    ],
  });

  output.appendChild(line);
  output.scrollTop = output.scrollHeight;
}

/* ============================================
   BUTTON BUSY / STATUS
   ============================================ */

function setBusy(busy) {
  state.busy = busy;
  document.querySelectorAll("#app-console .btn").forEach((btn) => {
    btn.disabled = busy;
    btn.classList.toggle("is-busy", busy);
  });
}

function setStatus(message, tone) {
  const status = $("connection-status");
  if (!status) return;
  status.textContent = message || "";
  status.dataset.tone = tone || "";
}

function fail(error) {
  const detail =
    error instanceof ApiError && error.detail
      ? `${error.message} — ${error.detail}`
      : error?.message || String(error);
  setStatus(detail, "error");
  log(detail, "error");
}

/** Run an async action with shared busy/status handling. */
async function run(label, action) {
  if (state.busy) return undefined;
  setBusy(true);
  setStatus(`${label}…`, "busy");
  log(`${label}…`, "muted");
  try {
    const result = await action();
    setStatus("", "");
    return result;
  } catch (error) {
    fail(error);
    return undefined;
  } finally {
    setBusy(false);
  }
}

/* ============================================
   CONNECTION
   ============================================ */

function initConnection() {
  const householdInput = $("household-id");
  const apiInput = $("api-base");

  if (householdInput) householdInput.value = getHouseholdId();
  if (apiInput) apiInput.value = getApiBase();

  $("btn-save-connection")?.addEventListener("click", () => {
    const household = (householdInput?.value || "").trim();
    const base = (apiInput?.value || "").trim();

    if (!household) {
      fail(new ApiError("Household ID cannot be empty."));
      return;
    }
    if (!/^https?:\/\//i.test(base)) {
      fail(new ApiError("API base URL must start with http:// or https://"));
      return;
    }

    setHouseholdId(household);
    setApiBase(base);
    setStatus(`Saved. Using household “${household}”.`, "ok");
    log(`Connection saved → ${base} (household ${household})`, "ok");
    loadProfileIntoForm();
  });
}

/* ============================================
   UPLOAD (bill / fridge photo)
   ============================================ */

function initUpload() {
  const fileInput = $("file-input");
  const cameraInput = $("camera-input");
  if (!fileInput) return;

  let pendingType = null;

  const pick = (type) => {
    pendingType = type;
    fileInput.value = "";
    fileInput.click();
  };

  const handleFile = async (file, uploadType) => {
    if (!file) return;
    const label =
      uploadType === "bill" ? "Uploading grocery bill" : "Uploading fridge photo";

    const result = await run(label, async () => {
      const householdId = getHouseholdId();
      const { upload_url, image_id } = await requestUploadUrl(householdId, uploadType);
      await uploadImageToS3(upload_url, file);
      return { image_id, sizeKb: Math.round(file.size / 1024) };
    });

    if (result) {
      log(
        `Uploaded as ${result.image_id} (${result.sizeKb} KB). AI analysis started.`,
        "ok"
      );

      const initialCount = state.inventory?.items?.length ?? 0;
      let attempt = 0;
      const maxAttempts = 12;
      const pollIntervalMs = 3000;

      setStatus(
        `Analyzing ${uploadType === "bill" ? "grocery bill" : "fridge photo"} with AI (checking 1/${maxAttempts})…`,
        "busy"
      );

      const pollTimer = setInterval(async () => {
        attempt++;
        setStatus(
          `Analyzing ${uploadType === "bill" ? "grocery bill" : "fridge photo"} with AI (checking ${attempt}/${maxAttempts})…`,
          "busy"
        );

        try {
          const payload = await getInventory(getHouseholdId());
          const newCount = payload?.items?.length ?? 0;

          if (newCount > initialCount) {
            clearInterval(pollTimer);
            renderInventory(payload);
            const added = newCount - initialCount;
            setStatus(`Done! Extracted and added ${added} item(s).`, "ok");
            log(`Scan complete: ${added} ingredient(s) added to inventory.`, "ok");
            return;
          }

          if (attempt >= maxAttempts) {
            clearInterval(pollTimer);
            renderInventory(payload);
            setStatus("Scan completed.", "ok");
            log(
              "Finished scanning image. If expected items didn't appear, verify they match the 22 catalog or your Additional Valid Items list.",
              "muted"
            );
          }
        } catch {
          if (attempt >= maxAttempts) {
            clearInterval(pollTimer);
            setStatus("Image scan finished.", "");
          }
        }
      }, pollIntervalMs);
    }
  };

  // Camera button — opens device camera directly
  $("btn-camera")?.addEventListener("click", () => {
    pendingType = "fridge_photo";
    cameraInput.value = "";
    cameraInput.click();
  });

  if (cameraInput) {
    cameraInput.addEventListener("change", () => {
      const file = cameraInput.files?.[0];
      const type = pendingType || "fridge_photo";
      pendingType = null;
      handleFile(file, type);
    });
  }

  // Bill / Fridge Photo file picker buttons
  $("btn-upload-bill")?.addEventListener("click", () => pick("bill"));
  $("btn-upload-fridge")?.addEventListener("click", () => pick("fridge_photo"));

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    const type = pendingType;
    pendingType = null;
    handleFile(file, type);
  });
}

/* ============================================
   INVENTORY
   ============================================ */

async function removeInventoryItem(index) {
  if (state.busy) return;
  if (!state.inventory || !Array.isArray(state.inventory.items)) return;
  const removed = state.inventory.items[index];
  if (!removed) return;

  // Immediate UI update
  state.inventory.items.splice(index, 1);
  state.inventory.count = state.inventory.items.length;
  renderInventory(state.inventory);

  const itemName = removed.name || removed.ingredient_id;

  // If backend API is configured, delete permanently from DynamoDB
  if (getApiBase()) {
    try {
      await deleteInventoryItem(getHouseholdId(), {
        itemSk: removed.item_sk,
        ingredientId: removed.ingredient_id,
      });
      log(`Removed ${itemName} from inventory and database.`, "ok");
    } catch (error) {
      fail(error);
    }
  } else {
    log(`Removed ${itemName} from inventory.`, "ok");
  }
}

function renderInventory(payload) {
  if (payload) {
    state.inventory = {
      ...payload,
      items: Array.isArray(payload.items) ? [...payload.items] : [],
    };
  }

  const container = $("inventory-results");
  if (!container) return;
  clear(container);

  const items = state.inventory?.items || [];
  if (!items.length) {
    container.appendChild(
      el("p", {
        className: "console-empty",
        text: "No ingredients yet. Upload a grocery bill or a fridge photo to populate your inventory.",
      })
    );
    return;
  }

  container.appendChild(
    el("h4", { className: "result-title", text: `Inventory (${items.length})` })
  );

  const list = el("ul", { className: "inventory-list" });
  items.forEach((item, index) => {
    const badge = expiryBadge(item.predicted_expiry);

    const removeBtn = el("button", {
      className: "btn btn-tiny btn-remove-item",
      attrs: {
        type: "button",
        "aria-label": `Remove ${item.name || item.ingredient_id}`,
      },
      text: "Remove",
    });
    removeBtn.addEventListener("click", () => removeInventoryItem(index));

    list.appendChild(
      el("li", {
        className: "inventory-item",
        children: [
          el("div", {
            className: "inventory-main",
            children: [
              el("span", {
                className: "inventory-name",
                text: item.name || item.ingredient_id,
              }),
              el("span", {
                className: "inventory-qty",
                text: `${num(item.quantity_g, 0)} g`,
              }),
            ],
          }),
          el("div", {
            className: "inventory-meta",
            children: [
              el("span", { className: `chip chip-${badge.tone}`, text: badge.label }),
              el("span", {
                className: "inventory-date",
                text: `exp ${formatDate(item.predicted_expiry)}`,
              }),
              el("span", {
                className: "inventory-source",
                text: item.source === "fridge_photo" ? "photo" : "bill",
              }),
              removeBtn,
            ],
          }),
        ],
      })
    );
  });
  container.appendChild(list);
}

async function loadInventory({ silent = false } = {}) {
  if (silent) {
    try {
      const payload = await getInventory(getHouseholdId());
      renderInventory(payload);
      log(`Inventory refreshed (${payload?.count ?? 0} item(s)).`, "muted");
    } catch (error) {
      fail(error);
    }
    return undefined;
  }

  return run("Loading inventory", async () => {
    const payload = await getInventory(getHouseholdId());
    renderInventory(payload);
    log(`Loaded ${payload?.count ?? 0} inventory item(s).`, "ok");
    return payload;
  });
}

/* ============================================
   RECIPES
   ============================================ */

function nutritionBar(label, value, target, unit) {
  const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;

  const track = el("div", { className: "macro-track" });
  const fill = el("div", { className: "macro-fill" });
  fill.style.width = `${pct}%`;
  track.appendChild(fill);

  return el("div", {
    className: "macro",
    children: [
      el("div", {
        className: "macro-head",
        children: [
          el("span", { text: label }),
          el("span", { text: `${num(value)} ${unit}` }),
        ],
      }),
      track,
    ],
  });
}

function renderRecipe(recipe, index) {
  const card = el("article", { className: "recipe-card" });

  card.appendChild(
    el("div", {
      className: "recipe-head",
      children: [
        el("h4", {
          className: "recipe-name",
          text: recipe.name || `Recipe ${index + 1}`,
        }),
        el("span", {
          className: "recipe-time",
          text: `${recipe.prep_time_minutes ?? "—"} min`,
        }),
      ],
    })
  );

  if (recipe.reason) {
    card.appendChild(el("p", { className: "recipe-reason", text: recipe.reason }));
  }

  const nutrition = recipe.nutrition_per_serving || {};
  card.appendChild(
    el("div", {
      className: "recipe-nutrition",
      children: [
        el("span", {
          className: "nutrition-pill",
          text: `${num(nutrition.calories, 0)} kcal`,
        }),
        el("span", {
          className: "nutrition-pill",
          text: `${num(nutrition.protein)} g protein`,
        }),
        el("span", {
          className: "nutrition-pill",
          text: `${num(nutrition.carbs)} g carbs`,
        }),
        el("span", {
          className: "nutrition-pill",
          text: `${num(nutrition.fat)} g fat`,
        }),
        el("span", {
          className: "nutrition-pill muted",
          text: `${recipe.servings ?? 2} servings`,
        }),
      ],
    })
  );

  const ingredients = recipe.ingredients || [];
  if (ingredients.length) {
    const ingList = el("ul", { className: "recipe-ingredients" });
    for (const ing of ingredients) {
      ingList.appendChild(
        el("li", {
          text: `${ing.name || ing.ingredient_id} — ${num(ing.grams, 0)} g`,
        })
      );
    }
    card.appendChild(
      el("details", {
        className: "recipe-details",
        attrs: { open: "" },
        children: [
          el("summary", { text: `Ingredients (${ingredients.length})` }),
          ingList,
        ],
      })
    );
  }

  const steps = recipe.steps || [];
  if (steps.length) {
    const stepList = el("ol", { className: "recipe-steps" });
    for (const step of steps) stepList.appendChild(el("li", { text: step }));
    card.appendChild(
      el("details", {
        className: "recipe-details",
        children: [
          el("summary", { text: `Method (${steps.length} steps)` }),
          stepList,
        ],
      })
    );
  }

  const servingsInput = el("input", {
    className: "recipe-servings",
    attrs: {
      type: "number",
      min: "1",
      max: "20",
      value: String(recipe.servings ?? 2),
      "aria-label": "Servings cooked",
    },
  });

  const cookBtn = el("button", {
    className: "btn btn-primary btn-small",
    text: "Mark as Cooked",
  });

  cookBtn.addEventListener("click", () =>
    run(`Marking “${recipe.name}” as cooked`, async () => {
      const servingsCooked = Math.max(
        1,
        Math.min(20, Number(servingsInput.value) || recipe.servings || 2)
      );

      // Send only the fields the backend Recipe model expects.
      const payloadRecipe = {
        name: recipe.name,
        ingredients: (recipe.ingredients || []).map((ing) => ({
          ingredient_id: ing.ingredient_id,
          name: ing.name || ing.ingredient_id,
          grams: Number(ing.grams) || 0,
        })),
        steps: recipe.steps || [],
        prep_time_minutes: recipe.prep_time_minutes ?? 30,
        servings: recipe.servings ?? 2,
      };

      const result = await markCooked({
        householdId: getHouseholdId(),
        recipe: payloadRecipe,
        servingsCooked,
      });

      log(result?.message || "Marked as cooked.", "ok");
      if (result?.daily_nutrition) {
        log(
          `Today so far: ${num(result.daily_nutrition.calories, 0)} kcal, ` +
            `${num(result.daily_nutrition.protein)} g protein.`,
          "muted"
        );
      }
      loadInventory({ silent: true });
      return result;
    })
  );

  card.appendChild(
    el("div", {
      className: "recipe-actions",
      children: [
        el("label", {
          className: "recipe-servings-label",
          children: [el("span", { text: "Servings" }), servingsInput],
        }),
        cookBtn,
      ],
    })
  );

  return card;
}

function renderRecipes(payload) {
  const container = $("recipes-results");
  if (!container) return;
  clear(container);

  const recipes = payload?.recipes || [];
  if (!recipes.length) {
    container.appendChild(
      el("p", {
        className: "console-empty",
        text:
          payload?.message ||
          "No recipes returned. Add ingredients first, then generate again.",
      })
    );
    return;
  }

  container.appendChild(
    el("h4", {
      className: "result-title",
      text: `Suggested recipes (${recipes.length})`,
    })
  );

  const grid = el("div", { className: "recipe-grid" });
  recipes.forEach((recipe, index) => grid.appendChild(renderRecipe(recipe, index)));
  container.appendChild(grid);

  const gap = payload?.nutrition_gap;
  if (gap) {
    container.appendChild(
      el("p", {
        className: "console-hint",
        text: `Still to eat today: ~${num(gap.calories, 0)} kcal and ${num(gap.protein)} g protein.`,
      })
    );
  }
}

function initRecipes() {
  $("btn-regenerate")?.addEventListener("click", () =>
    run("Generating recipes", async () => {
      const mealType = $("meal-type")?.value || "lunch";
      const prep = Number($("prep-time")?.value) || 30;

      const payload = await generateRecipes({
        householdId: getHouseholdId(),
        mealType,
        prepTimePreference: prep,
      });

      renderRecipes(payload);
      log(
        `Generated ${payload?.recipes?.length ?? 0} recipe(s) for ${mealType} (≤${prep} min).`,
        "ok"
      );
      return payload;
    })
  );
}

/* ============================================
   NUTRITION
   ============================================ */

function renderNutrition(payload) {
  const container = $("nutrition-results");
  if (!container) return;
  clear(container);
  if (!payload) return;

  container.appendChild(
    el("h4", {
      className: "result-title",
      text: `Nutrition — ${formatDate(payload.date)}`,
    })
  );

  const consumed = payload.consumed || {};
  const targets = payload.targets || {};

  container.appendChild(
    el("div", {
      className: "nutrition-box",
      children: [
        nutritionBar("Calories", Number(consumed.calories), Number(targets.calories), "kcal"),
        nutritionBar("Protein", Number(consumed.protein), Number(targets.protein), "g"),
        nutritionBar("Carbs", Number(consumed.carbs), Number(targets.carbs), "g"),
        nutritionBar("Fat", Number(consumed.fat), Number(targets.fat), "g"),
        nutritionBar("Fiber", Number(consumed.fiber), Number(targets.fiber), "g"),
      ],
    })
  );
}

function initNutrition() {
  $("btn-nutrition")?.addEventListener("click", () =>
    run("Loading nutrition summary", async () => {
      const payload = await getNutritionSummary(getHouseholdId());
      renderNutrition(payload);
      log(`Nutrition summary loaded for ${payload?.date}.`, "ok");
      return payload;
    })
  );
}

/* ============================================
   PROFILE
   ============================================ */

async function loadProfileIntoForm() {
  // There is no GET /profile route — the nutrition summary exposes the targets.
  try {
    const payload = await getNutritionSummary(getHouseholdId());
    const targets = payload?.targets || {};
    if ($("profile-calories") && !$("profile-calories").value) {
      $("profile-calories").value = num(targets.calories, 0);
    }
    if ($("profile-protein") && !$("profile-protein").value) {
      $("profile-protein").value = num(targets.protein, 0);
    }
  } catch {
    // Non-fatal — the user can still enter values manually.
  }
}

function initProfile() {
  $("btn-save-profile")?.addEventListener("click", () =>
    run("Saving profile", async () => {
      const fields = {};

      const diet = $("profile-diet")?.value;
      if (diet) fields.diet_type = diet;

      const size = Number($("profile-size")?.value);
      if (size >= 1 && size <= 20) fields.household_size = size;

      const calories = Number($("profile-calories")?.value);
      if (calories >= 500) fields.daily_calorie_target = calories;

      const protein = Number($("profile-protein")?.value);
      if (protein >= 10) fields.daily_protein_target = protein;

      if (!Object.keys(fields).length) {
        throw new ApiError("Fill in at least one profile field.");
      }

      const result = await updateProfile(getHouseholdId(), fields);
      log(result?.message || "Profile updated.", "ok");
      return result;
    })
  );
}

/* ============================================
   INIT
   ============================================ */

/* ============================================
   MANUAL INGREDIENT ENTRY
   ============================================ */

// Ingredient catalog — IDs and display names
const INGREDIENT_CATALOG = [
  ["tomato", "Tomato"],
  ["onion", "Onion"],
  ["potato", "Potato"],
  ["rice", "Rice"],
  ["wheat_flour", "Wheat Flour"],
  ["milk", "Milk"],
  ["curd", "Curd"],
  ["paneer", "Paneer"],
  ["ghee", "Ghee"],
  ["moong_dal", "Moong Dal"],
  ["toor_dal", "Toor Dal"],
  ["chicken_breast", "Chicken Breast"],
  ["egg", "Egg"],
  ["coriander", "Coriander"],
  ["green_chilli", "Green Chilli"],
  ["ginger", "Ginger"],
  ["garlic", "Garlic"],
  ["turmeric", "Turmeric"],
  ["oil", "Cooking Oil"],
  ["sugar", "Sugar"],
  ["salt", "Salt"],
  ["banana", "Banana"],
];

function getCustomValidItems() {
  try {
    const raw = localStorage.getItem(`useitup.custom_valid_items.${getHouseholdId()}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveCustomValidItems(items) {
  try {
    localStorage.setItem(
      `useitup.custom_valid_items.${getHouseholdId()}`,
      JSON.stringify(items)
    );
  } catch {}
}

function populateIngredientDropdown() {
  const select = $("manual-ingredient");
  if (!select) return;

  clear(select);
  select.appendChild(el("option", { text: "— pick one —", attrs: { value: "" } }));

  for (const [id, name] of INGREDIENT_CATALOG) {
    select.appendChild(el("option", { text: name, attrs: { value: id } }));
  }

  const custom = getCustomValidItems();
  if (custom.length) {
    const group = el("optgroup", { attrs: { label: "Custom Valid Items" } });
    for (const item of custom) {
      const id = item.toLowerCase().replace(/[\s-]+/g, "_");
      group.appendChild(
        el("option", {
          text: item.charAt(0).toUpperCase() + item.slice(1),
          attrs: { value: id },
        })
      );
    }
    select.appendChild(group);
  }

  select.appendChild(
    el("option", { text: "— write custom item —", attrs: { value: "__custom__" } })
  );
}

function initValidItems() {
  const input = $("additional-valid-items");
  const saveBtn = $("btn-save-valid-items");
  const statusHint = $("valid-items-status");
  if (!input) return;

  const current = getCustomValidItems();
  if (current.length) {
    input.value = current.join(", ");
  }

  saveBtn?.addEventListener("click", async () => {
    const raw = input.value || "";
    const items = raw
      .split(/[,;\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    saveCustomValidItems(items);

    if (statusHint) {
      statusHint.textContent = `Saved ${items.length} custom valid item(s): ${items.join(", ")}`;
      statusHint.style.color = "#4ade80";
    }

    log(`Saved ${items.length} additional valid item(s).`, "ok");

    if (getApiBase()) {
      try {
        await updateProfile(getHouseholdId(), {
          additional_valid_ingredients: items,
        });
        log("Synced additional valid items with cloud profile.", "ok");
      } catch (err) {
        log(`Note: Saved locally. (${err.message})`, "muted");
      }
    }

    populateIngredientDropdown();
  });
}

function initManualIngredient() {
  const select = $("manual-ingredient");
  const customField = $("custom-ingredient-field");
  const customInput = $("manual-custom-name");
  if (!select) return;

  populateIngredientDropdown();

  select.addEventListener("change", () => {
    if (customField) {
      customField.style.display = select.value === "__custom__" ? "flex" : "none";
    }
  });

  $("btn-add-ingredient")?.addEventListener("click", async () => {
    let ingredientId = select.value;
    let displayName = "";

    if (ingredientId === "__custom__") {
      const customVal = customInput?.value?.trim() || "";
      if (!customVal) {
        const statusEl = $("manual-status");
        if (statusEl) {
          statusEl.textContent = "Enter a custom ingredient name.";
          statusEl.dataset.tone = "error";
        }
        return;
      }
      ingredientId = customVal.toLowerCase().replace(/[\s-]+/g, "_");
      displayName = customVal;

      const current = getCustomValidItems();
      if (!current.some((c) => c.toLowerCase() === customVal.toLowerCase())) {
        current.push(customVal);
        saveCustomValidItems(current);
        if ($("additional-valid-items")) {
          $("additional-valid-items").value = current.join(", ");
        }
        if (getApiBase()) {
          updateProfile(getHouseholdId(), {
            additional_valid_ingredients: current,
          }).catch(() => {});
        }
        populateIngredientDropdown();
      }
    } else {
      displayName = select.options[select.selectedIndex]?.text || ingredientId;
    }

    const quantity = Number($("manual-quantity")?.value);
    const statusEl = $("manual-status");

    if (!ingredientId) {
      if (statusEl) {
        statusEl.textContent = "Pick an ingredient.";
        statusEl.dataset.tone = "error";
      }
      return;
    }
    if (!quantity || quantity <= 0) {
      if (statusEl) {
        statusEl.textContent = "Enter a valid quantity.";
        statusEl.dataset.tone = "error";
      }
      return;
    }

    await run(`Adding ${displayName}`, async () => {
      const result = await addInventoryItem(getHouseholdId(), ingredientId, quantity);
      log(result?.message || `Added ${displayName} (${quantity}g).`, "ok");
      if (statusEl) {
        statusEl.textContent = "Added!";
        statusEl.dataset.tone = "ok";
      }
      loadInventory({ silent: true });
      return result;
    });
  });
}

function revealConnectionPanel() {
  const panel = $("connection-panel");
  if (!panel) return;
  panel.classList.add("is-visible");
}

export function initAppConsole() {
  const section = $("app-console");
  if (!section) return; // section not present — nothing to wire

  // Reveal the Connection panel only when ?debug is in the URL or Ctrl+Shift+D is pressed.
  if (window.location.search.includes("debug")) {
    revealConnectionPanel();
  }
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === "D") {
      e.preventDefault();
      revealConnectionPanel();
    }
  });

  initConnection();
  initUpload();
  initValidItems();
  initManualIngredient();
  initRecipes();
  initNutrition();
  initProfile();

  $("btn-inventory")?.addEventListener("click", () => loadInventory());
  $("btn-clear-log")?.addEventListener("click", () =>
    clear($("console-log-output"))
  );

  log("Console ready.", "ok");
  if (!getApiBase()) {
    log(
      "No API URL set. Deploy the backend, then paste the API endpoint above.",
      "muted"
    );
  }

  loadProfileIntoForm();
}
