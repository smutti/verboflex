import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { HtmlTemplatePreview } from "./HtmlTemplatePreview";

import userEvent from "@testing-library/user-event";

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});
const api = vi.hoisted(() => ({ getHtmlTemplatePreview: vi.fn() }));
vi.mock("@/api/client", () => api);
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
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
  expect(frame).toBeVisible();
  expect(frame.closest("details")).toBeNull();
  expect(frame.getAttribute("srcdoc")).toContain("data-verboflex-selected");
  view.rerender(
    <HtmlTemplatePreview accessToken="token" groupId="group" text="Updated" />,
  );
  expect(frame.getAttribute("srcdoc")).toContain(">Updated</mark>");
  expect(api.getHtmlTemplatePreview).toHaveBeenCalledTimes(1);
  api.getHtmlTemplatePreview.mockReturnValue(new Promise(() => {}));
  view.rerender(
    <HtmlTemplatePreview accessToken="token" groupId="other" text="Other" />,
  );
  expect(screen.queryByTitle("HTML template preview")).not.toBeInTheDocument();
});

it("shows failures and retries without blocking text editing", async () => {
  api.getHtmlTemplatePreview.mockRejectedValueOnce(new Error("Unavailable"));
  render(
    <HtmlTemplatePreview accessToken="token" groupId="group" text="Hello" />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Loading HTML template");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "HTML preview could not be loaded",
  );
  api.getHtmlTemplatePreview.mockResolvedValueOnce({
    data: {
      document: "<html><body><!--SELECTED--></body></html>",
      marker: "<!--SELECTED-->",
      path: "Hello-EN.html",
    },
  });
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByTitle("HTML template preview")).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("discards previews when the session changes and ignores late responses", async () => {
  let resolve!: (result: unknown) => void;
  api.getHtmlTemplatePreview.mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const view = render(
    <HtmlTemplatePreview accessToken="old" groupId="group" text="Old" />,
  );
  api.getHtmlTemplatePreview.mockResolvedValueOnce({
    data: {
      document: "<html><body><!--NEW--></body></html>",
      marker: "<!--NEW-->",
      path: "New-EN.html",
    },
  });
  view.rerender(
    <HtmlTemplatePreview accessToken="new" groupId="group" text="Current" />,
  );
  const frame = await screen.findByTitle("HTML template preview");
  resolve({
    data: {
      document: "<html><!--OLD--></html>",
      marker: "<!--OLD-->",
      path: "Old-EN.html",
    },
  });
  await waitFor(() =>
    expect(frame.getAttribute("srcdoc")).toContain("Current"),
  );
  expect(screen.queryByText("Old-EN.html")).not.toBeInTheDocument();
  api.getHtmlTemplatePreview.mockReturnValueOnce(new Promise(() => {}));
  view.rerender(
    <HtmlTemplatePreview accessToken="third" groupId="group" text="Current" />,
  );
  expect(screen.queryByTitle("HTML template preview")).not.toBeInTheDocument();
});

it("shows document titles without injecting highlight markup into the title", async () => {
  api.getHtmlTemplatePreview.mockResolvedValue({
    data: {
      document:
        "<html><head><title><!--SELECTED--></title></head><body>Email body</body></html>",
      marker: "<!--SELECTED-->",
      path: "Hello-EN.html",
    },
  });
  render(
    <HtmlTemplatePreview
      accessToken="token"
      groupId="group"
      text="Hello & welcome"
    />,
  );
  const frame = await screen.findByTitle("HTML template preview");
  expect(frame.getAttribute("srcdoc")).toContain(
    "<title>Hello &amp; welcome</title>",
  );
  expect(frame.getAttribute("srcdoc")).not.toContain("<mark");
  expect(screen.getByText("Hello & welcome")).toBeVisible();
});
