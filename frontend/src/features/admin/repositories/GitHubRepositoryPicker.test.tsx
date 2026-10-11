import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  connectAdminGithubRepository,
  getAdminRepository,
} from "../../../api/client";
import { GitHubRepositoryPicker } from "./GitHubRepositoryPicker";

vi.mock("../../../api/client", () => ({
  connectAdminGithubRepository: vi.fn(),
  getAdminRepository: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const repository = {
  id: "repo-1",
  provider: "github" as const,
  workspace: "owner",
  repository_slug: "app",
  descriptive_name: "owner/app",
  default_branch: "main",
  stars: 1500,
  language: "Kotlin",
  html_url: "https://github.com/owner/app",
  import_only: true,
};

describe("GitHub public repository connection", () => {
  it("restores a previously selected GitHub repository without querying GitHub", async () => {
    vi.mocked(getAdminRepository).mockResolvedValue({
      data: repository,
      request: new Request("http://localhost"),
      response: new Response(),
      error: undefined,
    });
    render(
      <GitHubRepositoryPicker
        accessToken="session"
        selectedRepositoryIds={[repository.id]}
      />,
    );
    expect(await screen.findByText("owner/app")).toBeVisible();
    expect(connectAdminGithubRepository).not.toHaveBeenCalled();
  });
  it("accepts a GitHub URL and exposes the verified repository to the wizard", async () => {
    const user = userEvent.setup();
    vi.mocked(connectAdminGithubRepository).mockResolvedValue({
      data: repository,
      request: new Request("http://localhost"),
      response: new Response(),
      error: undefined,
    });
    const selected = vi.fn();
    render(
      <GitHubRepositoryPicker
        accessToken="session"
        onRepositorySelected={selected}
      />,
    );
    await user.type(
      screen.getByLabelText("Repository GitHub"),
      "https://github.com/owner/app",
    );
    await user.click(
      screen.getByRole("button", { name: "Collega repository GitHub" }),
    );
    expect(await screen.findByText("owner/app")).toBeVisible();
    expect(screen.getByText("GitHub · Importazione")).toBeVisible();
    expect(screen.getByText("Kotlin")).toBeVisible();
    expect(selected).toHaveBeenCalledWith(repository);
    expect(connectAdminGithubRepository).toHaveBeenCalledWith(
      expect.objectContaining({
        auth: "session",
        body: { owner: "owner", repository: "app" },
      }),
    );
  });

  it("rejects foreign URLs before making a provider request", async () => {
    const user = userEvent.setup();
    render(<GitHubRepositoryPicker accessToken="session" />);
    await user.type(
      screen.getByLabelText("Repository GitHub"),
      "https://github.com.evil.test/owner/app",
    );
    await user.click(
      screen.getByRole("button", { name: "Collega repository GitHub" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Inserisci owner/repository",
    );
    expect(connectAdminGithubRepository).not.toHaveBeenCalled();
  });

  it("shows a recoverable rate limit without discarding input or selecting a repository", async () => {
    const user = userEvent.setup();
    vi.mocked(connectAdminGithubRepository).mockResolvedValue({
      data: undefined,
      error: { detail: "rate limited" },
      request: new Request("http://localhost"),
      response: new Response(null, { status: 429 }),
    });
    const selected = vi.fn();
    render(
      <GitHubRepositoryPicker
        accessToken="session"
        onRepositorySelected={selected}
      />,
    );
    await user.type(screen.getByLabelText("Repository GitHub"), "owner/app");
    await user.click(
      screen.getByRole("button", { name: "Collega repository GitHub" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "limite di richieste pubbliche",
    );
    expect(screen.getByLabelText("Repository GitHub")).toHaveValue("owner/app");
    expect(selected).not.toHaveBeenCalled();
  });
});
