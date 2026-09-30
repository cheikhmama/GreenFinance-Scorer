import { describe, expect, it } from "vitest";
import {
  libelleActionJournal,
  libelleResultatJournal,
  libelleTypeRessource,
  libelleValeurJournal,
} from "./journal";

describe("libellés du journal d'audit", () => {
  it("traduit les codes connus", () => {
    expect(libelleActionJournal("account_deactivated")).toBe("Désactivation du compte");
    expect(libelleTypeRessource("User")).toBe("Utilisateur");
    expect(libelleResultatJournal("failure")).toBe("Échec");
    expect(libelleValeurJournal("inactive")).toBe("inactif");
  });

  it("affiche tel quel un code inconnu ou une valeur libre", () => {
    expect(libelleActionJournal("nouvelle_action")).toBe("nouvelle_action");
    expect(libelleValeurJournal("ancien@example.com")).toBe("ancien@example.com");
  });
});
