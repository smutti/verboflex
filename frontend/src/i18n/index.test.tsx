import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProfilePage } from "../features/auth/ProfilePage";
import { TranslationStatusBadge } from "../features/translations/TranslationStatusBadge";
import { translationFilterLabels } from "../features/translations/translationFilterLabels";
import { LanguagePicker } from "./LanguagePicker";
import {
  UI_LANGUAGES,
  UI_LANGUAGE_STORAGE_KEY,
  displayLanguage,
  getUiLanguage,
  initializeUiLanguage,
  resolveUiLanguage,
  setUiLanguage,
  t,
  useUiLanguage,
} from ".";

vi.mock("../features/auth/session", () => ({
  useSession: () => ({ changePassword: vi.fn() }),
}));

beforeEach(() => {
  setUiLanguage("en");
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  setUiLanguage("en");
  localStorage.clear();
});

describe("interface language preference", () => {
  it.each([
    [null, ["it-IT"], "it"],
    [null, ["en-US"], "en"],
    [null, ["de-CH"], "de"],
    [null, ["es-MX"], "es"],
    [null, ["fr-CA"], "fr"],
    [null, ["nl-BE"], "nl"],
    [null, ["ja-JP"], "en"],
    [null, [], "en"],
    [null, ["ja", "fr-CA"], "fr"],
    ["nl", ["it"], "nl"],
    ["invalid", ["DE_at"], "de"],
    ["__proto__", ["ja"], "en"],
  ] as const)(
    "resolves saved %s and browser %j to %s",
    (saved, preferred, expected) => {
      expect(resolveUiLanguage(saved, preferred)).toBe(expected);
    },
  );

  it("detects the browser until a manual preference is saved", () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["it-IT"]);
    initializeUiLanguage();
    expect(getUiLanguage()).toBe("it");
    expect(localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBeNull();
    setUiLanguage("de");
    initializeUiLanguage();
    expect(getUiLanguage()).toBe("de");
    expect(document.documentElement.lang).toBe("de");
    expect(document.documentElement.className).not.toContain("translate-yes");
  });

  it("works when browser storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("disabled");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("disabled");
    });
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["fr-CA"]);
    expect(() => initializeUiLanguage()).not.toThrow();
    expect(getUiLanguage()).toBe("fr");
    expect(() => setUiLanguage("es")).not.toThrow();
    expect(document.documentElement.lang).toBe("es");
  });

  it("synchronizes a preference from another tab, ignoring unrelated and session storage", () => {
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["it"]);
    render(<LanguagePicker />);
    fireEvent(
      window,
      new StorageEvent("storage", {
        key: UI_LANGUAGE_STORAGE_KEY,
        newValue: "de",
        storageArea: localStorage,
      }),
    );
    expect(
      screen.getByRole("button", { name: "Oberflächensprache: Deutsch" }),
    ).toBeInTheDocument();
    fireEvent(
      window,
      new StorageEvent("storage", {
        key: "other",
        newValue: "nl",
        storageArea: localStorage,
      }),
    );
    fireEvent(
      window,
      new StorageEvent("storage", {
        key: UI_LANGUAGE_STORAGE_KEY,
        newValue: "nl",
        storageArea: sessionStorage,
      }),
    );
    expect(getUiLanguage()).toBe("de");
    fireEvent(
      window,
      new StorageEvent("storage", {
        key: UI_LANGUAGE_STORAGE_KEY,
        newValue: null,
        storageArea: localStorage,
      }),
    );
    expect(getUiLanguage()).toBe("it");
  });
});

it("updates the real profile, roles and validation messages without remounting password fields", async () => {
  const user = userEvent.setup();
  render(
    <ProfilePage
      principal={{
        id: "synthetic-user",
        display_name: "MUG Demo",
        email: "reader@example.test",
        roles: ["viewer"],
        must_change_password: false,
      }}
    />,
  );
  const current = screen.getByLabelText("Current password");
  const next = screen.getByLabelText("New password");
  await user.type(current, "synthetic-current-password");
  await user.type(next, "short");
  await user.click(screen.getByRole("button", { name: "Change password" }));
  expect(
    screen.getByText("Password must contain 12 to 128 characters."),
  ).toBeVisible();
  act(() => setUiLanguage("it"));
  expect(screen.getByRole("heading", { name: "Profilo" })).toBeVisible();
  expect(screen.getByText("Lettore", { exact: true })).toBeVisible();
  expect(screen.getByLabelText("Password attuale")).toBe(current);
  expect(current).toHaveValue("synthetic-current-password");
  expect(next).toHaveValue("short");
  expect(
    screen.queryByText("Password must contain 12 to 128 characters."),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(t("Password must contain 12 to 128 characters.")),
  ).toBeVisible();
  expect(screen.getByText("MUG Demo", { exact: true })).toBeVisible();
});

it.each(UI_LANGUAGES)(
  "preserves Git branch identifiers and review behavior in $name",
  ({ code }) => {
    setUiLanguage(code);
    const { rerender } = render(
      <TranslationStatusBadge
        proposal={{
          state: "approved",
          target_branch: "master",
          target_integrated: false,
        }}
      />,
    );
    expect(screen.getByText(t("Approved"), { exact: true })).toBeVisible();
    expect(
      screen.getByText(`${t("Awaiting")} master`, { exact: true }),
    ).toBeVisible();
    rerender(
      <TranslationStatusBadge
        proposal={{
          state: "approved",
          target_branch: "master",
          target_integrated: true,
        }}
      />,
    );
    expect(
      screen.queryByText(t("Approved"), { exact: true }),
    ).not.toBeInTheDocument();
  },
);

it("translates live lookup labels and escapes interpolated data as React text", () => {
  function Copy() {
    useUiLanguage();
    return (
      <p>
        {t("Open user menu for {{v0}}", {
          v0: '<img src=x onerror="alert(1)">',
        })}
      </p>
    );
  }
  const { container } = render(<Copy />);
  act(() => setUiLanguage("it"));
  expect(container.textContent).toBe(
    'Apri menu utente per <img src=x onerror="alert(1)">',
  );
  expect(container.querySelector("img")).toBeNull();
  expect(translationFilterLabels.workStatus.needs_translation).toBe(
    "Da tradurre",
  );
  expect(displayLanguage("fr")).toBe("francese");
  expect(displayLanguage("not_a_tag", "original")).toBe("original");
  expect(t(" Unknown source copy ")).toBe(" Unknown source copy ");
  expect(t("  ")).toBe("  ");
});
