import { t, useUiLanguage } from "@/i18n";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  listProjectUpdates,
  listMyActivity,
  type CurrentUserResponse,
  type ProjectUpdatesPage as ProjectUpdatesResponse,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { ActivityEventList } from "./ActivityEventList";

function ProjectUpdatesController({
  accessToken,
  personal,
}: {
  accessToken: string;
  personal: boolean;
}) {
  useUiLanguage();
  const title = personal ? t("My activity") : t("Project updates");
  const list = personal ? listMyActivity : listProjectUpdates;
  const [items, setItems] = useState<ProjectUpdatesResponse["items"]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failedCursor, setFailedCursor] = useState<string | null | undefined>(
    undefined,
  );
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const load = useCallback(
    async (cursor: string | null = null) => {
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      const current = ++generation.current;
      setLoading(true);
      setFailedCursor(undefined);
      if (cursor === null) {
        setItems([]);
        setNextCursor(null);
      }
      try {
        const response = await list({
          auth: accessToken,
          signal: controller.signal,
          query: cursor ? { cursor } : {},
        });
        if (controller.signal.aborted || current !== generation.current) return;
        if (!response.data) throw new Error("Updates unavailable");
        const page = response.data;
        setItems((previous) =>
          cursor === null
            ? page.items
            : [
                ...previous,
                ...page.items.filter(
                  (item) =>
                    !previous.some(
                      (existing) => existing.event_id === item.event_id,
                    ),
                ),
              ],
        );
        setNextCursor(page.next_cursor);
      } catch {
        if (!controller.signal.aborted && current === generation.current)
          setFailedCursor(cursor);
      } finally {
        if (!controller.signal.aborted && current === generation.current)
          setLoading(false);
      }
    },
    [accessToken, list],
  );
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
      generation.current += 1;
      request.current?.abort();
    };
  }, [load]);

  return (
    <section
      className="mx-auto grid w-full max-w-4xl gap-5"
      aria-labelledby="project-updates-title"
    >
      <Link to="/" className="w-fit text-sm text-primary hover:underline">
        {t("Back to Home")}
      </Link>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 id="project-updates-title" className="text-display font-semibold">
          {title}
        </h1>
        <Button
          variant="outline"
          disabled={loading}
          onClick={() => void load()}
        >
          {t("Refresh")}
        </Button>
      </header>
      {items.length > 0 && <ActivityEventList items={items} />}
      {loading && <p role="status">{t("Loading activity…")}</p>}
      {failedCursor !== undefined && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/40 p-4"
        >
          <p>{t("Activity could not be loaded.")}</p>
          <Button variant="outline" onClick={() => void load(failedCursor)}>
            {t("Retry")}
          </Button>
        </div>
      )}
      {!loading && failedCursor === undefined && items.length === 0 && (
        <p>{personal ? t("No activity yet") : t("No project updates yet")}</p>
      )}
      {nextCursor && failedCursor === undefined && (
        <Button
          className="justify-self-start"
          variant="outline"
          disabled={loading}
          onClick={() => void load(nextCursor)}
        >
          {t("Load more")}
        </Button>
      )}
    </section>
  );
}

export function ProjectUpdatesPage({
  accessToken,
  principal,
  personal = false,
}: {
  accessToken: string;
  principal: CurrentUserResponse;
  personal?: boolean;
}) {
  useUiLanguage();
  return (
    <ProjectUpdatesController
      key={JSON.stringify([
        personal,
        principal.id,
        accessToken,
        [...principal.roles].sort(),
      ])}
      accessToken={accessToken}
      personal={personal}
    />
  );
}
