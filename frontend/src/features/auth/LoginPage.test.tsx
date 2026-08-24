import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";
import { useSession } from "./session";

vi.mock("./session", () => ({
  useSession: vi.fn(),
}));

const loginMock = vi.fn();
const useSessionMock = vi.mocked(useSession);

describe("login page", () => {
  beforeEach(() => {
    loginMock.mockReset();
    loginMock.mockResolvedValue(undefined);
    useSessionMock.mockReturnValue({
      state: { status: "signed_out" },
      login: loginMock,
      changePassword: vi.fn(),
      restoreSession: vi.fn(),
      logout: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("exposes the approved copy and programmatic field labels", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "VerboFlex" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Email" })).toHaveAttribute(
      "type",
      "email",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
    expect(
      screen.getByRole("button", { name: "Sign in to VerboFlex" }),
    ).toBeEnabled();
  });

  it("submits the entered corporate email and password through the session action", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByRole("textbox", { name: "Email" }),
      "person@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "secure phrase 2026!");
    await user.click(
      screen.getByRole("button", { name: "Sign in to VerboFlex" }),
    );

    expect(loginMock).toHaveBeenCalledOnce();
    expect(loginMock).toHaveBeenCalledWith({
      email: "person@example.com",
      password: "secure phrase 2026!",
    });
  });

  it.each([
    new Error("401 unknown account"),
    new Error("Failed to fetch https://api.internal/auth/token"),
  ])("shows the same non-enumerating error for rejected login", async (reason) => {
    loginMock.mockRejectedValueOnce(reason);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByRole("textbox", { name: "Email" }),
      "person@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "wrong phrase 2026!");
    await user.click(
      screen.getByRole("button", { name: "Sign in to VerboFlex" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not sign you in. Check your email and password, then try again.",
    );
    expect(alert).not.toHaveTextContent(reason.message);
  });
});
