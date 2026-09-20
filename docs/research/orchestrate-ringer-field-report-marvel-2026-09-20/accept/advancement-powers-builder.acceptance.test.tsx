// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { loadBuilderCatalog } from "@/catalog/builder-catalog";
import { createCharacterRecord, setAdvancementBoxes, setGettingSchooled } from "@/domain/character";
import { Builder } from "@/features/builder/Builder";
import { createInMemoryCharacterRepository } from "@/persistence";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);
const catalog = loadBuilderCatalog();

it("lets a player spend a marked power box on a next-rank power in the Builder", async () => {
  const repository = createInMemoryCharacterRepository();
  const record = setAdvancementBoxes(setGettingSchooled(createCharacterRecord({ id: "r", codename: "Rookie", rank: 1 }, catalog), true), "power", 1, 1);
  await repository.create(record);
  const user = userEvent.setup({ delay: null });
  render(<Builder characterId="r" repository={repository} catalog={catalog} saveDelay={0} />);
  await screen.findByRole("heading", { level: 1, name: "Rookie" });

  const powers = screen.getByRole("region", { name: "Powers" });
  await user.click(within(powers).getByText("Basic powers"));
  const flight = await within(powers).findByRole("button", { name: "Flight 1" });
  expect((flight as HTMLButtonElement).disabled).toBe(false);
  expect(flight.closest("li")!.textContent).toMatch(/getting schooled/i);

  await user.click(flight);
  await waitFor(async () => expect((await repository.get("r"))!.powers.find((p) => p.slug === "flight-1")?.reason).toBe("advancement"));
  // The one box is spent, so the other Rank 2 basic power locks again.
  expect((within(powers).getByRole("button", { name: "Combat Trickery" }) as HTMLButtonElement).disabled).toBe(true);
});
