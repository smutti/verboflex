import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
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
});
