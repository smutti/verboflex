import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readSystemStatus } from "./api/client";
import { App } from "./App";
import { useSession } from "./features/auth/session";

vi.mock("./api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api/client")>();
  return {
    ...original,
    readSystemStatus: vi.fn(),
  };
});

vi.mock("./features/auth/session", () => ({
  useSession: vi.fn(),
}));

const readSystemStatusMock = vi.mocked(readSystemStatus);
const useSessionMock = vi.mocked(useSession);

const principal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person Example",
  roles: ["translator" as const],
  must_change_password: false,
};

describe("authenticated application entry", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    readSystemStatusMock.mockReset();
    readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
    useSessionMock.mockReset();
  });

  it("renders the shell only from an authenticated session principal", () => {
    useSessionMock.mockReturnValue({
      state: {
        status: "authenticated",
        accessToken: "ordinary-memory-token",
        principal,
      },
      login: vi.fn(),
      changePassword: vi.fn(),
      restoreSession: vi.fn(),
      logout: vi.fn(),
    });

    render(<App />);

    expect(screen.getByRole("heading", { name: "Workspace" })).toBeVisible();
    expect(screen.getByText("Person Example")).toBeVisible();
    expect(readSystemStatusMock).toHaveBeenCalledWith({
      auth: "ordinary-memory-token",
    });
  });

  it("fails closed when rendered outside ordinary authenticated authority", () => {
    useSessionMock.mockReturnValue({
      state: { status: "signed_out" },
      login: vi.fn(),
      changePassword: vi.fn(),
      restoreSession: vi.fn(),
      logout: vi.fn(),
    });

    const { container } = render(<App />);

    expect(container).toBeEmptyDOMElement();
    expect(readSystemStatusMock).not.toHaveBeenCalled();
  });
});
