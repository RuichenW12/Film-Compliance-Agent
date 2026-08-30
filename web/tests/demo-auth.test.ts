import { describe, expect, it } from "vitest";

import {
  DEFAULT_ROLE,
  DEFAULT_USER_ID,
  getRole,
  getUserId,
  setRole,
  setUserId,
} from "@/lib/demoAuth";


describe("demo auth without browser storage", () => {
  it("falls back without throwing when localStorage is unavailable", () => {
    const original = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: undefined,
    });

    try {
      expect(getRole()).toBe(DEFAULT_ROLE);
      expect(getUserId()).toBe(DEFAULT_USER_ID);
      expect(() => setRole("admin")).not.toThrow();
      expect(() => setUserId("u_other")).not.toThrow();
    } finally {
      if (original) {
        Object.defineProperty(window, "localStorage", original);
      } else {
        Reflect.deleteProperty(window, "localStorage");
      }
    }
  });
});
