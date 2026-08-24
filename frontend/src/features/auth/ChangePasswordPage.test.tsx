import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChangePasswordPage } from "./ChangePasswordPage";
import { useSession } from "./session";

vi.mock("./session", () => ({
  useSession: vi.fn(),
}));

const changePasswordMock = vi.fn();
const useSessionMock = vi.mocked(useSession);

describe("required password change page", () => {
  beforeEach(() => {
    changePasswordMock.mockReset();
    changePasswordMock.mockResolvedValue(undefined);
    useSessionMock.mockReturnValue({
      state: {
        status: "password_change_required",
        accessToken: "restricted-server-token",
      },
      login: vi.fn(),
      changePassword: changePasswordMock,
      restoreSession: vi.fn(),
      logout: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("exposes approved copy, field labels, and associated password requirements", () => {
    render(<ChangePasswordPage />);

    expect(
      screen.getByRole("heading", { name: "Set a new password" }),
    ).toBeVisible();
    expect(screen.getByText(
      "Your temporary password must be replaced before you can continue.",
    )).toBeVisible();
    expect(screen.getByLabelText("Current password")).toHaveAttribute(
      "type",
      "password",
    );
    const newPassword = screen.getByLabelText("New password");
    expect(newPassword).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Confirm new password")).toHaveAttribute(
      "type",
      "password",
    );
    const requirements = screen.getByText(
      "Use 12 to 128 characters. Spaces and Unicode characters are allowed.",
    );
    expect(newPassword).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining(requirements.id),
    );
    expect(
      screen.getByRole("button", { name: "Set new password" }),
    ).toBeEnabled();
  });

  it("announces and associates the 12-to-128-character requirement", async () => {
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    await user.type(
      screen.getByLabelText("Current password"),
      "temporary phrase 2026!",
    );
    const newPassword = screen.getByLabelText("New password");
    await user.type(newPassword, "too short");
    await user.type(screen.getByLabelText("Confirm new password"), "too short");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent(
      "Password must contain 12 to 128 characters.",
    );
    expect(newPassword).toHaveAttribute("aria-invalid", "true");
    expect(newPassword).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining(error.id),
    );
    expect(changePasswordMock).not.toHaveBeenCalled();
  });
});
