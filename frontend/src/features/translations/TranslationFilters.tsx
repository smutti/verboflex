import { useId, useState, type ReactNode } from "react";
import { Filter, Languages, Rows3, Columns2, X } from "lucide-react";
import type { TranslationOptionsResponse } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { SearchableSelect } from "../../components/ui/searchable-select";
import { Input } from "../../components/ui/input";
import type { TranslationSearchFilters } from "./useTranslationSearch";
import { translationFilterLabels } from "./translationFilterLabels";
import { coherentTranslationSelection } from "./translationPreferences";

interface TranslationFiltersProps {
  filters: TranslationSearchFilters;
  options: TranslationOptionsResponse;
  visibleLanguages?: readonly string[];
  availableLanguages?: readonly string[];
  baseLanguage?: string | null;
  defaultSelectionCapped?: boolean;
  availableLanguagesTruncated?: boolean;
  searchControl?: ReactNode;
  disabled?: boolean;
  hideProduct?: boolean;
  onChange: (filters: TranslationSearchFilters) => void;
  onClear: () => void;
}

function languageLabel(code: string, label: string) {
  if (label !== code) return label;
  try {
    return new Intl.DisplayNames(["en"], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}

export function TranslationFilters({
  filters,
  options,
  visibleLanguages = filters.visibleLanguages ?? [],
  availableLanguages,
  baseLanguage,
  availableLanguagesTruncated,
  searchControl,
  disabled,
  hideProduct = false,
  onChange,
  onClear,
}: TranslationFiltersProps) {
  const id = useId();
  const [filterOpen, setFilterOpen] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);
  const [draft, setDraft] = useState(filters);
  const [languageDraft, setLanguageDraft] = useState<string[]>([]);
  const [languageQuery, setLanguageQuery] = useState("");
  const languages = options.languages
    .filter(
      ({ code }) => !availableLanguages || availableLanguages.includes(code),
    )
    .map(({ code, label }) => ({ code, label: languageLabel(code, label) }));
  const controls = [
    {
      key: "productId",
      label: "Product",
      choices: [
        ["all", "All products"],
        ...options.products.map((p) => [p.id, p.name]),
      ],
    },
    {
      key: "language",
      label: "Matching language",
      choices: [
        ["all", "All selected languages"],
        ...languages.map((l) => [
          l.code,
          l.label === l.code ? l.code : l.label + " (" + l.code + ")",
        ]),
      ],
    },
    {
      key: "workStatus",
      label: "Work queue",
      choices: [
        ["all", "All entries"],
        ...Object.entries(translationFilterLabels.workStatus),
      ],
    },
    {
      key: "state",
      label: "Imported approval state",
      choices: [
        ["all", "Any state"],
        ...Object.entries(translationFilterLabels.state),
      ],
    },
    {
      key: "violation",
      label: "Imported length status",
      choices: [
        ["all", "Any length"],
        ...Object.entries(translationFilterLabels.violation),
      ],
    },
    {
      key: "deleted",
      label: "Deleted status",
      choices: Object.entries(translationFilterLabels.deleted),
    },
  ] as const;
  const chips: {
    key: keyof TranslationSearchFilters;
    label: string;
    reset: string | null;
  }[] = [];
  if (!hideProduct && filters.productId)
    chips.push({
      key: "productId",
      label:
        "Product: " +
        (options.products.find((p) => p.id === filters.productId)?.name ??
          filters.productId),
      reset: null,
    });
  if (filters.language)
    chips.push({
      key: "language",
      label: "Matching language: " + filters.language,
      reset: null,
    });
  if (filters.workStatus)
    chips.push({
      key: "workStatus",
      label: translationFilterLabels.workStatus[filters.workStatus],
      reset: null,
    });
  if (filters.state)
    chips.push({
      key: "state",
      label: "Imported state: " + translationFilterLabels.state[filters.state],
      reset: null,
    });
  if (filters.violation)
    chips.push({
      key: "violation",
      label:
        "Imported length: " +
        translationFilterLabels.violation[filters.violation],
      reset: null,
    });
  if (filters.deleted !== "active")
    chips.push({
      key: "deleted",
      label: translationFilterLabels.deleted[filters.deleted],
      reset: "active",
    });
  const accept = (next: TranslationSearchFilters) => {
    setFilterOpen(false);
    setLanguageOpen(false);
    onChange(
      coherentTranslationSelection(
        filters.language && !next.language
          ? { ...next, viewMode: "multilingual" }
          : next,
        languages.map(({ code }) => code),
        next.visibleLanguages ?? visibleLanguages,
        baseLanguage ? [baseLanguage] : [],
      ),
    );
  };
  return (
    <div className="min-w-0 space-y-2">
      <div
        className="flex min-w-0 flex-wrap items-center gap-2"
        aria-label="Translation toolbar"
      >
        {searchControl}
        <Dialog
          open={filterOpen}
          onOpenChange={(open) => {
            if (open) setDraft(filters);
            setFilterOpen(open);
          }}
        >
          <DialogTrigger asChild>
            <Button
              variant="outline"
              disabled={disabled}
              className="min-h-[44px]"
            >
              <Filter aria-hidden="true" />
              Filter{chips.length ? " (" + chips.length + ")" : ""}
            </Button>
          </DialogTrigger>
          <DialogContent
            className="max-h-[85dvh] overflow-y-auto [&_button]:min-h-[44px] [&_[data-slot=dialog-close]]:min-w-[44px]"
            onEscapeKeyDown={(event) => {
              if (
                event.target instanceof Element &&
                event.target.matches('[role="combobox"][aria-expanded="true"]')
              )
                event.preventDefault();
            }}
          >
            <DialogTitle>Filter translations</DialogTitle>
            <DialogDescription>
              One language must match all filters.
            </DialogDescription>
            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="Translation work queue"
            >
              {(
                [
                  [null, "All"],
                  ["needs_translation", "Needs translation"],
                  ["needs_review", "Needs review"],
                  ["source_changed", "Source changed"],
                ] as const
              ).map(([value, label]) => (
                <Button
                  key={value ?? "all"}
                  variant="outline"
                  className="min-h-[44px]"
                  aria-pressed={(filters.workStatus ?? null) === value}
                  onClick={() => accept({ ...filters, workStatus: value })}
                >
                  {label}
                </Button>
              ))}
            </div>
            <div className="grid min-w-0 gap-3 sm:grid-cols-2">
              {controls
                .filter((c) => !hideProduct || c.key !== "productId")
                .map(({ key, label, choices }) => (
                  <div key={key} className="min-w-0 space-y-1">
                    <Label htmlFor={id + "-" + key}>{label}</Label>
                    <SearchableSelect
                      id={id + "-" + key}
                      value={draft[key] ?? "all"}
                      options={choices.map(([value, text]) => ({
                        value,
                        label: text,
                      }))}
                      onValueChange={(value) =>
                        setDraft({
                          ...draft,
                          [key]:
                            value === "all" && key !== "deleted" ? null : value,
                        })
                      }
                    />
                  </div>
                ))}
            </div>
            <p className="text-sm text-muted-foreground">
              State and length use imported values; review uses drafts.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setFilterOpen(false)}>
                Cancel
              </Button>
              <Button onClick={() => accept(draft)}>Apply filters</Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog
          open={languageOpen}
          onOpenChange={(open) => {
            if (open) {
              setLanguageDraft([...visibleLanguages]);
              setLanguageQuery("");
            }
            setLanguageOpen(open);
          }}
        >
          <DialogTrigger asChild>
            <Button
              variant="outline"
              disabled={disabled}
              className="min-h-[44px]"
            >
              <Languages aria-hidden="true" />
              Languages ({visibleLanguages.length})
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[85dvh] overflow-y-auto [&_button]:min-h-[44px] [&_[data-slot=dialog-close]]:min-w-[44px]">
            <DialogTitle>Visible languages</DialogTitle>
            <DialogDescription className="sr-only">
              Select up to 20 languages.
            </DialogDescription>
            <p
              className="text-sm text-muted-foreground"
              aria-label="Languages selected"
            >
              {languageDraft.length}/20
            </p>
            {availableLanguagesTruncated && (
              <p className="text-sm">Select a product for more languages.</p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={languages.length > 20}
                onClick={() => setLanguageDraft(languages.map((l) => l.code))}
              >
                Select all
              </Button>
              <Button variant="outline" onClick={() => setLanguageDraft([])}>
                Clear selection
              </Button>
              <Button
                variant="outline"
                onClick={() => accept({ ...filters, visibleLanguages: null })}
              >
                Use default languages
              </Button>
            </div>
            <Input
              aria-label="Search languages"
              placeholder="Search languages"
              value={languageQuery}
              onChange={(event) => setLanguageQuery(event.target.value)}
            />
            <div className="max-h-64 overflow-y-auto">
              {languages
                .filter(({ code, label }) =>
                  `${label} ${code}`
                    .toLocaleLowerCase()
                    .includes(languageQuery.trim().toLocaleLowerCase()),
                )
                .map(({ code, label }) => (
                  <label
                    key={code}
                    className="flex min-h-[44px] items-center gap-3 rounded px-2 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      className="size-4"
                      aria-label={
                        label === code ? code : label + " (" + code + ")"
                      }
                      checked={languageDraft.includes(code)}
                      disabled={
                        !languageDraft.includes(code) &&
                        languageDraft.length >= 20
                      }
                      onChange={(event) =>
                        setLanguageDraft(
                          event.target.checked
                            ? [...languageDraft, code]
                            : languageDraft.filter((l) => l !== code),
                        )
                      }
                    />
                    <span>
                      {label === code ? code : label + " (" + code + ")"}
                    </span>
                    {baseLanguage && (
                      <span className="ml-auto text-xs text-muted-foreground">
                        {code === baseLanguage ? "Base / source" : "Target"}
                      </span>
                    )}
                  </label>
                ))}
            </div>
            {!languages.some(({ code, label }) =>
              `${label} ${code}`
                .toLocaleLowerCase()
                .includes(languageQuery.trim().toLocaleLowerCase()),
            ) && (
              <p role="status" className="text-sm text-muted-foreground">
                No results
              </p>
            )}
            {languageDraft.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Select a language.
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setLanguageOpen(false)}>
                Cancel
              </Button>
              <Button
                disabled={!languageDraft.length}
                onClick={() =>
                  accept({ ...filters, visibleLanguages: languageDraft })
                }
              >
                Apply languages
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        <div role="group" aria-label="Translation view" className="flex gap-1">
          {(["multilingual", "bilingual"] as const).map((mode) => (
            <Button
              key={mode}
              disabled={disabled}
              className="min-h-[44px]"
              variant={
                (filters.viewMode ?? "multilingual") === mode
                  ? "default"
                  : "ghost"
              }
              aria-pressed={(filters.viewMode ?? "multilingual") === mode}
              onClick={() =>
                accept({
                  ...filters,
                  viewMode: mode,
                  visibleLanguages:
                    mode === "multilingual"
                      ? null
                      : (filters.visibleLanguages ?? [...visibleLanguages]),
                })
              }
            >
              {mode === "multilingual" ? (
                <Rows3 aria-hidden="true" />
              ) : (
                <Columns2 aria-hidden="true" />
              )}
              {mode === "multilingual" ? "Multilingual" : "Bilingual"}
            </Button>
          ))}
        </div>
      </div>
      <div
        className="flex flex-wrap items-center gap-1"
        aria-label="Active filters"
      >
        {chips.map((chip) => (
          <Button
            key={chip.key}
            variant="outline"
            size="sm"
            className="min-h-[44px] max-w-full whitespace-normal"
            aria-label={"Remove " + chip.label}
            onClick={() => accept({ ...filters, [chip.key]: chip.reset })}
          >
            {chip.label}
            <X className="size-3" aria-hidden="true" />
          </Button>
        ))}
        <Button
          data-clear-translation-filters
          type="button"
          variant="ghost"
          size="sm"
          className="min-h-[44px]"
          onClick={onClear}
        >
          Clear filters
        </Button>
      </div>
    </div>
  );
}
