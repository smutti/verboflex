import "@testing-library/jest-dom/vitest";
import { useState } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { CodeSourceConfig } from "../../../api/client";
import { CodeSourceFields } from "./CodeSourceFields";

afterEach(cleanup);
it("lets administrators type multiple functions and previews without losing separators", async () => {
  const saved = vi.fn();
  function Editor() {
    const [config, setConfig] = useState<CodeSourceConfig | null>({
      resource_roots: ["Res.strings"],
      localization_calls: [],
      compose: { runner_profile: "synthetic", preview_functions: [] },
    });
    return (
      <CodeSourceFields
        value={config}
        onChange={(value) => {
          setConfig(value);
          saved(value);
        }}
      />
    );
  }
  render(<Editor />);
  const user = userEvent.setup();
  await user.type(
    screen.getByLabelText("Translation functions"),
    "translate,localize",
  );
  expect(saved.mock.lastCall?.[0].localization_calls).toEqual([
    "translate",
    "localize",
  ]);
  await user.type(
    screen.getByLabelText("Callable preview functions (one per line)"),
    "demo.HomePreview\ndemo.SettingsPreview",
  );
  expect(saved.mock.lastCall?.[0].compose.preview_functions).toEqual([
    "demo.HomePreview",
    "demo.SettingsPreview",
  ]);
});

it("configures named scenarios and clears them when capture is disabled", async () => {
  const saved = vi.fn();
  function Editor() {
    const [config, setConfig] = useState<CodeSourceConfig | null>({
      compose: {
        runner_profile: "synthetic",
        preview_functions: ["demo.RegisterPreview"],
      },
    });
    return (
      <CodeSourceFields
        value={config}
        onChange={(value) => {
          saved(value);
          setConfig(value);
        }}
      />
    );
  }
  render(<Editor />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Add scenario" }));
  await user.type(
    screen.getByLabelText("Scenario name"),
    "Registration — dialog open",
  );
  await user.selectOptions(
    screen.getByLabelText("Callable preview function"),
    "demo.RegisterPreview",
  );
  await user.type(
    screen.getByLabelText("Visible keys (one per line)"),
    "privacy_notice\nterms_notice",
  );
  expect(saved.mock.lastCall?.[0].preview_scenarios).toEqual([
    {
      preview_function: "demo.RegisterPreview",
      label: "Registration — dialog open",
      keys: ["privacy_notice", "terms_notice"],
    },
  ]);
  await user.click(
    screen.getByRole("checkbox", {
      name: "Enable on-demand Compose screenshots",
    }),
  );
  expect(saved.mock.lastCall?.[0].preview_scenarios).toEqual([]);
});
