import { t, useUiLanguage } from "@/i18n";
import type { CodeSourceConfig } from "../../../api/client";
import { useState, type ChangeEvent, type FocusEvent } from "react";
import { Checkbox } from "../../../components/ui/checkbox";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";

const symbols = (value: string) =>
  value
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);

function SymbolField({
  label,
  values,
  placeholder,
  multiline = false,
  onChange,
}: {
  label: string;
  values: string[];
  placeholder: string;
  multiline?: boolean;
  onChange: (values: string[]) => void;
}) {
  useUiLanguage();
  // Preserve separators while typing; the parent still receives every edit.
  const [editing, setEditing] = useState<string | null>(null);
  const props = {
    value: editing ?? values.join(multiline ? "\n" : ", "),
    placeholder,
    onFocus: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setEditing(e.target.value),
    onBlur: () => setEditing(null),
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setEditing(e.target.value);
      onChange(symbols(e.target.value));
    },
  };
  return (
    <Label className="grid gap-2">
      {label}
      {multiline ? (
        <textarea
          {...props}
          className="min-h-24 rounded-md border p-2 text-sm"
        />
      ) : (
        <Input {...props} />
      )}
    </Label>
  );
}

export function CodeSourceFields({
  value,
  onChange,
}: {
  value: CodeSourceConfig | null;
  onChange: (value: CodeSourceConfig | null) => void;
}) {
  useUiLanguage();
  return (
    <fieldset className="space-y-4 rounded-md border p-4">
      <legend className="text-sm font-semibold">
        {t("Keys defined in Kotlin or Java")}
      </legend>
      <Label className="flex gap-2">
        <Checkbox
          checked={value !== null}
          onCheckedChange={(checked) =>
            onChange(
              checked
                ? {
                    resource_roots: ["Res.strings"],
                    declaration_symbols: [],
                    localization_calls: [],
                    compose: null,
                  }
                : null,
            )
          }
        />
        {t("Extract keys from application code")}
      </Label>
      <p className="text-sm text-muted-foreground">
        {t(
          "The keys repository contains code; the translations repository supplies the language files and base text.",
        )}
      </p>
      {value && (
        <>
          <SymbolField
            label={t("Resource references")}
            values={value.resource_roots ?? []}
            placeholder="Res.strings"
            onChange={(roots) => onChange({ ...value, resource_roots: roots })}
          />
          <SymbolField
            label={t("Constant declarations (qualified names or patterns)")}
            values={value.declaration_symbols ?? []}
            placeholder="com.example.Keys.*"
            onChange={(names) =>
              onChange({
                ...value,
                declaration_symbols: names,
              })
            }
          />
          <SymbolField
            label={t("Translation functions")}
            values={value.localization_calls ?? []}
            placeholder={t("translate, localize")}
            onChange={(names) =>
              onChange({
                ...value,
                localization_calls: names,
              })
            }
          />
          <Label className="flex gap-2">
            <Checkbox
              checked={Boolean(value.compose)}
              onCheckedChange={(checked) =>
                onChange({
                  ...value,
                  compose: checked
                    ? {
                        runner_profile: "",
                        module: ":app",
                        variant: "Debug",
                        preview_functions: [],
                        width_dp: 1280,
                        height_dp: 800,
                      }
                    : null,
                })
              }
            />{" "}
            {t("Enable on-demand Compose screenshots")}
          </Label>
          {value.compose && (
            <div className="grid gap-4">
              <Label className="grid gap-2">
                {t("Configured capture runner")}
                <Input
                  value={value.compose.runner_profile}
                  placeholder="android-preview"
                  onChange={(e) =>
                    onChange({
                      ...value,
                      compose: {
                        ...value.compose!,
                        runner_profile: e.target.value,
                      },
                    })
                  }
                />
              </Label>
              <Label className="grid gap-2">
                {t("Android module")}
                <Input
                  value={value.compose.module ?? ":app"}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      compose: { ...value.compose!, module: e.target.value },
                    })
                  }
                />
              </Label>
              <Label className="grid gap-2">
                {t("Build variant")}
                <Input
                  value={value.compose.variant ?? "Debug"}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      compose: { ...value.compose!, variant: e.target.value },
                    })
                  }
                />
              </Label>
              <SymbolField
                label={t("Callable preview functions (one per line)")}
                multiline
                values={value.compose.preview_functions}
                placeholder="com.example.screens.HomePreview"
                onChange={(names) =>
                  onChange({
                    ...value,
                    compose: {
                      ...value.compose!,
                      preview_functions: names,
                    },
                  })
                }
              />
              <p className="text-sm text-muted-foreground">
                {t(
                  "Register previews with fixture data and configure the isolated runner on the server. Screenshots are rendered only when requested.",
                )}
              </p>
            </div>
          )}
        </>
      )}
    </fieldset>
  );
}
