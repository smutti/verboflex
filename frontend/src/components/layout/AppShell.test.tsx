import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readSystemStatus, type CurrentUserResponse } from "../../api/client";
import { AppShell } from "./AppShell";

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return {
    ...original,
    readSystemStatus: vi.fn(),
  };
});

const readSystemStatusMock = vi.mocked(readSystemStatus);

const principal: CurrentUserResponse = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person Example",
  roles: ["admin", "product_manager_reviewer", "translator", "viewer"],
  must_change_password: false,
};

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  readSystemStatusMock.mockReset();
  readSystemStatusMock.mockReturnValue(new Promise<never>(() => undefined));
});

describe("authenticated application shell", () => {
  it("shows server identity, human role labels, and the approved neutral workspace copy", () => {
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Workspace overview", level: 1 }),
    ).toBeVisible();
    expect(screen.getByText("Person Example")).toBeVisible();
    expect(screen.getByText("person@example.com")).toBeVisible();
    expect(screen.getByText("Administrator")).toBeVisible();
    expect(screen.getByText("Product manager / reviewer")).toBeVisible();
    expect(screen.getByText("Translator")).toBeVisible();
    expect(screen.getByText("Viewer")).toBeVisible();
    expect(
      screen.getByText(
        "Your review workspace will appear here as products and repositories are configured.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Workspace ready for configuration",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Phase 1 confirms the platform shell, session, and services. Product and translation workflows will appear after configuration is added.",
      ),
    ).toBeVisible();
  });

  it("announces a bounded loading state while generated service status is pending", () => {
    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking service status",
    );
    expect(readSystemStatusMock).toHaveBeenCalledWith({
      auth: "ordinary-server-token",
    });
  });

  it("renders every server service enum as an explicit text label", async () => {
    readSystemStatusMock.mockResolvedValue({
      data: {
        api: "online",
        database: "online",
        redis: "unavailable",
        worker: "pending",
        checked_at: "2026-08-24T20:10:00Z",
      },
      error: undefined,
    });

    render(
      <AppShell
        accessToken="ordinary-server-token"
        onLogout={vi.fn()}
        principal={principal}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Service status" }),
    ).toBeVisible();
    expect(screen.getByText("API online")).toBeVisible();
    expect(screen.getByText("Database online")).toBeVisible();
    expect(screen.getByText("Redis unavailable")).toBeVisible();
    expect(screen.getByText("Worker pending")).toBeVisible();
    expect(screen.queryByText("Checking service status")).not.toBeInTheDocument();
  });
});
