import { t, useUiLanguage } from "@/i18n";
import { Label } from "../../../components/ui/label";
import { Textarea } from "../../../components/ui/textarea";

const example = JSON.stringify(
  {
    version: 1,
    syntax: "ngx_translate",
    files: { en: "en.json", it: "it.json" },
    rich_text_paths: [],
  },
  null,
  2,
);
export function WebProfileFields({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  useUiLanguage();
  let valid = true;
  try {
    if (value) JSON.parse(value);
  } catch {
    valid = false;
  }
  return (
    <details className="rounded-md border p-4" open={Boolean(value)}>
      <summary className="cursor-pointer text-sm font-semibold">
        {t("Angular localization (optional)")}
      </summary>
      <div className="space-y-3 pt-4">
        <Label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) => onChange(event.target.checked ? example : "")}
          />
          {t("Select JSON catalogs and protect ngx-translate messages")}
        </Label>
        {value && (
          <>
            <p className="text-sm text-muted-foreground">
              {t(
                "List locale files relative to the localization folder. Add web_capture with the reviewed manifest path, source roots and runner profile to enable screenshots.",
              )}
            </p>
            <Label className="grid gap-2">
              {t("Localization profile JSON")}
              <Textarea
                rows={12}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                aria-invalid={!valid}
                spellCheck={false}
                className="font-mono"
              />
            </Label>
            {!valid && (
              <p role="alert">{t("Enter valid JSON before saving.")}</p>
            )}
          </>
        )}
      </div>
    </details>
  );
}
