import { describe, expect, it } from "vitest";
import { libellePays } from "./pays";

describe("libellePays", () => {
  it("traduit un code ISO et garde un nom déjà lisible", () => {
    expect(libellePays("MR")).toBe("Mauritanie");
    expect(libellePays("France")).toBe("France");
    expect(libellePays("")).toBe("—");
  });
});
