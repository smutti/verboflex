import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  listProductWorkspaces,
  type ProductWorkspaceCard,
} from "../../api/client";
import { ProductWorkspaceIndex } from "./ProductWorkspaceIndex";

vi.mock("../../api/client", () => ({ listProductWorkspaces: vi.fn() }));
const api = vi.mocked(listProductWorkspaces);
const card: ProductWorkspaceCard = {
  id: "product-one",
  name: "Northstar Android",
  imported_scope_count: 1,
  unimported_scope_count: 0,
  last_imported_at: null,
  coverage: {
    source_string_count: 200,
    expected_translation_count: 600,
    translated_count: 450,
    missing_count: 150,
    coverage_percent: 75,
    languages: ["en", "it", "vi", "ar"],
    language_count: 4,
  },
};
const response = (items = [card], total = items.length, hasMore = false) => ({
  data: { items, total, page: 1, has_more: hasMore },
  error: undefined,
});
const mount = () =>
  render(
    <MemoryRouter>
      <ProductWorkspaceIndex accessToken="session" />
    </MemoryRouter>,
  );
beforeEach(() => {
  api.mockReset();
  api.mockResolvedValue(response());
});
afterEach(cleanup);

it("shows repository coverage and supported languages with a product link", async () => {
  mount();
  const link = await screen.findByRole("link", {
    name: "Open Northstar Android workspace",
  });
  expect(link).toHaveAttribute("href", "/products/product-one/strings");
  expect(within(link).getByText("200")).toBeVisible();
  expect(within(link).getByText("150 missing")).toBeVisible();
  expect(within(link).getByRole("progressbar")).toHaveAttribute(
    "aria-valuenow",
    "75",
  );
  expect(within(link).getByLabelText("Supported languages")).toHaveTextContent(
    "enitviar",
  );
  expect(api).toHaveBeenCalledTimes(1);
});

it("does not claim completion for missing statistics or zero denominators", async () => {
  api.mockResolvedValue(
    response([
      {
        ...card,
        id: "unimported",
        name: "Unimported",
        coverage: null,
        imported_scope_count: 0,
      },
      {
        ...card,
        id: "source-only",
        name: "Source only",
        coverage: {
          ...card.coverage!,
          coverage_percent: null,
          expected_translation_count: 0,
          translated_count: 0,
          missing_count: 0,
        },
      },
    ]),
  );
  mount();
  expect(await screen.findByText("Not imported yet")).toBeVisible();
  expect(screen.getByText("No target translations imported")).toBeVisible();
  expect(screen.queryByRole("progressbar")).toBeNull();
});

it("searches on the server and resets pagination when the query changes", async () => {
  api.mockResolvedValue(response([card], 25, true));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Next" }));
  await waitFor(() =>
    expect(api).toHaveBeenLastCalledWith(
      expect.objectContaining({ query: { q: "", page: 2 } }),
    ),
  );
  fireEvent.change(screen.getByRole("searchbox", { name: "Search products" }), {
    target: { value: "Android" },
  });
  await waitFor(() =>
    expect(api).toHaveBeenLastCalledWith(
      expect.objectContaining({ query: { q: "Android", page: 1 } }),
    ),
  );
});

it("can clear a no-match search", async () => {
  mount();
  await screen.findByRole("link", { name: /Northstar/ });
  api.mockResolvedValue(response([]));
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "missing" },
  });
  expect(await screen.findByText("No products found")).toBeVisible();
  api.mockResolvedValue(response());
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(await screen.findByRole("link", { name: /Northstar/ })).toBeVisible();
  expect(screen.getByRole("searchbox")).toHaveValue("");
});

it("ignores stale results from a previous query", async () => {
  let resolve!: (value: ReturnType<typeof response>) => void;
  api.mockReturnValueOnce(
    new Promise<ReturnType<typeof response>>((r) => {
      resolve = r;
    }),
  );
  mount();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "new" } });
  api.mockResolvedValue(response([{ ...card, name: "New product" }]));
  expect(
    await screen.findByRole("link", { name: "Open New product workspace" }),
  ).toBeVisible();
  await act(async () => {
    resolve(response());
  });
  expect(screen.queryByRole("link", { name: /Northstar/ })).toBeNull();
});

it("hides previous session data and retries failed requests", async () => {
  const view = mount();
  await screen.findByRole("link", { name: /Northstar/ });
  api.mockRejectedValueOnce(new Error("offline"));
  view.rerender(
    <MemoryRouter>
      <ProductWorkspaceIndex accessToken="new-session" />
    </MemoryRouter>,
  );
  expect(screen.queryByRole("link", { name: /Northstar/ })).toBeNull();
  expect(await screen.findByText("Products could not be loaded")).toBeVisible();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry loading products" }),
  );
  expect(await screen.findByRole("link", { name: /Northstar/ })).toBeVisible();
});
