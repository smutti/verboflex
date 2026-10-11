import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { Glossary } from "./Glossary";
import { listGlossaryTerms, saveGlossaryTerm } from "../../api/client";
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  listGlossaryTerms: vi.fn(),
  saveGlossaryTerm: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
function setup(canManage = true) {
  vi.mocked(listGlossaryTerms).mockResolvedValue({
    data: { items: [], next_after: null },
  } as never);
  return render(
    <Glossary
      accessToken="token"
      productId="product"
      canManage={canManage}
      languages={[
        { code: "en", label: "English" },
        { code: "it", label: "Italian" },
      ]}
    />,
  );
}
it("saves a forbidden term with explicit languages and version", async () => {
  setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Glossary" }));
  await user.click(await screen.findByRole("button", { name: "Add term" }));
  await user.type(screen.getByLabelText("Source term"), "app");
  await user.type(screen.getByLabelText("Translation"), "programma");
  await user.click(screen.getByLabelText("Forbidden translation"));
  vi.mocked(saveGlossaryTerm).mockResolvedValue({
    data: { id: "new" },
  } as never);
  await user.click(screen.getByRole("button", { name: "Save term" }));
  await waitFor(() =>
    expect(saveGlossaryTerm).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          expected_version: 0,
          source_language: "en",
          target_language: "it",
          source_term: "app",
          target_term: "programma",
          forbidden: true,
        }),
      }),
    ),
  );
  expect(await screen.findByRole("button", { name: "Add term" })).toBeVisible();
});
it("requires confirmation before discarding a dirty term and hides writes from viewers", async () => {
  const { unmount } = setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Glossary" }));
  await user.click(await screen.findByRole("button", { name: "Add term" }));
  await user.type(screen.getByLabelText("Source term"), "app");
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(await screen.findByRole("alertdialog")).toHaveTextContent(
    "Discard changes?",
  );
  await user.click(screen.getByRole("button", { name: "Keep" }));
  expect(screen.getByLabelText("Source term")).toHaveValue("app");
  unmount();
  setup(false);
  await user.click(screen.getByRole("button", { name: "Glossary" }));
  expect(await screen.findByText("No terms")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Add term" }),
  ).not.toBeInTheDocument();
});
