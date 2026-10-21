import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ScreenshotImage } from "./ScreenshotImage";

afterEach(cleanup);
it.each(["not_found", "ambiguous", "unavailable"] as const)(
  "keeps the original image without inventing a position when %s",
  (status) => {
    render(
      <ScreenshotImage
        url="blob:synthetic"
        location={{ status, regions: [] }}
        stale={false}
      />,
    );
    expect(
      screen.getByAltText(
        "Compose screen preview with the selected translations",
      ),
    ).toHaveAttribute("src", "blob:synthetic");
    expect(
      screen.queryByRole("button", { name: "Show position" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("img", { name: "Text position in screenshot" }),
    ).not.toBeInTheDocument();
  },
);
