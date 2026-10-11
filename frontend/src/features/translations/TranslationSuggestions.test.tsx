import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { TranslationSuggestions } from "./TranslationSuggestions";
import {
  getTranslationSuggestions,
  resolveTranslationSuggestion,
  matchGlossaryTerms,
  type ReuseQuery,
} from "../../api/client";
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  getTranslationSuggestions: vi.fn(),
  resolveTranslationSuggestion: vi.fn(),
  matchGlossaryTerms: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const query: ReuseQuery = {
  source_text: "Hello",
  source_language: "en",
  target_language: "it",
  format: "android_xml",
  selector_kind: "scalar",
};
const item = {
  source_value_id: "source",
  target_value_id: "target",
  source_text: "Hello",
  target_text: "Ciao",
  digest: "digest",
  match_percent: 100,
  origin: "repository",
  product_name: "Product",
  key: "hello",
  repository: "team/repo",
  file: "values-it/strings.xml",
};
function setup() {
  vi.mocked(getTranslationSuggestions).mockResolvedValue({
    data: { items: [item] },
  } as never);
  vi.mocked(matchGlossaryTerms).mockResolvedValue({
    data: { items: [], truncated: false },
  } as never);
  const onUse = vi.fn();
  const props = {
    accessToken: "token",
    productId: "product",
    query,
    disabled: false,
    onUse,
    currentText: "",
  };
  return { ...render(<TranslationSuggestions {...props} />), props, onUse };
}
it("displays match and provenance, resolves Use and never applies automatically", async () => {
  const { onUse } = setup();
  const user = userEvent.setup();
  expect(await screen.findByText("100%")).toBeVisible();
  expect(screen.getByText("Repository")).toBeVisible();
  expect(onUse).not.toHaveBeenCalled();
  vi.mocked(resolveTranslationSuggestion).mockResolvedValue({
    data: item,
  } as never);
  await user.click(screen.getByRole("button", { name: "Use" }));
  await waitFor(() => expect(onUse).toHaveBeenCalledWith("Ciao"));
  expect(resolveTranslationSuggestion).toHaveBeenCalledWith(
    expect.objectContaining({
      body: expect.objectContaining({ expected_digest: "digest" }),
    }),
  );
});
it("does not overwrite text typed while the suggestion is being checked", async () => {
  const { onUse, rerender, props } = setup();
  const user = userEvent.setup();
  let finish!: (v: never) => void;
  vi.mocked(resolveTranslationSuggestion).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }) as never,
  );
  await user.click(await screen.findByRole("button", { name: "Use" }));
  rerender(<TranslationSuggestions {...props} currentText="typed now" />);
  finish({ data: item } as never);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Translation changed",
  );
  expect(onUse).not.toHaveBeenCalled();
});
it("reports stale suggestions without changing the draft", async () => {
  const { onUse } = setup();
  const user = userEvent.setup();
  vi.mocked(resolveTranslationSuggestion).mockResolvedValue({
    error: { detail: "changed" },
  } as never);
  await user.click(await screen.findByRole("button", { name: "Use" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This suggestion changed",
  );
  expect(onUse).not.toHaveBeenCalled();
});
it("highlights forbidden terms as the translation is edited", async () => {
  const { rerender, props } = setup();
  vi.mocked(matchGlossaryTerms).mockResolvedValue({
    data: {
      items: [
        {
          id: "term",
          source_term: "Hello",
          target_term: "Salve",
          forbidden: true,
          case_sensitive: false,
        },
      ],
      truncated: false,
    },
  } as never);
  rerender(
    <TranslationSuggestions
      {...props}
      query={{ ...query, source_text: "Hello there" }}
      currentText="Salve"
    />,
  );
  expect(
    await screen.findByText("Forbidden term in translation"),
  ).toBeVisible();
});
