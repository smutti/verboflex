import { useId, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Input } from "./input";
import { cn } from "@/lib/utils";

interface SearchableSelectProps {
  id?: string;
  value: string;
  options: readonly { value: string; label: string }[];
  onValueChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

export function SearchableSelect({
  id,
  value,
  options,
  onValueChange,
  disabled,
  className,
}: SearchableSelectProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const listId = `${inputId}-options`;
  const listRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const selected = options.find((option) => option.value === value);
  const normalize = (text: string) =>
    text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
  const filtered = options.filter((option) =>
    normalize(option.label).includes(normalize(query.trim())),
  );
  const show = () => {
    if (!open) {
      setQuery("");
      setActive(-1);
      setOpen(true);
    }
  };
  const close = () => {
    setOpen(false);
    setQuery("");
    setActive(-1);
  };
  const choose = (next: string) => {
    onValueChange(next);
    close();
  };
  return (
    <div className="relative min-w-0">
      <Input
        id={inputId}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={
          open && active >= 0 && active < filtered.length
            ? `${listId}-${active}`
            : undefined
        }
        autoComplete="off"
        disabled={disabled}
        className={cn("min-h-[44px] pr-9", className)}
        value={open ? query : (selected?.label ?? "")}
        placeholder={selected?.label ?? "Search…"}
        onFocus={show}
        onClick={show}
        onBlur={close}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(-1);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape" && open) {
            event.preventDefault();
            event.stopPropagation();
            close();
          } else if (event.key === "Enter") {
            event.preventDefault();
            if (open && filtered[active]) choose(filtered[active].value);
            else show();
          } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            show();
            const next = filtered.length
              ? event.key === "ArrowDown"
                ? (active + 1) % filtered.length
                : active <= 0
                  ? filtered.length - 1
                  : active - 1
              : -1;
            setActive(next);
            listRef.current?.children[next]?.scrollIntoView({
              block: "nearest",
            });
          }
        }}
      />
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-3 top-3.5 size-4 text-muted-foreground"
      />
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
          <div
            ref={listRef}
            id={listId}
            role="listbox"
            aria-labelledby={inputId}
            className="max-h-60 overflow-y-auto"
          >
            {filtered.map((option, index) => (
              <button
                type="button"
                role="option"
                id={`${listId}-${index}`}
                key={option.value}
                tabIndex={-1}
                aria-selected={option.value === value}
                className={cn(
                  "flex min-h-[44px] w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-sm hover:bg-muted",
                  index === active && "bg-muted",
                )}
                onMouseDown={(event) => event.preventDefault()}
                onPointerDown={(event) => event.preventDefault()}
                onClick={() => choose(option.value)}
              >
                {option.label}
                {option.value === value && (
                  <Check aria-hidden="true" className="size-4 shrink-0" />
                )}
              </button>
            ))}
          </div>
          {!filtered.length && (
            <p role="status" className="p-2 text-sm text-muted-foreground">
              No results
            </p>
          )}
        </div>
      )}
    </div>
  );
}
