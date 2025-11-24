let form;
let saveButton;
let statusEl;
let messageEl;
const fields = new Map();
let snapshot = null;
let initialValues = new Map();
let dirty = new Set();

function registerFields() {
  document.querySelectorAll("[data-field]").forEach((wrapper) => {
    const key = wrapper.dataset.field;
    const type = wrapper.dataset.type || "text";
    let control;
    if (type === "radio") {
      control = Array.from(wrapper.querySelectorAll(`input[name="${key}"]`));
    } else if (type === "boolean") {
      control = wrapper.querySelector("input[type=checkbox]");
    } else {
      control = wrapper.querySelector("input, textarea, select");
    }
    fields.set(key, {
      key,
      wrapper,
      control,
      type,
      target: wrapper.dataset.target || "env",
      sensitive: wrapper.dataset.sensitive === "true",
    });
  });
}

function init() {
  form = document.getElementById("config-form");
  saveButton = document.getElementById("save-button");
  statusEl = document.getElementById("status");
  messageEl = document.getElementById("message");
  if (!form || !saveButton || !statusEl || !messageEl) {
    throw new Error("Config UI failed to load required elements");
  }
  registerFields();
  form.addEventListener("input", handleFieldChange);
  form.addEventListener("change", handleFieldChange);
  saveButton.addEventListener("click", handleSave);
  loadSnapshot();
}

function loadSnapshot() {
  setStatus("Loading…");
  fetch("/api/config")
    .then((response) => {
      if (!response.ok) {
        throw new Error("Unable to load config");
      }
      return response.json();
    })
    .then((data) => {
      snapshot = data;
      applyValues();
      setMessage("");
    })
    .catch((error) => {
      setMessage(error.message, true);
      setStatus("Load failed");
    });
}

function applyValues() {
  if (!snapshot) {
    return;
  }
  initialValues = new Map();
  dirty = new Set();
  fields.forEach((field) => {
    const value = snapshot.values ? snapshot.values[field.key] : undefined;
    const fallback = snapshot.defaults ? snapshot.defaults[field.key] : undefined;
    if (field.sensitive) {
      setControlValue(field, "");
      const note = field.wrapper.querySelector("[data-secret-note]");
      if (note) {
        const detail = snapshot.secrets?.[field.key];
        if (detail?.present) {
          note.textContent = `Stored (${detail.preview})`;
        } else {
          note.textContent = "No value saved";
        }
      }
      initialValues.set(field.key, "");
      return;
    }
    const displayValue = resolveDisplayValue(field, value, fallback);
    setControlValue(field, displayValue);
    initialValues.set(field.key, normalizeForComparison(field, displayValue));
  });
  updateDirtyState();
}

function resolveDisplayValue(field, value, fallback) {
  if (field.target === "cli") {
    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
    if (fallback !== undefined) {
      return fallback;
    }
    if (field.type === "boolean") {
      return false;
    }
    if (field.type === "radio") {
      return "";
    }
    return "";
  }
  if (value !== undefined && value !== "") {
    return value;
  }
  if (fallback !== undefined) {
    return fallback;
  }
  return "";
}

function setControlValue(field, value) {
  if (field.type === "radio") {
    const raw = value == null ? "" : String(value);
    field.control.forEach((input) => {
      input.checked = input.value === raw;
    });
    return;
  }
  if (field.type === "boolean") {
    field.control.checked = Boolean(value);
    return;
  }
  if (field.control) {
    field.control.value = value == null ? "" : String(value);
  }
}

function readControlValue(field) {
  if (field.type === "radio") {
    const checked = field.control.find((input) => input.checked);
    return checked ? checked.value : "";
  }
  if (field.type === "boolean") {
    return field.control.checked;
  }
  return field.control ? field.control.value : "";
}

function normalizeForComparison(field, value) {
  if (field.target === "cli") {
    if (field.type === "boolean") {
      return Boolean(value);
    }
    if (field.type === "radio") {
      return value || null;
    }
    if (field.control && field.control.type === "number") {
      if (value === "" || value === null || value === undefined) {
        return null;
      }
      const num = Number(value);
      return Number.isFinite(num) ? num : null;
    }
    return value === "" ? null : value;
  }
  return value == null ? "" : String(value);
}

function handleFieldChange(event) {
  const wrapper = event.target.closest("[data-field]");
  if (!wrapper) {
    return;
  }
  const key = wrapper.dataset.field;
  const field = fields.get(key);
  if (!field) {
    return;
  }

  // Clear any existing error for this field when user starts editing
  clearFieldError(key);
  if (field.sensitive) {
    const current = readControlValue(field);
    if (current) {
      dirty.add(key);
    } else {
      dirty.delete(key);
    }
  } else {
    const current = normalizeForComparison(field, readControlValue(field));
    const baseline = initialValues.get(key);
    if (isEqual(current, baseline)) {
      dirty.delete(key);
    } else {
      dirty.add(key);
    }
  }
  updateDirtyState();
}

function isEqual(a, b) {
  if (typeof a === "number" && typeof b === "number") {
    return Number.isNaN(a) && Number.isNaN(b) ? true : a === b;
  }
  return a === b;
}

function updateDirtyState() {
  if (!snapshot) {
    saveButton.disabled = true;
    setStatus("Loading…");
    return;
  }
  if (dirty.size === 0) {
    saveButton.disabled = true;
    setStatus("Up to date");
  } else {
    saveButton.disabled = false;
    setStatus(`${dirty.size} pending ${dirty.size === 1 ? "change" : "changes"}`);
  }
}

function setStatus(text) {
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function setMessage(text, isError = false) {
  if (!messageEl) {
    return;
  }
  messageEl.textContent = text;
  messageEl.style.color = isError ? "#b91c1c" : "#0f172a";
}

function showFieldError(fieldKey, message) {
  const field = fields.get(fieldKey);
  if (!field) {
    return;
  }
  field.wrapper.classList.add("error");

  // Get the field label for better error messages
  const labelEl = field.wrapper.querySelector("label");
  const fieldName = labelEl ? labelEl.textContent.trim() : fieldKey;

  // Find or create error message element
  let errorEl = field.wrapper.querySelector(".error-message");
  if (!errorEl) {
    errorEl = document.createElement("div");
    errorEl.className = "error-message";
    field.wrapper.appendChild(errorEl);
  }

  // Make the error message more visible and informative
  const isRequiredError = message.toLowerCase().includes("required") || message.toLowerCase().includes("field required");
  if (isRequiredError) {
    errorEl.textContent = `${fieldName} is required`;
  } else {
    errorEl.textContent = `${fieldName}: ${message}`;
  }
}

function clearFieldError(fieldKey) {
  const field = fields.get(fieldKey);
  if (!field) {
    return;
  }
  field.wrapper.classList.remove("error");
  const errorEl = field.wrapper.querySelector(".error-message");
  if (errorEl) {
    errorEl.remove();
  }
}

function clearAllFieldErrors() {
  fields.forEach((field, key) => {
    clearFieldError(key);
  });
}

function collectChanges() {
  const payload = {};
  dirty.forEach((key) => {
    const field = fields.get(key);
    if (!field) {
      return;
    }
    const raw = readControlValue(field);
    if (field.sensitive && !raw) {
      return;
    }
    payload[key] = serializeValue(field, raw);
  });
  return payload;
}

function serializeValue(field, raw) {
  if (field.target === "cli") {
    if (field.type === "boolean") {
      return Boolean(raw);
    }
    if (field.type === "radio") {
      return raw || null;
    }
    if (field.control && field.control.type === "number") {
      if (raw === "" || raw === null) {
        return null;
      }
      const num = Number(raw);
      return Number.isFinite(num) ? num : null;
    }
    return raw === "" ? null : raw;
  }
  return raw == null ? "" : String(raw);
}

function handleSave() {
  if (!snapshot) {
    return;
  }
  const updates = collectChanges();
  if (Object.keys(updates).length === 0) {
    setMessage("No changes to save", true);
    return;
  }
  const versions = snapshot.versions || {};
  const payload = {
    values: updates,
    versions: {
      env: versions.env?.digest || null,
      overrides: versions.overrides?.digest || null,
    },
  };
  saveButton.disabled = true;
  setStatus("Saving…");
  fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
    .then(({ ok, body }) => {
      if (!ok) {
        clearAllFieldErrors();
        if (body.detail && body.detail.errors) {
          // Show field-specific errors
          body.detail.errors.forEach(error => {
            if (error.field) {
              showFieldError(error.field, error.message);
            }
          });
          // Show the first error message in the general message area
          const first = body.detail.errors[0];
          setMessage(first.message || "Validation failed", true);
        } else {
          setMessage(body.detail?.message || "Save failed", true);
        }
        updateDirtyState();
        return;
      }
      clearAllFieldErrors();
      snapshot = body;
      applyValues();
      setMessage("Changes saved");
    })
    .catch((error) => {
      setMessage(error.message || "Save failed", true);
    });
}

init();
