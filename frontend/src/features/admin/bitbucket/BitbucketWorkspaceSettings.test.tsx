import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  getAdminBitbucketWorkspace,
  updateAdminBitbucketWorkspace,
} from "../../../api/client";
import { BitbucketWorkspaceSettings } from "./BitbucketWorkspaceSettings";

vi.mock("../../../api/client", () => ({
  getAdminBitbucketWorkspace: vi.fn(),
  updateAdminBitbucketWorkspace: vi.fn(),
}));
function ok(workspace: string | null) {
  return {
    data: { workspace },
    error: undefined,
    request: new Request("http://localhost/workspace"),
    response: new Response(null, { status: 200 }),
  };
}
beforeEach(() => {
  vi.mocked(getAdminBitbucketWorkspace)
    .mockReset()
    .mockResolvedValue(ok("acme"));
  vi.mocked(updateAdminBitbucketWorkspace)
    .mockReset()
    .mockResolvedValue(ok("other"));
});
afterEach(cleanup);

it("loads the central workspace and saves a normalized replacement", async () => {
  render(<BitbucketWorkspaceSettings accessToken="token" />);
  expect(await screen.findByText("Workspace configurato: acme")).toBeVisible();
  const input = screen.getByLabelText("Workspace");
  await userEvent.clear(input);
  await userEvent.type(input, " Other ");
  await userEvent.click(
    screen.getByRole("button", { name: "Salva workspace" }),
  );
  expect(await screen.findByText("Workspace configurato: other")).toBeVisible();
  expect(updateAdminBitbucketWorkspace).toHaveBeenCalledWith({
    auth: "token",
    body: { workspace: "Other" },
  });
  expect(input).toHaveValue("other");
});

it("preserves input after a save failure and bounds duplicate writes", async () => {
  vi.mocked(updateAdminBitbucketWorkspace).mockRejectedValueOnce(
    new Error("private diagnostics"),
  );
  render(<BitbucketWorkspaceSettings accessToken="token" />);
  await screen.findByText("Workspace configurato: acme");
  const input = screen.getByLabelText("Workspace");
  await userEvent.clear(input);
  await userEvent.type(input, "other");
  await userEvent.click(
    screen.getByRole("button", { name: "Salva workspace" }),
  );
  expect(await screen.findByRole("alert")).not.toHaveTextContent(
    "private diagnostics",
  );
  expect(input).toHaveValue("other");
  vi.mocked(updateAdminBitbucketWorkspace).mockReturnValueOnce(
    new Promise<ReturnType<typeof ok>>(() => {}),
  );
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Salva workspace" }),
  );
  expect(updateAdminBitbucketWorkspace).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("button", { name: "Salvataggio…" })).toBeDisabled();
});

it("retries a failed load before allowing a workspace overwrite", async () => {
  vi.mocked(getAdminBitbucketWorkspace).mockRejectedValueOnce(
    new Error("private diagnostics"),
  );
  render(<BitbucketWorkspaceSettings accessToken="token" />);
  expect(await screen.findByRole("alert")).not.toHaveTextContent(
    "private diagnostics",
  );
  expect(screen.getByLabelText("Workspace")).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
  await waitFor(() =>
    expect(screen.getByLabelText("Workspace")).toHaveValue("acme"),
  );
  expect(updateAdminBitbucketWorkspace).not.toHaveBeenCalled();
});
