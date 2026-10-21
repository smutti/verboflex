import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HtmlTemplatePreview } from "./HtmlTemplatePreview";

const api = vi.hoisted(() => ({ getHtmlTemplatePreview: vi.fn() }));
vi.mock("@/api/client", () => api);
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("escapes edited text and sandboxes the imported template", async () => {
  api.getHtmlTemplatePreview.mockResolvedValue({
    data: {
      document:
        "<html><body><p><!--SELECTED--></p><script>alert(1)</script></body></html>",
      marker: "<!--SELECTED-->",
      path: "mail/Welcome-FR-BE.html",
    },
  });
  const view = render(
    <HtmlTemplatePreview
      accessToken="token"
      groupId="group"
      text={"<img src=x> & {{name}}"}
    />,
  );
  const frame = await screen.findByTitle("HTML template preview");
  expect(frame).toHaveAttribute("sandbox", "");
  expect(frame).toHaveAttribute("referrerpolicy", "no-referrer");
  expect(frame.getAttribute("srcdoc")).toContain("default-src 'none'");
  expect(frame.getAttribute("srcdoc")).toContain(
    "&lt;img src=x&gt; &amp; {{name}}",
  );
  expect(frame.getAttribute("srcdoc")).not.toContain("<img src=x>");
  api.getHtmlTemplatePreview.mockReturnValue(new Promise(() => {}));
  view.rerender(
    <HtmlTemplatePreview accessToken="token" groupId="other" text="Other" />,
  );
  expect(screen.queryByTitle("HTML template preview")).not.toBeInTheDocument();
});
