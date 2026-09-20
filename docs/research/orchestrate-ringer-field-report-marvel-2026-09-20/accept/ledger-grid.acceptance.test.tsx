// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { loadBuilderCatalog } from "@/catalog/builder-catalog";
import { evaluateCharacter, setAdvancementBoxes, type CharacterRecord } from "@/domain/character";
import { createJsonMarkdownExporter } from "@/exports";
import { LedgerPanel } from "@/features/builder/LedgerPanel";
import { failsafeRecord } from "@/test/fixtures/failsafe";
import { parallaxRecord } from "@/test/fixtures/parallax";

afterEach(cleanup);
const catalog = loadBuilderCatalog();
const open = (record: CharacterRecord) => {
  const evaluation = evaluateCharacter(record, catalog);
  render(<LedgerPanel evaluation={evaluation} open onClose={() => {}} />);
  return evaluation;
};
const cell = (term: string) => {
  const grid = document.querySelector('[aria-label="Derived statistics"]')!;
  const dt = [...grid.querySelectorAll("dt")].find((d) => d.textContent?.trim() === term);
  return dt?.parentElement?.querySelector("dd")?.textContent?.trim();
};

describe("ledger stat grid", () => {
  it("shows Flight and Damage Reduction when the character has them", () => {
    const ev = open(failsafeRecord(catalog.revision));
    expect(ev.derived.speeds.flight).toBe(15);
    expect(cell("Flight")).toBe("15");
    expect(cell("Health DR")).toBe("3");
    expect(cell("Focus DR")).toBeUndefined(); // she has none
  });

  it("leaves them out for a character with neither", () => {
    open(parallaxRecord(catalog.revision));
    expect(cell("Run")).toBeDefined();
    expect(cell("Flight")).toBeUndefined();
    expect(cell("Health DR")).toBeUndefined();
  });
});

describe("power pick sum", () => {
  const schooled = () => setAdvancementBoxes(parallaxRecord(catalog.revision), "power", 2, 3);

  it("counts Getting Schooled power boxes in the ledger note, so the note adds up to the total", () => {
    const ev = open(schooled());
    const note = within(screen.getByRole("region", { name: "Power picks budget" })).getByText(/for rank/).textContent!;
    expect(note).toMatch(/\+ 2 from Getting Schooled/i);
    const numbers = [...note.matchAll(/([+−-])?\s*(\d+)/g)].reduce((sum, m) => sum + (m[1] === "−" || m[1] === "-" ? -1 : 1) * Number(m[2]), 0);
    expect(numbers).toBe(ev.budget.power.available);
  });

  it("says nothing about Getting Schooled when no power box is marked", () => {
    open(parallaxRecord(catalog.revision));
    expect(screen.getByRole("region", { name: "Power picks budget" }).textContent).not.toMatch(/getting schooled/i);
  });

  it("counts them on the Markdown export's Power picks line too", () => {
    const record = schooled();
    const md = createJsonMarkdownExporter().toMarkdown(record, evaluateCharacter(record, catalog));
    const line = md.split("\n").find((l) => l.startsWith("Power picks:"))!;
    expect(line).toMatch(/2 from Getting Schooled/i);
    const plain = parallaxRecord(catalog.revision);
    expect(createJsonMarkdownExporter().toMarkdown(plain, evaluateCharacter(plain, catalog))).not.toMatch(/from Getting Schooled/i);
  });
});
