import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreSummary } from "./EsgSummary";

const score = {
  valeur_globale: 66.4,
  score_environnement: 50,
  score_social: 86,
  score_gouvernance: 80,
  configuration_version: 2,
};

describe("ScoreSummary", () => {
  it("affiche la couverture à côté du score global", () => {
    render(<ScoreSummary score={{ ...score, taux_couverture: 0.625 }} />);

    expect(screen.getByText("Couverture 63 %")).toBeInTheDocument();
  });

  it("n’invente pas de couverture pour un score qui n’en a pas", () => {
    render(<ScoreSummary score={{ ...score, taux_couverture: null }} />);

    expect(screen.queryByText(/Couverture/)).not.toBeInTheDocument();
  });
});
