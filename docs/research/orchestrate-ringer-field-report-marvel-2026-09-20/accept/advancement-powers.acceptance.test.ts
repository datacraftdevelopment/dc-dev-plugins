import { describe, expect, it } from "vitest";
import { loadBuilderCatalog } from "@/catalog/builder-catalog";
import { createCharacterRecord, evaluateCharacter, powerOptions, setAdvancementBoxes, setGettingSchooled, togglePower } from "@/domain/character";

// Flight 1 and Combat Trickery are Basic powers whose only prerequisite is Rank 2.
const catalog = loadBuilderCatalog();
const rookie = () => setGettingSchooled(createCharacterRecord({ id: "r", codename: "Rookie", rank: 1 }, catalog), true);
const option = (record: ReturnType<typeof rookie>, slug: string) => powerOptions(record, catalog, "basic").find((o) => o.entry.slug === slug)!;
const codes = (record: ReturnType<typeof rookie>) => evaluateCharacter(record, catalog).validation.map((i) => i.code);

describe("a Getting Schooled power box reaches one rank up", () => {
  it("keeps a next-rank power locked without a box", () => {
    expect(option(rookie(), "flight-1")).toMatchObject({ state: "locked", viaAdvancement: false });
  });

  it("offers it once a power box is marked, and says the box is why", () => {
    const record = setAdvancementBoxes(rookie(), "power", 1, 1);
    expect(option(record, "flight-1")).toMatchObject({ state: "available", viaAdvancement: true });
    // A power the character could take anyway is not an advancement pick.
    const plain = powerOptions(record, catalog, "basic").find((o) => o.state === "available" && o.requirements.length === 0)!;
    expect(plain.viaAdvancement).toBe(false);
  });

  it("spends the box: the pick is recorded as advancement, passes the rank check, and the next one is locked again", () => {
    let record = setAdvancementBoxes(rookie(), "power", 1, 1);
    record = togglePower(record, "flight-1", "advancement");
    expect(record.powers.find((p) => p.slug === "flight-1")?.reason).toBe("advancement");
    expect(codes(record)).not.toContain("power-rank-too-low");
    expect(option(record, "combat-trickery")).toMatchObject({ state: "locked", viaAdvancement: false });
    // Toggling it off gives the box back.
    expect(option(togglePower(record, "flight-1"), "combat-trickery").state).toBe("available");
  });

  it("is an error to hold more next-rank powers than power boxes", () => {
    let record = setAdvancementBoxes(rookie(), "power", 1, 1);
    record = togglePower(record, "flight-1", "advancement");
    record = setAdvancementBoxes(record, "power", 0, 1);
    const issue = evaluateCharacter(record, catalog).validation.find((i) => i.code === "advancement-powers-over-boxes");
    expect(issue?.severity).toBe("error");
  });

  it("stops counting an advancement power against boxes once the character reaches its rank", () => {
    let record = setAdvancementBoxes(rookie(), "power", 1, 1);
    record = togglePower(record, "flight-1", "advancement");
    const ranked = { ...record, identity: { ...record.identity, rank: 2 }, advancement: { ...record.advancement, completedRank: 2, powerBoxes: 0, rankProgress: 0, remainingBoxes: 10 } };
    expect(codes(ranked)).not.toContain("advancement-powers-over-boxes");
    expect(codes(ranked)).not.toContain("power-rank-too-low");
  });

  it("still defaults a plain toggle to a purchased pick", () => {
    const record = togglePower(rookie(), "accuracy-1");
    expect(record.powers.find((p) => p.slug === "accuracy-1")?.reason).toBe("purchased");
  });
});
