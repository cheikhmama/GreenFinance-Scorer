import { describe, expect, it, vi } from "vitest";
import { chargerToutesLesPagesAvecEtat, LIGNES_MAX } from "./toutesLesPages";

function source(pages: number) {
  return vi.fn(async (page: number) => {
    // Les pages répondent dans le désordre : l'assemblage doit quand même suivre leur numéro.
    await new Promise((fin) => setTimeout(fin, (pages - page) % 3));
    return { items: [page * 10, page * 10 + 1], page, pages };
  });
}

describe("chargerToutesLesPagesAvecEtat", () => {
  it("charge toutes les pages dans l'ordre", async () => {
    const charger = source(7);
    const { lignes, tronque } = await chargerToutesLesPagesAvecEtat(charger);
    expect(lignes).toEqual([10, 11, 20, 21, 30, 31, 40, 41, 50, 51, 60, 61, 70, 71]);
    expect(tronque).toBe(false);
    expect(charger).toHaveBeenCalledTimes(7);
  });

  it("s'arrête au plafond et le signale", async () => {
    const charger = source(80);
    const { tronque } = await chargerToutesLesPagesAvecEtat(charger);
    expect(tronque).toBe(true);
    expect(charger).toHaveBeenCalledTimes(LIGNES_MAX / 100);
  });

  it("une liste vide ne demande que la première page", async () => {
    const charger = vi.fn(async () => ({ items: [], page: 1, pages: 0 }));
    expect(await chargerToutesLesPagesAvecEtat(charger)).toEqual({ lignes: [], tronque: false });
    expect(charger).toHaveBeenCalledTimes(1);
  });
});
