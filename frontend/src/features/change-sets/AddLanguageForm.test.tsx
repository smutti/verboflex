import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createProjectLanguage } from "@/api/client";
import { AddLanguageForm } from "./AddLanguageForm";

vi.mock("@/api/client", () => ({ createProjectLanguage: vi.fn() }));
const create = vi.mocked(createProjectLanguage);
beforeEach(() => vi.resetAllMocks());
afterEach(cleanup);

it("queues the chosen locale and preserves input on failure", async () => {
  const onCreated = vi.fn();
  create.mockRejectedValueOnce(new Error("conflict"));
  render(
    <AddLanguageForm
      accessToken="synthetic"
      productId="product"
      workflowId="workflow"
      onCreated={onCreated}
    />,
  );
  const input = screen.getByRole("textbox", { name: "New language" });
  await userEvent.type(input, "fr-BE");
  await userEvent.click(screen.getByRole("button", { name: "Add language" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not add this language",
  );
  expect(input).toHaveValue("fr-BE");
  expect(onCreated).not.toHaveBeenCalled();
  create.mockResolvedValueOnce({
    data: { id: "job", state: "queued" },
  } as never);
  await userEvent.click(screen.getByRole("button", { name: "Add language" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
  expect(create).toHaveBeenLastCalledWith({
    auth: "synthetic",
    path: { product_id: "product" },
    body: { workflow_id: "workflow", language: "fr-BE" },
  });
  expect(input).toHaveValue("");
  expect(screen.getByRole("status")).toHaveTextContent("refresh the source");
});

it("explains copied source text and screenshot reuse before submission", () => {
  render(
    <AddLanguageForm
      accessToken="synthetic"
      productId="product"
      workflowId="workflow"
      onCreated={() => {}}
    />,
  );
  expect(
    screen.getByText(/preserving keys, structure and placeholders/),
  ).toBeVisible();
  expect(screen.getByText(/configured screenshot scenarios/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Add language" })).toBeDisabled();
});
