// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";
import { loadBuilderCatalog } from "@/catalog/builder-catalog";
import { evaluateCharacter } from "@/domain/character";
import { SheetView } from "@/features/sheet/SheetView";
import { createInMemoryPlayStateRepository } from "@/persistence";
import { failsafeRecord } from "@/test/fixtures/failsafe";

afterEach(cleanup);
const catalog = loadBuilderCatalog();
const scripted = (...faces: number[]) => () => faces.shift()!;

async function openSheet(...faces: number[]) {
  const evaluation = evaluateCharacter(failsafeRecord(catalog.revision), catalog);
  const user = userEvent.setup({ delay: null });
  render(<SheetView evaluation={evaluation} playRepository={createInMemoryPlayStateRepository()} rollDie={scripted(...faces)} />);
  await screen.findByRole("heading", { level: 1, name: "Failsafe" });
  return user;
}
const current = (track: string) => Number(screen.getByLabelText(`${track} current`).textContent);

it("starts a turn: Bleeding costs 5 Health and the sheet says so", async () => {
  const user = await openSheet();
  await user.click(within(screen.getByRole("group", { name: "Toggle conditions" })).getByRole("button", { name: "Bleeding" }));
  await user.click(screen.getByRole("button", { name: "Start my turn" }));
  expect(current("Health")).toBe(85);
  expect(screen.getByRole("status", { name: "Start of turn" }).textContent).toMatch(/bleeding.*5 health/i);
});

it("says a turn start cost nothing when no condition bites", async () => {
  const user = await openSheet();
  await user.click(screen.getByRole("button", { name: "Start my turn" }));
  expect(current("Health")).toBe(90);
  expect(screen.getByRole("status", { name: "Start of turn" }).textContent).toMatch(/nothing/i);
});

it("spends Karma on a Health recovery check and applies what the dice give", async () => {
  const user = await openSheet(4, 3, 4);
  const lose = screen.getByRole("button", { name: /^Lose \d+ Health$/ });
  await user.click(lose);
  const before = current("Health");
  expect(before).toBeLessThan(90);
  await user.click(screen.getByRole("button", { name: "Spend 1 Karma to recover Health" }));
  expect(current("Karma")).toBe(2);
  expect(current("Health")).toBe(Math.min(90, before + 12));
  expect(screen.getByRole("status", { name: "Health recovery" }).textContent).toMatch(/recovered \d+ health/i);
});

it("offers no recovery at full Health or with no Karma", async () => {
  await openSheet();
  expect((screen.getByRole("button", { name: "Spend 1 Karma to recover Health" }) as HTMLButtonElement).disabled).toBe(true);
});
