import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TranslationFilters } from "./TranslationFilters";

afterEach(cleanup);
const defaults = {
  productId: null,
  language: null,
  state: null,
  violation: null,
  deleted: "active" as const,
};
const options = {
  products: [
    { id: "alpha", name: "Alpha" },
    { id: "beta", name: "Beta" },
  ],
  languages: [
    { code: "it", label: "Italian" },
    { code: "en", label: "English" },
  ],
};
function mount(disabled = false) {
  const onChange = vi.fn();
  const onClear = vi.fn();
  render(
    <TranslationFilters
      filters={defaults}
      options={options}
      disabled={disabled}
      onChange={onChange}
      onClear={onClear}
    />,
  );
  return { onChange, onClear };
}

describe("TranslationFilters", () => {
  it("has exactly five ordered, named controls and approved defaults", () => {
    mount();
    const labels = [
      "Product",
      "Language",
      "Approval state",
      "Length status",
      "Deleted status",
    ];
    expect(screen.getAllByRole("combobox")).toEqual(
      labels.map((name) => screen.getByRole("combobox", { name })),
    );
    for (const [index, value] of [
      "All products",
      "All languages",
      "All states",
      "All length statuses",
      "Active only",
    ].entries()) {
      expect(screen.getAllByRole("combobox")[index]).toHaveTextContent(value);
    }
    expect(
      screen.getAllByRole("button", { name: "Clear filters" }),
    ).toHaveLength(1);
  });

  it.each([
    [
      "Product",
      ["All products", "Alpha", "Beta"],
      "Beta",
      { productId: "beta" },
    ],
    [
      "Language",
      ["All languages", "Italian (it)", "English (en)"],
      "Italian (it)",
      { language: "it" },
    ],
    [
      "Approval state",
      ["All states", "Draft", "Approved", "Rejected"],
      "Approved",
      { state: "approved" },
    ],
    [
      "Length status",
      ["All length statuses", "Over limit", "Within limit", "No max length"],
      "No max length",
      { violation: "no_max" },
    ],
    [
      "Deleted status",
      ["Active only", "Deleted only", "Active and deleted"],
      "Active and deleted",
      { deleted: "all" },
    ],
  ])(
    "exposes exact %s choices and emits immediately",
    async (label, choices, choice, changed) => {
      const user = userEvent.setup();
      const { onChange } = mount();
      await user.click(screen.getByRole("combobox", { name: label }));
      expect(
        within(screen.getByRole("listbox"))
          .getAllByRole("option")
          .map((option) => option.textContent),
      ).toEqual(choices);
      await user.click(
        screen.getByRole("option", { name: choice, exact: true }),
      );
      expect(onChange).toHaveBeenCalledExactlyOnceWith({
        ...defaults,
        ...changed,
      });
    },
  );

  it("supports keyboard selection and a separate clear action", async () => {
    const user = userEvent.setup();
    const { onChange, onClear } = mount();
    screen.getByRole("combobox", { name: "Approval state" }).focus();
    await user.keyboard("{Enter}{End}{Enter}");
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      ...defaults,
      state: "rejected",
    });
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("disables unauthorized options while loading", () => {
    mount(true);
    for (const control of screen.getAllByRole("combobox"))
      expect(control).toBeDisabled();
  });
});
