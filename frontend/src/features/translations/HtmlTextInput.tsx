import type { Ref } from "react";
import { LockKeyhole } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { t, useUiLanguage } from "@/i18n";

const variablePattern = /(\{\{\s*[A-Za-z_][A-Za-z0-9_.]*\s*\}\})/g;

/** The same literal placeholders protected by the HTML writer stay outside inputs. */
export function HtmlTextInput({
  id,
  value,
  onChange,
  disabled,
  language,
  describedBy,
  invalid,
  inputRef,
}: {
  id: string;
  value: string;
  onChange: (text: string) => void;
  disabled: boolean;
  language: string;
  describedBy: string;
  invalid: boolean;
  inputRef?: Ref<HTMLTextAreaElement>;
}) {
  useUiLanguage();
  const parts = value.split(variablePattern);
  return (
    <div className="space-y-2">
      {parts.map((part, index) =>
        index % 2 ? (
          <span
            key={index}
            className="flex w-fit max-w-full items-center gap-2 rounded border bg-muted px-2 py-1 text-label"
            aria-label={t("Protected variable: {{v0}}", { v0: part })}
          >
            <LockKeyhole className="size-3 shrink-0" aria-hidden="true" />
            <code className="wrap-anywhere">{part}</code>
          </span>
        ) : (
          <Textarea
            key={index}
            id={index === 0 ? id : `${id}-${index}`}
            ref={index === 0 ? inputRef : undefined}
            aria-label={
              index === 0
                ? undefined
                : t("Text segment {{v0}}", { v0: index / 2 + 1 })
            }
            aria-describedby={describedBy}
            aria-invalid={invalid}
            lang={language}
            dir="auto"
            className={
              parts.length === 1
                ? "min-h-40 whitespace-pre-wrap"
                : "min-h-20 whitespace-pre-wrap"
            }
            value={part}
            disabled={disabled}
            onChange={(event) => {
              const text = event.currentTarget.value;
              if (text.includes("{{") || text.includes("}}")) return;
              onChange(
                parts.map((item, at) => (at === index ? text : item)).join(""),
              );
            }}
          />
        ),
      )}
    </div>
  );
}
