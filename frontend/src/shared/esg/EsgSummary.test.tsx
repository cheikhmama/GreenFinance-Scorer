import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreSummary } from "./EsgSummary";

const score = {
  global_score: 66.4,
  environmental_score: 50,
  social_score: 86,
  governance_score: 80,
  config_version: 2,
};

describe("ScoreSummary", () => {
  it("affiche la couverture à côté du score global", () => {
    render(<ScoreSummary score={{ ...score, coverage_rate: 0.625 }} />);

    expect(screen.getByText("Couverture 63 %")).toBeInTheDocument();
  });

  it("n’invente pas de couverture pour un score qui n’en a pas", () => {
    render(<ScoreSummary score={{ ...score, coverage_rate: null }} />);

    expect(screen.queryByText(/Couverture/)).not.toBeInTheDocument();
  });
});
