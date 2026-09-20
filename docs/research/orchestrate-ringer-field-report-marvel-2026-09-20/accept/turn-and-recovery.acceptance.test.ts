import { describe, expect, it } from "vitest";
import { loadBuilderCatalog } from "@/catalog/builder-catalog";
import { evaluateCharacter } from "@/domain/character";
import { RECOVERY_TARGET_NUMBER, adjustResource, createPlayState, recover, recoveryRoll, rollD616, setResource, startOfTurn, toggleCondition, type D616Roll } from "@/domain/play";
import { failsafeRecord } from "@/test/fixtures/failsafe";

// Failsafe: Rank 3, Resilience 3, Vigilance 3, Health 90, Focus 90, Karma 3.
const catalog = loadBuilderCatalog();
const sheet = evaluateCharacter(failsafeRecord(catalog.revision), catalog).sheet;
const fresh = () => createPlayState(sheet);
const scripted = (...faces: number[]) => () => faces.shift()!;
const roll = (a: number, m: number, b: number): D616Roll => rollD616(scripted(a, m, b));

describe("start of turn", () => {
  it("takes 5 Health for each of Ablaze, Bleeding, and Corroding, and says which", () => {
    let state = toggleCondition(toggleCondition(fresh(), "bleeding"), "ablaze");
    const turn = startOfTurn(state, sheet);
    expect(turn.state.health).toBe(80);
    expect(turn.losses.map((l) => [l.slug, l.amount]).sort()).toEqual([["ablaze", 5], ["bleeding", 5]]);
    state = toggleCondition(fresh(), "corroding");
    expect(startOfTurn(state, sheet).state.health).toBe(85);
  });

  it("changes nothing for a character with no such condition", () => {
    const state = toggleCondition(fresh(), "stunned");
    const turn = startOfTurn(state, sheet);
    expect(turn.state).toBe(state);
    expect(turn.losses).toEqual([]);
  });

  it("never takes Health below the track's floor", () => {
    const state = toggleCondition(setResource(fresh(), sheet, "health", -88), "bleeding");
    expect(startOfTurn(state, sheet).state.health).toBe(-90);
  });
});

describe("Karma recovery", () => {
  it("rolls Resilience for Health and Vigilance for Focus against TN 10", () => {
    expect(recoveryRoll(sheet, "health")).toMatchObject({ ability: "resilience", kind: "check" });
    expect(recoveryRoll(sheet, "focus")).toMatchObject({ ability: "vigilance", kind: "check" });
    expect(RECOVERY_TARGET_NUMBER).toBe(10);
  });

  it("on a success recovers Marvel die x rank + the ability, spends 1 Karma, and stops Bleeding", () => {
    const hurt = toggleCondition(setResource(fresh(), sheet, "health", 40), "bleeding");
    const result = recover(hurt, sheet, "health", roll(4, 3, 4)); // 11 + 3 = 14, a success
    expect(result.outcome).toBe("recovered");
    expect(result.amount).toBe(3 * 3 + 3);
    expect(result.state.health).toBe(52);
    expect(result.state.karma).toBe(2);
    expect(result.state.conditions).not.toContain("bleeding");
  });

  it("doubles on a Fantastic roll and stops at the maximum", () => {
    const result = recover(setResource(fresh(), sheet, "focus", 60), sheet, "focus", roll(2, 1, 2)); // the M counts 6: (6 x 3 + 3) x 2 = 42
    expect(result.amount).toBe(42);
    expect(result.state.focus).toBe(90);
    // Focus recovery leaves Bleeding alone.
    const bleeding = toggleCondition(setResource(fresh(), sheet, "focus", 10), "bleeding");
    expect(recover(bleeding, sheet, "focus", roll(4, 3, 4)).state.conditions).toContain("bleeding");
  });

  it("spends the Karma even when the check fails, and recovers nothing", () => {
    const result = recover(setResource(fresh(), sheet, "health", 40), sheet, "health", roll(1, 2, 1)); // 4 + 3 = 7
    expect(result).toMatchObject({ outcome: "failed", amount: 0 });
    expect(result.state.health).toBe(40);
    expect(result.state.karma).toBe(2);
  });

  it("can't be tried with no Karma", () => {
    const broke = adjustResource(setResource(fresh(), sheet, "health", 40), sheet, "karma", -3);
    const result = recover(broke, sheet, "health", roll(6, 6, 6));
    expect(result.outcome).toBe("no-karma");
    expect(result.state).toBe(broke);
  });
});
