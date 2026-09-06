import { useId } from "react";
import type { TranslationOptionsResponse } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import type { TranslationSearchFilters } from "./useTranslationSearch";
import { translationFilterLabels } from "./translationFilterLabels";

interface TranslationFiltersProps {
  filters: TranslationSearchFilters;
  options: TranslationOptionsResponse;
  disabled?: boolean;
  onChange: (filters: TranslationSearchFilters) => void;
  onClear: () => void;
}

export function TranslationFilters({
  filters,
  options,
  disabled,
  onChange,
  onClear,
}: TranslationFiltersProps) {
  const id = useId();
  const controls = [
    {
      key: "productId",
      label: "Product",
      choices: [
        ["all", "All products"],
        ...options.products.map((product) => [product.id, product.name]),
      ],
    },
    {
      key: "language",
      label: "Language",
      choices: [
        ["all", "All languages"],
        ...options.languages.map((language) => [
          language.code,
          language.label === language.code
            ? language.code
            : `${language.label} (${language.code})`,
        ]),
      ],
    },
    {
      key: "state",
      label: "Approval state",
      choices: [
        ["all", "All states"],
        ...Object.entries(translationFilterLabels.state),
      ],
    },
    {
      key: "violation",
      label: "Length status",
      choices: [
        ["all", "All length statuses"],
        ...Object.entries(translationFilterLabels.violation),
      ],
    },
    {
      key: "deleted",
      label: "Deleted status",
      choices: [...Object.entries(translationFilterLabels.deleted)],
    },
  ] as const;
  return (
    <div className="space-y-(--space-md) rounded-lg bg-secondary p-(--space-md)">
      <div className="grid min-w-0 grid-cols-1 gap-(--space-md) md:grid-cols-2 xl:grid-cols-5">
        {controls.map(({ key, label, choices }) => (
          <div key={key} className="min-w-0 space-y-(--space-sm)">
            <Label htmlFor={`${id}-${key}`}>{label}</Label>
            <Select
              disabled={disabled}
              value={filters[key] ?? "all"}
              onValueChange={(value) =>
                onChange({
                  ...filters,
                  [key]: value === "all" && key !== "deleted" ? null : value,
                })
              }
            >
              <SelectTrigger
                id={`${id}-${key}`}
                className="h-auto min-h-[44px] w-full min-w-0 whitespace-normal text-left [&_[data-slot=select-value]]:line-clamp-none [&_[data-slot=select-value]]:wrap-anywhere"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {choices.map(([value, text]) => (
                  <SelectItem
                    key={value}
                    value={value}
                    className="min-h-[44px] whitespace-normal wrap-anywhere"
                  >
                    {text}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>
      <Button
        data-clear-translation-filters
        type="button"
        variant="outline"
        className="min-h-[44px]"
        onClick={onClear}
      >
        Clear filters
      </Button>
    </div>
  );
}
