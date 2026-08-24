import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { readHealth } from "./api/client";

vi.mock("./api/client", () => ({
  readHealth: vi.fn(),
}));

const readHealthMock = vi.mocked(readHealth);

describe("API health tracer", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    readHealthMock.mockReset();
  });

  it("renders loading while the generated health call is pending", () => {
    readHealthMock.mockReturnValue(new Promise<never>(() => undefined));

    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking API connection",
    );
    expect(readHealthMock).toHaveBeenCalledOnce();
  });

  it("renders API online for the exact healthy response", async () => {
    readHealthMock.mockResolvedValue({
      data: { status: "ok" },
      error: undefined,
    });

    render(<App />);

    expect(await screen.findByText("API online")).toHaveAttribute(
      "role",
      "status",
    );
    expect(readHealthMock).toHaveBeenCalledOnce();
  });

  it("renders sanitized API error copy and retries without raw diagnostics", async () => {
    readHealthMock.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "postgresql://db.internal:5432/verboflex" },
    });

    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "We could not reach the API. Check that the backend is running, then retry the connection.",
    );
    expect(alert).not.toHaveTextContent("db.internal");

    readHealthMock.mockReturnValueOnce(new Promise<never>(() => undefined));
    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }));

    expect(readHealthMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking API connection",
    );
  });

  it("sanitizes rejected network diagnostics", async () => {
    readHealthMock.mockRejectedValueOnce(
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
