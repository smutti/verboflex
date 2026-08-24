import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { readHealthApiV1HealthGet } from "./api/client";

vi.mock("./api/client", () => ({
  readHealthApiV1HealthGet: vi.fn(),
}));

const readHealth = vi.mocked(readHealthApiV1HealthGet);

describe("API health tracer", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    readHealth.mockReset();
  });

  it("renders loading while the generated health call is pending", () => {
    readHealth.mockReturnValue(new Promise<never>(() => undefined));

    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking API connection",
    );
    expect(readHealth).toHaveBeenCalledOnce();
  });

  it("renders API online for the exact healthy response", async () => {
    readHealth.mockResolvedValue({
      data: { status: "ok" },
      error: undefined,
    });

    render(<App />);

    expect(await screen.findByText("API online")).toHaveAttribute(
      "role",
      "status",
    );
    expect(readHealth).toHaveBeenCalledOnce();
  });

  it("renders sanitized API error copy and retries without raw diagnostics", async () => {
    readHealth.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "postgresql://db.internal:5432/verboflex" },
    });

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not reach the API. Check that the backend is running, then retry the connection.",
    );
    expect(alert).not.toHaveTextContent("db.internal");

    readHealth.mockReturnValueOnce(new Promise<never>(() => undefined));
    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }));

    expect(readHealth).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking API connection",
    );
  });

  it("sanitizes rejected network diagnostics", async () => {
    readHealth.mockRejectedValueOnce(
      new Error("Failed to fetch postgresql://db.internal:5432/verboflex"),
    );

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not reach the API. Check that the backend is running, then retry the connection.",
    );
    expect(alert).not.toHaveTextContent("db.internal");
    expect(
      screen.getByRole("button", { name: "Retry connection" }),
    ).toBeEnabled();
  });
});
