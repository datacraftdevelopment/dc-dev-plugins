// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { loadBuilderCatalog } from "@/catalog/builder-catalog";
import { evaluateCharacter, setAdvancementBoxes, setIgnorePrerequisites, setTrade, type CharacterRecord } from "@/domain/character";
import { ProfileView } from "@/features/profile/ProfileView";
import { parallaxRecord } from "@/test/fixtures/parallax";

afterEach(cleanup);
const catalog = loadBuilderCatalog();
const show = (record: CharacterRecord) => render(<ProfileView evaluation={evaluateCharacter(record, catalog)} />);
const region = () => screen.queryByRole("region", { name: "Build adjustments" });

describe("Profile build adjustments", () => {
  it("has no such section for a plain build", () => {
    show(parallaxRecord(catalog.revision));
    expect(region()).toBeNull();
  });

  it("lists trades, Narrator overrides, and Getting Schooled boxes in plain words", () => {
    let record = parallaxRecord(catalog.revision);
    record = setTrade(record, "powerToAbility", 1);
    record = setTrade(record, "powerToTrait", 2);
    record = setTrade(record, "extraPowerPoints", 2);
    record = setIgnorePrerequisites(record, true);
    record = setAdvancementBoxes(record, "ability", 3, 3);
    show(record);
    const items = within(region()!).getAllByRole("listitem").map((li) => li.textContent ?? "");
    const has = (re: RegExp) => expect(items.some((t) => re.test(t)), `${re} in ${JSON.stringify(items)}`).toBe(true);
    has(/1 power pick traded for an ability point/i);
    has(/2 power picks traded for (2 )?traits/i);
    has(/2 extra power picks.*override/i);
    has(/prerequisites.*ignored.*override/i);
    has(/getting schooled.*3 ability/i);
  });

  it("marks overrides so they read as outside the rules, and trades as ordinary", () => {
    let record = setTrade(parallaxRecord(catalog.revision), "extraPowerPoints", 1);
    record = setTrade(record, "powerToAbility", 1);
    show(record);
    const items = within(region()!).getAllByRole("listitem");
    const override = items.find((li) => /override/i.test(li.textContent ?? ""))!;
    const trade = items.find((li) => /traded/i.test(li.textContent ?? ""))!;
    expect(override.getAttribute("data-override")).toBe("true");
    expect(trade.getAttribute("data-override")).not.toBe("true");
  });
});
