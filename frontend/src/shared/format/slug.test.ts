import { describe, expect, it } from "vitest";
import { creerSlug, idDepuisSlug } from "./slug";

const UUID = "19aaf2b0-5cff-42c0-a9e3-c2c40eb71e6d";

describe("creerSlug", () => {
  it("normalise accents, casse et ponctuation", () => {
    expect(creerSlug("Finance durable — obligations vertes", UUID)).toBe(
      `finance-durable-obligations-vertes-${UUID}`,
    );
  });

  it("retombe sur l'UUID seul quand le libellé est vide ou absent", () => {
    expect(creerSlug(null, UUID)).toBe(UUID);
    expect(creerSlug(undefined, UUID)).toBe(UUID);
    expect(creerSlug("   ", UUID)).toBe(UUID);
  });

  it("tronque un libellé trop long sans laisser de tiret final", () => {
    const long = "a".repeat(100);
    const slug = creerSlug(long, UUID);
    expect(slug.endsWith(`-${UUID}`)).toBe(true);
    expect(slug.length).toBeLessThan(long.length + UUID.length);
  });
});

describe("idDepuisSlug", () => {
  it("extrait l'UUID en fin d'un slug lisible", () => {
    expect(idDepuisSlug(`mon-portefeuille-${UUID}`)).toBe(UUID);
  });

  it("reste compatible avec un UUID brut hérité (notifications, anciens liens)", () => {
    expect(idDepuisSlug(UUID)).toBe(UUID);
  });

  it("est insensible à la casse de l'UUID", () => {
    expect(idDepuisSlug(`cmm-${UUID.toUpperCase()}`)).toBe(UUID.toUpperCase());
  });
});
