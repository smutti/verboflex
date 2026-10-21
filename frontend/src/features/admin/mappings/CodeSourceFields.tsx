import { t, useUiLanguage } from "@/i18n";
import type { CodeSourceConfig } from "../../../api/client";
import { useState, type ChangeEvent, type FocusEvent } from "react";
import { Checkbox } from "../../../components/ui/checkbox";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Button } from "../../../components/ui/button";

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
                  preview_scenarios: [],
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
              <fieldset className="space-y-4 rounded-md border p-3">
                <legend className="px-1 font-medium">
                  {t("Screen scenarios")}
                </legend>
                <p className="text-sm text-muted-foreground">
                  {t(
                    "Name each screen state and list the keys visible in it. The first matching scenario is selected automatically.",
                  )}
                </p>
                {(value.preview_scenarios ?? []).map((scenario, index) => {
                  const update = (changes: Partial<typeof scenario>) =>
                    onChange({
                      ...value,
                      preview_scenarios: value.preview_scenarios!.map(
                        (item, position) =>
                          position === index ? { ...item, ...changes } : item,
                      ),
                    });
                  return (
                    <fieldset
                      key={index}
                      className="space-y-3 rounded-md border p-3"
                    >
                      <legend className="px-1 text-sm">
                        {t("Scenario {{number}}", { number: index + 1 })}
                      </legend>
                      <Label className="grid gap-2">
                        {t("Scenario name")}
                        <Input
                          value={scenario.label}
                          maxLength={120}
                          onChange={(e) => update({ label: e.target.value })}
                          placeholder={t("Registration — dialog open")}
                        />
                      </Label>
                      <Label className="grid gap-2">
                        {t("Callable preview function")}
                        <select
                          className="min-w-0 max-w-full rounded-md border bg-background p-2"
                          value={scenario.preview_function}
                          onChange={(e) =>
                            update({ preview_function: e.target.value })
                          }
                        >
                          <option value="">{t("Select a preview")}</option>
                          {value.compose!.preview_functions.map((name) => (
                            <option key={name} value={name}>
                              {name}
                            </option>
                          ))}
                        </select>
                      </Label>
                      <SymbolField
                        label={t("Visible keys (one per line)")}
                        multiline
                        values={scenario.keys}
                        placeholder="privacy_notice"
                        onChange={(keys) => update({ keys })}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() =>
                          onChange({
                            ...value,
                            preview_scenarios: value.preview_scenarios!.filter(
                              (_, position) => position !== index,
                            ),
                          })
                        }
                      >
                        {t("Remove scenario")}
                      </Button>
                    </fieldset>
                  );
                })}
                <Button
                  type="button"
                  variant="outline"
                  disabled={(value.preview_scenarios?.length ?? 0) >= 100}
                  onClick={() =>
                    onChange({
                      ...value,
                      preview_scenarios: [
                        ...(value.preview_scenarios ?? []),
                        { preview_function: "", label: "", keys: [] },
                      ],
                    })
                  }
                >
                  {t("Add scenario")}
                </Button>
              </fieldset>
            </div>
          )}
        </>
      )}
    </fieldset>
  );
}
