import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
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
});
