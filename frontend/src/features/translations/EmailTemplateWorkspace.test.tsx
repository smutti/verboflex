import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  getHtmlEditorDocument,
  getTranslationGroup,
  listHtmlTemplates,
  saveTranslationProposal,
  type CurrentUserResponse,
} from "@/api/client";
import { TranslationsWorkspace } from "./TranslationsWorkspace";
import { ProductStringsPage } from "./ProductStringsPage";
import {
  emailDetail,
  emailDocument,
  emailProjection,
  emailTemplates,
} from "./emailEditorTestFixture";
import { loadEmailWorkspaceView } from "./translationPreferences";

vi.mock("@/api/client", async (original) => ({
  ...(await original<typeof import("@/api/client")>()),
  getHtmlEditorDocument: vi.fn(),
  getTranslationGroup: vi.fn(),
  listHtmlTemplates: vi.fn(),
  saveTranslationProposal: vi.fn(),
}));
vi.mock("./TranslationSearchPage", () => ({
  TranslationSearchPage: () => <p>Existing string list</p>,
}));
const principal: CurrentUserResponse = {
  id: "editor",
  email: "editor@example.test",
  display_name: "Editor",
  roles: ["translator"],
  must_change_password: false,
};
function show(user = principal) {
  return render(
    <MemoryRouter initialEntries={["/strings"]}>
      <Routes>
        <Route
          element={
            <TranslationsWorkspace
              accessToken="token"
              principal={user}
              lockedProduct={{ id: "product", name: "Emails" }}
            />
          }
        >
          <Route path="strings" element={<ProductStringsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  vi.mocked(listHtmlTemplates).mockResolvedValue({
    data: { items: emailTemplates, next_cursor: null },
  } as never);
  vi.mocked(getHtmlEditorDocument).mockImplementation(
    async (request) =>
      ({
        data: emailDocument(request!.path.translation_group_id.split("-")[0]),
      }) as never,
  );
  vi.mocked(getTranslationGroup).mockImplementation(
    async (request) =>
      ({ data: emailDetail(request!.path.translation_group_id) }) as never,
  );
  vi.mocked(saveTranslationProposal).mockImplementation(
    async (request) =>
      ({
        data: emailProjection(
          request!.path.translation_group_id,
          request!.body.values[0].proposed_text,
          request!.body.expected_version + 1,
        ),
      }) as never,
  );
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
});

it("opens the selected template with protected variables and saves through the existing proposal API", async () => {
  const user = userEvent.setup();
  show();
  const field = await screen.findByRole("textbox", {
    name: "Translation · Italian",
  });
  expect(field).toHaveValue("Ciao ");
  expect(screen.getByLabelText("Protected variable: {{name}}")).toBeVisible();
  const frame = screen.getByTitle("Interactive email preview");
  expect(frame).toHaveAttribute("sandbox", "allow-same-origin");
  expect(frame.getAttribute("srcdoc")).toContain("script-src 'none'");
  await user.clear(field);
  await user.type(field, "Benvenuto ");
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  await waitFor(() => expect(saveTranslationProposal).toHaveBeenCalled());
  expect(vi.mocked(saveTranslationProposal).mock.calls[0][0]).toMatchObject({
    path: { translation_group_id: "it-body" },
    body: {
      expected_version: 0,
      values: [
        {
          translation_value_id: "it-body",
          basis_revision_number: 1,
          proposed_text: "Benvenuto {{name}}",
        },
      ],
    },
  });
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Translation saved as Draft",
  );
  await user.type(field, "ancora ");
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  await waitFor(() =>
    expect(
      vi.mocked(saveTranslationProposal).mock.calls[1][0]?.body
        .expected_version,
    ).toBe(1),
  );
});

it("guards dirty text when changing fragment, language, or project view", async () => {
  const user = userEvent.setup();
  show();
  const field = await screen.findByRole("textbox", {
    name: "Translation · Italian",
  });
  await user.type(field, "modificato ");
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByRole("alertdialog")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Keep editing" }));
  expect(field).toHaveValue("Ciao modificato ");
  await user.selectOptions(screen.getByLabelText("Translate into"), "fr");
  await user.click(
    await screen.findByRole("button", { name: "Discard changes" }),
  );
  expect(
    await screen.findByRole("textbox", { name: "Translation · French" }),
  ).toHaveValue("Hello ");
  await user.type(
    screen.getByRole("textbox", { name: "Translation · French" }),
    "changed ",
  );
  await user.selectOptions(screen.getByLabelText("Project view"), "strings");
  expect(await screen.findByRole("alertdialog")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Keep editing" }));
  expect(screen.getByLabelText("Project view")).toHaveValue("email");
  expect(
    screen.getByRole("textbox", { name: "Translation · French" }),
  ).toHaveValue("Hello changed ");
});

it("remembers a per-user per-project view and retains the existing string workflow", async () => {
  const user = userEvent.setup();
  const view = show();
  await screen.findByRole("textbox", { name: "Translation · Italian" });
  await user.selectOptions(screen.getByLabelText("Project view"), "strings");
  expect(screen.getByText("Existing string list")).toBeVisible();
  expect(loadEmailWorkspaceView("editor", "product")).toBe("strings");
  expect(loadEmailWorkspaceView("another", "product")).toBeNull();
  expect(loadEmailWorkspaceView("editor", "another")).toBeNull();
  view.unmount();
  show();
  expect(await screen.findByText("Existing string list")).toBeVisible();
});

it("allows viewers to inspect every fragment without exposing a save action", async () => {
  const user = userEvent.setup();
  show({ ...principal, roles: ["viewer"] });
  expect(await screen.findByText("Read-only translation")).toBeVisible();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Save draft" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByText("Apri account")).toBeVisible();
  expect(saveTranslationProposal).not.toHaveBeenCalled();
});

it("keeps a failed save in the editor and reconciles conflicts through the existing dialog", async () => {
  const user = userEvent.setup();
  show();
  const field = await screen.findByRole("textbox", {
    name: "Translation · Italian",
  });
  await user.type(field, "mine ");
  vi.mocked(saveTranslationProposal).mockResolvedValueOnce({
    error: { latest: emailProjection("it-body", "Server {{name}}", 3) },
    response: { status: 409 },
  } as never);
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("Server {{name}}")).toBeVisible();
  await user.click(
    within(dialog).getByRole("button", { name: "Keep editing" }),
  );
  expect(field).toHaveValue("Ciao mine ");
  vi.mocked(saveTranslationProposal).mockRejectedValueOnce(
    new Error("Unavailable"),
  );
  await user.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Translation was not saved",
  );
  expect(field).toHaveValue("Ciao mine ");
});

it("rejects a stale or foreign template response and permits a bounded retry", async () => {
  vi.mocked(getHtmlEditorDocument).mockResolvedValueOnce({
    data: { ...emailDocument(), product_id: "foreign" },
  } as never);
  const user = userEvent.setup();
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "HTML preview could not be loaded",
  );
  expect(
    screen.queryByTitle("Interactive email preview"),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Retry" }));
  expect(
    await screen.findByRole("textbox", { name: "Translation · Italian" }),
  ).toBeVisible();
});

it("ignores a late document from the previously selected language", async () => {
  let complete!: (value: unknown) => void;
  vi.mocked(getHtmlEditorDocument).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }) as never,
  );
  const user = userEvent.setup();
  show();
  await screen.findByLabelText("Translate into");
  await user.selectOptions(screen.getByLabelText("Translate into"), "fr");
  expect(
    await screen.findByRole("textbox", { name: "Translation · French" }),
  ).toBeVisible();
  await act(async () => complete({ data: emailDocument("it") }));
  expect(screen.getByLabelText("Translate into")).toHaveValue("fr");
  expect(
    screen.queryByRole("textbox", { name: "Translation · Italian" }),
  ).not.toBeInTheDocument();
});
