import en from "../locales/en.json";
import zh from "../locales/zh.json";

// Locked decision 1: the UI is English; Chinese legal terms are kept with an
// English gloss. The zh bundle exists so the same keys can be switched later.
export type Locale = "en" | "zh";

const BUNDLES: Record<Locale, Record<string, string>> = { en, zh };

export const DEFAULT_LOCALE: Locale = "en";

export function t(key: string, locale: Locale = DEFAULT_LOCALE): string {
  return BUNDLES[locale][key] ?? BUNDLES.en[key] ?? key;
}

// Message params come from the API as a flat map. A placeholder with no value
// is left as written rather than rendered as "undefined": an unknown stays
// visibly unknown.
export function format(
  key: string,
  params: Record<string, unknown> = {},
  locale: Locale = DEFAULT_LOCALE
): string {
  return t(key, locale).replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole
  );
}
