export const DEFAULT_PREFERENCES = {
  theme: "LIGHT",
  font_scale: "NORMAL",
  reduced_motion: false,
  enhanced_focus: true,
};

const STORAGE_KEY = "fp_accessibility_preferences";
const THEMES = new Set(["LIGHT", "DARK", "HIGH_CONTRAST"]);
const FONT_SCALES = new Set(["NORMAL", "LARGE", "EXTRA_LARGE"]);

export function normalizePreferences(source = {}) {
  const theme = String(source.theme || DEFAULT_PREFERENCES.theme).toUpperCase();
  const fontScale = String(source.font_scale || DEFAULT_PREFERENCES.font_scale).toUpperCase();
  return {
    theme: THEMES.has(theme) ? theme : DEFAULT_PREFERENCES.theme,
    font_scale: FONT_SCALES.has(fontScale) ? fontScale : DEFAULT_PREFERENCES.font_scale,
    reduced_motion: Boolean(source.reduced_motion),
    enhanced_focus: source.enhanced_focus !== false,
  };
}

export function loadStoredPreferences() {
  try {
    return normalizePreferences(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function storePreferences(source) {
  const preferences = normalizePreferences(source);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // A interface continua funcionando mesmo quando o armazenamento está indisponível.
  }
  return preferences;
}

export function applyPreferences(source) {
  const preferences = normalizePreferences(source);
  const root = document.documentElement;
  root.dataset.theme = {
    LIGHT: "light",
    DARK: "dark",
    HIGH_CONTRAST: "contrast",
  }[preferences.theme];
  root.dataset.fontScale = preferences.font_scale.toLowerCase().replaceAll("_", "-");
  root.dataset.reducedMotion = String(preferences.reduced_motion);
  root.dataset.enhancedFocus = String(preferences.enhanced_focus);
  root.style.colorScheme = preferences.theme === "LIGHT" ? "light" : "dark";
  return preferences;
}

export function applyAndStorePreferences(source) {
  const preferences = storePreferences(source);
  applyPreferences(preferences);
  return preferences;
}
