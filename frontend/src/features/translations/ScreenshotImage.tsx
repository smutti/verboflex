import { useState } from "react";
import { LocateFixed, Maximize2 } from "lucide-react";
import { t, useUiLanguage } from "@/i18n";
import type { ScreenshotLocation } from "../../api/client";
import { Button } from "../../components/ui/button";

export function ScreenshotImage({
  url,
  location,
  stale,
}: {
  url: string;
  location?: ScreenshotLocation | null;
  stale: boolean;
}) {
  useUiLanguage();
  const [showPosition, setShowPosition] = useState(true);
  const found =
    !stale && location?.status === "found" && location.regions?.length;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          className="h-auto min-h-[44px] whitespace-normal"
          asChild
        >
          <a href={url} target="_blank" rel="noreferrer">
            <Maximize2 aria-hidden="true" />
            {t("Open screenshot full size")}
          </a>
        </Button>
        {found ? (
          <Button
            variant="outline"
            className="h-auto min-h-[44px] whitespace-normal"
            aria-pressed={showPosition}
            onClick={() => setShowPosition(!showPosition)}
          >
            <LocateFixed aria-hidden="true" />
            {showPosition ? t("Hide position") : t("Show position")}
          </Button>
        ) : null}
      </div>
      {!found && !stale ? (
        <p className="text-sm text-muted-foreground">
          {location?.status === "ambiguous"
            ? t(
                "This text appears more than once. Its exact position cannot be determined.",
              )
            : location?.status === "not_found"
              ? t(
                  "Text not located in this screenshot. It may be hidden, clipped or unreadable. Try another screen scenario.",
                )
              : t("Position unavailable. You can still review the screenshot.")}
        </p>
      ) : null}
      <div className="relative mx-auto w-fit max-w-full">
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          aria-label={t("Open screenshot full size")}
        >
          <img
            src={url}
            alt={t("Compose screen preview with the selected translations")}
            className="block h-auto max-h-[36rem] max-w-full rounded-md border object-contain"
          />
        </a>
        {found && showPosition ? (
          <svg
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
            role="img"
            aria-label={t("Text position in screenshot")}
          >
            {location.regions?.map((region, index) => (
              <g key={index}>
                <rect
                  {...region}
                  vectorEffect="non-scaling-stroke"
                  fill="none"
                  stroke="white"
                  strokeWidth="6"
                />
                <rect
                  {...region}
                  vectorEffect="non-scaling-stroke"
                  className="fill-primary/15 stroke-primary"
                  strokeWidth="3"
                />
              </g>
            ))}
          </svg>
        ) : null}
      </div>
      {found && showPosition ? (
        <p className="text-xs text-muted-foreground">
          {t("The outline marks the text detected in this screenshot.")}
        </p>
      ) : null}
    </div>
  );
}
