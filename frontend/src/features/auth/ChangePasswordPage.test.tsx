import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
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
    expect(
      screen.getByText(
        "Your temporary password must be replaced before you can continue.",
      ),
    ).toBeVisible();
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

  it("announces and associates a password confirmation mismatch", async () => {
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    await user.type(
      screen.getByLabelText("Current password"),
      "temporary phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("New password"),
      "replacement phrase 2026!",
    );
    const confirmation = screen.getByLabelText("Confirm new password");
    await user.type(confirmation, "different phrase 2026!");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent("Passwords do not match.");
    expect(confirmation).toHaveAttribute("aria-invalid", "true");
    expect(confirmation).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining(error.id),
    );
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it("rejects a replacement equal to the current password", async () => {
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    const currentPassword = "same password 2026!";
    await user.type(screen.getByLabelText("Current password"), currentPassword);
    const newPassword = screen.getByLabelText("New password");
    await user.type(newPassword, currentPassword);
    await user.type(
      screen.getByLabelText("Confirm new password"),
      currentPassword,
    );
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent(
      "New password must differ from current password.",
    );
    expect(newPassword).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining(error.id),
    );
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it("submits valid replacement credentials through the restricted session action", async () => {
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    await user.type(
      screen.getByLabelText("Current password"),
      "temporary phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("New password"),
      "replacement phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "replacement phrase 2026!",
    );
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(changePasswordMock).toHaveBeenCalledOnce();
    expect(changePasswordMock).toHaveBeenCalledWith({
      currentPassword: "temporary phrase 2026!",
      newPassword: "replacement phrase 2026!",
    });
  });

  it("announces a sanitized error when password replacement is rejected", async () => {
    const reason = new Error("database.internal password policy detail");
    changePasswordMock.mockRejectedValueOnce(reason);
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    await user.type(
      screen.getByLabelText("Current password"),
      "temporary phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("New password"),
      "replacement phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "replacement phrase 2026!",
    );
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not change your password. Check the requirements and try again.",
    );
    expect(alert).not.toHaveTextContent(reason.message);
  });

  it("allows only one password replacement while the session action is pending", async () => {
    let resolveChange: (() => void) | undefined;
    changePasswordMock.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        resolveChange = resolve;
      }),
    );
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    await user.type(
      screen.getByLabelText("Current password"),
      "temporary phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("New password"),
      "replacement phrase 2026!",
    );
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "replacement phrase 2026!",
    );
    const submit = screen.getByRole("button", { name: "Set new password" });
    await user.click(submit);

    await waitFor(() => {
      expect(submit).toBeDisabled();
      expect(submit).toHaveAttribute("aria-busy", "true");
    });
    await user.click(submit);
    expect(changePasswordMock).toHaveBeenCalledOnce();

    await act(async () => {
      resolveChange?.();
    });
    await waitFor(() => expect(submit).toBeEnabled());
  });

  it("offers current, new, confirmation, then submit in logical keyboard order", async () => {
    const user = userEvent.setup();
    render(<ChangePasswordPage />);

    await user.tab();
    expect(screen.getByLabelText("Current password")).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("New password")).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Confirm new password")).toHaveFocus();
    await user.tab();
    expect(
      screen.getByRole("button", { name: "Set new password" }),
    ).toHaveFocus();
  });
});
