import "@testing-library/jest-dom/vitest";

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import {
  createMemoryRouter,
  Link,
  RouterProvider,
  useLocation,
} from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import {
  DirtyFormNavigationProvider,
  useDirtyFormNavigationGuard,
} from "./DirtyFormNavigationGuard";

afterEach(() => cleanup());

function FormRoute() {
  const [value, setValue] = useState("saved");
  const location = useLocation();
  useDirtyFormNavigationGuard("test-form", value !== "saved");

  return (
    <>
      <div data-testid="location">{location.pathname}</div>
      <label>
        Draft
        <input
          value={value}
          onChange={(event) => setValue(event.currentTarget.value)}
        />
      </label>
      <Link to="/destination-a">Destination A</Link>
      <Link to="/destination-b">Destination B</Link>
      <button type="button" onClick={() => setValue("saved")}>
        Reset draft
      </button>
      <button type="button">Programmatic trigger</button>
    </>
  );
}

function createHarness({
  initialEntries = ["/form"],
  initialIndex,
}: {
  initialEntries?: string[];
  initialIndex?: number;
} = {}) {
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <DirtyFormNavigationProvider>
            <FormRoute />
          </DirtyFormNavigationProvider>
        ),
      },
    ],
    { initialEntries, initialIndex },
  );
  render(<RouterProvider router={router} />);
  return router;
}

async function makeDirty(value = "draft byte-for-byte") {
  const user = userEvent.setup();
  const input = screen.getByRole("textbox", { name: "Draft" });
  await user.clear(input);
  await user.type(input, value);
  return { input, user };
}

async function expectDecision() {
  const dialog = await screen.findByRole("alertdialog");
  expect(dialog).toHaveTextContent("Leave without saving?");
  expect(dialog).toHaveTextContent(
    "Your unsaved entries on this page will be lost.",
  );
  expect(screen.getByRole("button", { name: "Keep editing" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Discard changes" })).toBeVisible();
}

describe("shared dirty-form router transaction", () => {
  it("lets a clean Link navigate without a decision", async () => {
    createHarness();
    await userEvent.click(screen.getByRole("link", { name: "Destination A" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/destination-a");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("blocks a dirty Link and Keep editing preserves bytes and trigger focus", async () => {
    createHarness();
    const { input, user } = await makeDirty();
    const trigger = screen.getByRole("link", { name: "Destination A" });
    await user.click(trigger);
    await expectDecision();
    expect(screen.getByTestId("location")).toHaveTextContent("/form");

    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(input).toHaveValue("draft byte-for-byte");
    expect(screen.getByTestId("location")).toHaveTextContent("/form");
  });

  it("Escape cancels the transition without changing the field", async () => {
    createHarness();
    const { input, user } = await makeDirty("unchanged after Escape");
    const trigger = screen.getByRole("link", { name: "Destination A" });
    await user.click(trigger);
    await expectDecision();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(input).toHaveValue("unchanged after Escape");
    expect(screen.getByTestId("location")).toHaveTextContent("/form");
  });

  it("discards the captured transaction once and never replays a canceled destination", async () => {
    const router = createHarness();
    const { user } = await makeDirty();

    await user.click(screen.getByRole("link", { name: "Destination A" }));
    await expectDecision();
    await user.click(screen.getByRole("button", { name: "Keep editing" }));

    await user.click(screen.getByRole("link", { name: "Destination B" }));
    await expectDecision();
    const discard = screen.getByRole("button", { name: "Discard changes" });
    await user.dblClick(discard);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/destination-b"),
    );
    expect(router.state.location.pathname).not.toBe("/destination-a");
  });

  it("consumes a captured discard transaction only once", async () => {
    const router = createHarness();
    await makeDirty();

    await userEvent.click(screen.getByRole("link", { name: "Destination A" }));
    await expectDecision();
    const discard = screen.getByRole("button", { name: "Discard changes" });
    act(() => {
      discard.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      discard.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/destination-a"),
    );
  });

  it("cancels the pending transaction when the registered form becomes clean", async () => {
    const router = createHarness();
    await makeDirty();

    await userEvent.click(screen.getByRole("link", { name: "Destination A" }));
    await expectDecision();
    fireEvent.click(screen.getByText("Reset draft"));

    await waitFor(() =>
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument(),
    );
    expect(router.state.location.pathname).toBe("/form");
  });

  it("cancels a pending transition even when no connected trigger owns focus", async () => {
    const router = createHarness();
    const { input } = await makeDirty();
    act(() => input.blur());
    expect(document.activeElement).toBe(document.body);

    await router.navigate("/destination-a");
    await expectDecision();
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() =>
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument(),
    );
    expect(router.state.location.pathname).toBe("/form");
  });

  it("blocks programmatic PUSH and POP transactions before the route changes", async () => {
    const router = createHarness({
      initialEntries: ["/history-origin", "/form"],
      initialIndex: 1,
    });
    await makeDirty();

    await router.navigate("/destination-a");
    await expectDecision();
    expect(router.state.location.pathname).toBe("/form");
    await userEvent.click(screen.getByRole("button", { name: "Keep editing" }));

    await router.navigate(-1);
    await expectDecision();
    expect(router.state.location.pathname).toBe("/form");
    await userEvent.click(
      screen.getByRole("button", { name: "Discard changes" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/history-origin"),
    );
  });

  it("prevents beforeunload only while a registered form is dirty", async () => {
    createHarness();
    const cleanExit = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(cleanExit);
    expect(cleanExit.defaultPrevented).toBe(false);

    await makeDirty();
    const dirtyExit = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirtyExit);
    expect(dirtyExit.defaultPrevented).toBe(true);
  });

  it("fails closed when a dirty-form hook is mounted outside its provider", () => {
    function UnwrappedDirtyForm() {
      useDirtyFormNavigationGuard("unwrapped", true);
      return null;
    }

    expect(() => render(<UnwrappedDirtyForm />)).toThrow(
      "useDirtyFormNavigationGuard requires DirtyFormNavigationProvider",
    );
  });
});
