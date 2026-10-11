import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { TranslationAuthoring } from "./TranslationAuthoring";
import {
  getAuthoringDestinations,
  listAuthoringRequests,
  saveAuthoringRequest,
  reviewAuthoringRequest,
} from "../../api/client";
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  getAuthoringDestinations: vi.fn(),
  listAuthoringRequests: vi.fn(),
  saveAuthoringRequest: vi.fn(),
  reviewAuthoringRequest: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
function setup(canWrite = true) {
  vi.mocked(listAuthoringRequests).mockResolvedValue({
    data: { items: [], next_after: null },
  } as never);
  vi.mocked(getAuthoringDestinations).mockResolvedValue({
    data: {
      items: [
        {
          scope_id: "scope",
          execution_id: "execution",
          file_position: 3,
          path: "app/res/values/strings.xml",
          format: "android_xml",
          repository: "team/app",
          provider: "bitbucket",
          repository_side: "direct",
          base_language: "en",
          languages: ["en"],
          topology: "direct",
        },
      ],
      truncated: false,
    },
  } as never);
  return render(
    <TranslationAuthoring
      accessToken="token"
      productId="product"
      canWrite={canWrite}
      canReview
      selection={null}
      onClearSelection={() => {}}
      onNew={(open) => open()}
    />,
  );
}
it("saves an explicit destination as a draft, then approves its returned version", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(screen.getByRole("button", { name: "New key" }));
  await user.type(await screen.findByLabelText("Key"), "welcome");
  await user.type(screen.getByLabelText("Translation"), "Welcome");
  const row = {
    id: "addition",
    version: 1,
    state: "draft",
    input: {
      key: "welcome",
      language: "en",
      forms: [{ form: "other", text: "Welcome" }],
    },
    source_changed: false,
  };
  vi.mocked(saveAuthoringRequest).mockResolvedValue({ data: row } as never);
  vi.mocked(listAuthoringRequests).mockResolvedValue({
    data: { items: [row] },
  } as never);
  await user.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(saveAuthoringRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          scope_id: "scope",
          execution_id: "execution",
          file_position: 3,
          key: "welcome",
          language: "en",
          expected_version: 0,
          forms: [{ form: "other", text: "Welcome" }],
        }),
      }),
    ),
  );
  expect(reviewAuthoringRequest).not.toHaveBeenCalled();
  vi.mocked(reviewAuthoringRequest).mockResolvedValue({
    data: { ...row, version: 2, state: "approved" },
  } as never);
  await user.click(await screen.findByRole("button", { name: "Approve" }));
  expect(reviewAuthoringRequest).toHaveBeenCalledWith(
    expect.objectContaining({
      body: { expected_version: 1, state: "approved" },
    }),
  );
});
it("keeps draft text on conflicts and protects cancellation", async () => {
  const user = userEvent.setup();
  setup();
  await user.click(screen.getByRole("button", { name: "New key" }));
  await user.type(await screen.findByLabelText("Key"), "hello");
  await user.type(screen.getByLabelText("Translation"), "My text");
  vi.mocked(saveAuthoringRequest).mockResolvedValue({
    error: { detail: "Key already exists" },
  } as never);
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Key already exists",
  );
  expect(screen.getByLabelText("Translation")).toHaveValue("My text");
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(await screen.findByRole("alertdialog")).toHaveTextContent(
    "Discard unsaved changes?",
  );
  await user.click(screen.getByRole("button", { name: "Keep editing" }));
  expect(screen.getByLabelText("Translation")).toHaveValue("My text");
});
it("does not expose authoring actions to viewers", async () => {
  setup(false);
  await waitFor(() => expect(listAuthoringRequests).toHaveBeenCalled());
  expect(
    screen.queryByRole("button", { name: "New key" }),
  ).not.toBeInTheDocument();
});
