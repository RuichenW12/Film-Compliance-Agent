"use client";

import { useState } from "react";

import { t } from "@/lib/i18n";

/** Common starting points, not a controlled vocabulary.
 *
 *  These are conveniences for someone facing an empty box, and nothing in the
 *  chain treats a suggested word differently from a typed one — the subject
 *  check reads whatever text is there and has to quote it either way. So the
 *  list can be wrong or incomplete without making an answer wrong. */
const SUGGESTED = [
  "都市",
  "甜宠",
  "古装",
  "悬疑",
  "家庭",
  "科幻",
  "职场",
  "校园",
  "重生",
  "复仇",
  "喜剧",
  "年代",
];

/**
 * Genre keywords: pick from a few, type anything, or both.
 *
 * A free-text box asks a first-time creator to guess the house vocabulary. A
 * fixed list tells them their story is not on it. This does neither: the chips
 * are a starting point and the box stays open.
 */
export function GenrePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);

  const chosen = value
    .split(",")
    .map((word) => word.trim())
    .filter(Boolean);

  function toggle(word: string) {
    const next = chosen.includes(word)
      ? chosen.filter((existing) => existing !== word)
      : [...chosen, word];
    onChange(next.join(","));
  }

  return (
    <span className="genre-picker">
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onFocus={() => setOpen(true)}
        placeholder={t("wizard.genre_keywords.placeholder")}
        size={40}
      />
      <button
        type="button"
        className="genre-toggle"
        aria-expanded={open}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        {open ? t("genre.hide") : t("genre.suggest")}
      </button>

      {open ? (
        <span className="genre-chips">
          {SUGGESTED.map((word) => (
            <button
              type="button"
              key={word}
              className={chosen.includes(word) ? "chip chip-on" : "chip"}
              aria-pressed={chosen.includes(word)}
              onClick={() => toggle(word)}
            >
              {word}
            </button>
          ))}
        </span>
      ) : null}
    </span>
  );
}
