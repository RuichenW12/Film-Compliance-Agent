import { describe, expect, it } from "vitest";

import { latestAssetOfKind } from "@/lib/assets";


describe("latestAssetOfKind", () => {
  it("selects the latest asset of the requested kind", () => {
    expect(
      latestAssetOfKind(
        [
          { version_id: "script-1", kind: "script" },
          { version_id: "synopsis-1", kind: "synopsis" },
          { version_id: "script-2", kind: "script" },
        ],
        "synopsis",
      )?.version_id,
    ).toBe("synopsis-1");
  });

  it("returns undefined when no matching asset exists", () => {
    expect(
      latestAssetOfKind([{ version_id: "script-1", kind: "script" }], "synopsis"),
    ).toBeUndefined();
  });
});
