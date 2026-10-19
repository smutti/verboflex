import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { UI_LANGUAGES, isUiLanguage, setUiLanguage, t, useUiLanguage } from ".";

export function LanguagePicker() {
  const language = useUiLanguage();
  const selected = UI_LANGUAGES.find(({ code }) => code === language)!;
  const label = t("Interface language: {{language}}", {
    language: selected.name,
  });
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          type="button"
          aria-label={label}
          title={label}
          className="min-h-[44px] min-w-[44px] shrink-0 gap-1.5 px-2"
        >
          <span aria-hidden="true" className="text-xl">
            {selected.flag}
          </span>
          <span
            className="hidden text-xs font-semibold sm:inline"
            aria-hidden="true"
          >
            {selected.code.toUpperCase()}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" aria-label={t("Interface language")}>
        <DropdownMenuRadioGroup
          value={language}
          onValueChange={(value) => {
            if (isUiLanguage(value)) setUiLanguage(value);
          }}
        >
          {UI_LANGUAGES.map((item) => (
            <DropdownMenuRadioItem
              key={item.code}
              value={item.code}
              lang={item.code}
              className="min-h-[44px] gap-2"
            >
              <span aria-hidden="true">{item.flag}</span>
              {item.name}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
