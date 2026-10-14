import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TranslationFilters } from "./TranslationFilters";

Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: { configurable: true, value: () => false },
  setPointerCapture: { configurable: true, value: () => {} },
  releasePointerCapture: { configurable: true, value: () => {} },
  scrollIntoView: { configurable: true, value: () => {} },
});
afterEach(async () => {
  cleanup();
  // Radix restores focus on the next task. Let that callback finish while
  // this test's document and CustomEvent still belong to the same DOM.
  await new Promise((resolve) => setTimeout(resolve, 0));
});
const defaults = {
  productId: null,
  language: null,
  state: null,
  violation: null,
  deleted: "active" as const,
};
const options = {
  products: [{ id: "alpha", name: "Alpha" }],
  languages: [
    { code: "en", label: "English" },
    { code: "fr", label: "French" },
    { code: "it", label: "Italian" },
  ],
};
function mount(extra = {}) {
  const onChange = vi.fn();
  const onClear = vi.fn();
  render(
    <TranslationFilters
      filters={defaults}
      options={options}
      onChange={onChange}
      onClear={onClear}
      {...extra}
    />,
  );
  return { onChange, onClear };
}
describe("TranslationFilters", () => {
  it("restores all language rows when switching from a focused subset to multilingual", async () => {
    const { onChange } = mount({
      filters: {
        ...defaults,
        language: "it",
        state: "draft",
        visibleLanguages: ["en", "it"],
        viewMode: "bilingual",
      },
      baseLanguage: "en",
    });
    await userEvent.click(screen.getByRole("button", { name: "Multilingual" }));
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      ...defaults,
      language: "it",
      state: "draft",
      visibleLanguages: null,
      viewMode: "multilingual",
    });
  });

  it("focuses an already visible target when entering bilingual view", async () => {
    const { onChange } = mount({
      filters: { ...defaults, visibleLanguages: ["en", "it"] },
      baseLanguage: "en",
    });
    await userEvent.click(screen.getByRole("button", { name: "Bilingual" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        language: "it",
        visibleLanguages: ["en", "it"],
        viewMode: "bilingual",
      }),
    );
  });
  it("includes an invisible advanced focus and retains source when the picker hides them", async () => {
    const filters = {
      ...defaults,
      language: "it",
      viewMode: "bilingual",
      visibleLanguages: ["en", "it"],
    };
    const { onChange } = mount({ filters, baseLanguage: "en" });
    await userEvent.click(screen.getByRole("button", { name: /^Filter/ }));
    await userEvent.click(
      screen.getByRole("combobox", { name: "Matching language" }),
    );
    await userEvent.click(screen.getByRole("option", { name: "French (fr)" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Apply filters" }),
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        language: "fr",
        visibleLanguages: ["en", "fr", "it"],
      }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Languages (2)" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "English (en)" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Italian (it)" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "French (fr)" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Apply languages" }),
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        language: "it",
        visibleLanguages: ["en", "fr", "it"],
      }),
    );
  });
  it("keeps advanced conditions closed until requested and applies a preset", async () => {
    const user = userEvent.setup();
    const { onChange } = mount();
    expect(screen.queryByRole("combobox")).toBeNull();
    await user.click(screen.getByRole("button", { name: /^Filter/ }));
    await user.click(screen.getByRole("button", { name: "Needs translation" }));
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      ...defaults,
      workStatus: "needs_translation",
    });
  });
  it("cancels draft conditions without emitting and applies one AND update", async () => {
    const user = userEvent.setup();
    const { onChange } = mount();
    await user.click(screen.getByRole("button", { name: /^Filter/ }));
    await user.click(
      screen.getByRole("combobox", { name: "Imported approval state" }),
    );
    await user.click(screen.getByRole("option", { name: "Approved" }));
    expect(onChange).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onChange).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /^Filter/ }));
    expect(
      screen.getByRole("combobox", { name: "Imported approval state" }),
    ).toHaveValue("Any state");
    await user.click(
      screen.getByRole("combobox", { name: "Imported approval state" }),
    );
    await user.click(screen.getByRole("option", { name: "Approved" }));
    await user.click(
      screen.getByRole("combobox", { name: "Imported length status" }),
    );
    await user.click(screen.getByRole("option", { name: "Over limit" }));
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      ...defaults,
      state: "approved",
      violation: "over_limit",
    });
  });
  it("removes accepted chips and clears optional criteria", async () => {
    const user = userEvent.setup();
    const { onChange, onClear } = mount({
      filters: { ...defaults, state: "approved", language: "it" },
    });
    await user.click(
      screen.getByRole("button", { name: "Remove Imported state: Approved" }),
    );
    expect(onChange).toHaveBeenCalledWith({
      ...defaults,
      state: null,
      language: "it",
    });
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onClear).toHaveBeenCalledOnce();
  });
  it("selects real visible locales with explicit default reset", async () => {
    const user = userEvent.setup();
    const { onChange } = mount({ visibleLanguages: ["en", "fr", "it"] });
    await user.click(screen.getByRole("button", { name: "Languages (3)" }));
    await user.click(screen.getByRole("checkbox", { name: "Italian (it)" }));
    expect(onChange).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Apply languages" }));
    expect(onChange).toHaveBeenCalledWith({
      ...defaults,
      visibleLanguages: ["en", "fr"],
    });
    await user.click(screen.getByRole("button", { name: "Languages (3)" }));
    await user.click(
      screen.getByRole("button", { name: "Use default languages" }),
    );
    expect(onChange).toHaveBeenLastCalledWith({
      ...defaults,
      visibleLanguages: null,
    });
  });
  it("returns focus on Escape and exposes disabled loading controls", async () => {
    const user = userEvent.setup();
    mount();
    const trigger = screen.getByRole("button", { name: /^Filter/ });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
    cleanup();
    mount({ disabled: true });
    expect(screen.getByRole("button", { name: /^Filter/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^Languages/ })).toBeDisabled();
  });
});

it("filters dropdown choices as the user types and applies only a selected option", async () => {
  const { onChange } = mount();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /^Filter/ }));
  const input = screen.getByRole("combobox", { name: "Matching language" });
  await user.click(input);
  await user.type(input, "ital");
  expect(screen.getByRole("option", { name: "Italian (it)" })).toBeVisible();
  expect(screen.queryByRole("option", { name: "French (fr)" })).toBeNull();
  expect(onChange).not.toHaveBeenCalled();
  await user.keyboard("{ArrowDown}{Enter}");
  expect(input).toHaveValue("Italian (it)");
  expect(screen.queryByRole("listbox")).toBeNull();
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({ language: "it" }),
  );
});

it("keeps the selected dropdown value when search is cancelled or has no results", async () => {
  const { onChange } = mount({ filters: { ...defaults, language: "fr" } });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /^Filter/ }));
  const input = screen.getByRole("combobox", { name: "Matching language" });
  await user.click(input);
  await user.type(input, "no-such-language");
  expect(screen.getByRole("status")).toHaveTextContent("No results");
  await user.keyboard("{Enter}{Escape}");
  expect(input).toHaveValue("French (fr)");
  expect(screen.getByRole("dialog")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({ language: "fr" }),
  );
});

it("searches visible languages without losing selections outside the results", async () => {
  const { onChange } = mount({ visibleLanguages: ["en"] });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Languages (1)" }));
  await user.type(
    screen.getByRole("textbox", { name: "Search languages" }),
    "french",
  );
  expect(screen.queryByRole("checkbox", { name: "English (en)" })).toBeNull();
  await user.click(screen.getByRole("checkbox", { name: "French (fr)" }));
  await user.click(screen.getByRole("button", { name: "Apply languages" }));
  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({ visibleLanguages: ["en", "fr"] }),
  );
});

it("finds region-specific locale codes by their language name", async () => {
  mount({
    options: { ...options, languages: [{ code: "it-IT", label: "it-IT" }] },
  });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /^Filter/ }));
  const input = screen.getByRole("combobox", { name: "Matching language" });
  await user.click(input);
  await user.type(input, "italian");
  expect(
    screen.getByRole("option", { name: "Italian (Italy) (it-IT)" }),
  ).toBeVisible();
});
