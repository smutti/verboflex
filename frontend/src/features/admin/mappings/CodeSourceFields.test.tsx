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
