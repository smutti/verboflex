import { useEffect, useState } from "react";
import {
  getTranslationGroup,
  type RoleName,
  type TranslationGroupDetailResponse,
  type TranslationProposalResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { TranslationScreenshots } from "./TranslationScreenshots";
import { Discussion, type DiscussionDraftState } from "./Discussion";
import { ActivityHistory } from "./ActivityHistory";
import { TranslationReviewActions } from "./TranslationReviewActions";
import { completeTranslationDetail } from "./translationDetailAuthority";

interface Props {
  section?: "comments" | "history" | "source" | "review";
  onSectionChange?: (
    section: "comments" | "history" | "source" | "review",
  ) => void;
  onDraftStateChange?: (state: DiscussionDraftState) => void;
  embedded?: boolean;
  detail: TranslationGroupDetailResponse;
  accessToken: string;
  principal: { id: string; roles: readonly RoleName[] };
  dirty: boolean;
  proposal?: TranslationProposalResponse | null;
  onReviewed: (projection: TranslationProposalResponse) => void;
}

function Context({
  detail,
  accessToken,
  principal,
  dirty,
  proposal,
  onReviewed,
  section,
  onSectionChange,
  onDraftStateChange,
  embedded = false,
}: Props) {
  // A refetch belongs to one particular incoming detail response. A later
  // response wins immediately, including source-only changes at the same version.
  const [context, setContext] = useState({
    input: detail,
    remote: detail,
    failure: false,
  });
  const remote = context.input === detail ? context.remote : detail;
  const failure = context.input === detail && context.failure;
  const [retry, setRetry] = useState(0);
  const [screenshotsOpen, setScreenshotsOpen] = useState(false);
  const version = Math.max(
    proposal?.version ?? 0,
    detail.pending_change?.version ?? 0,
  );
  const authoritative =
    (remote.pending_change?.version ?? 0) >= version &&
    (!proposal || (context.input === detail && context.remote !== detail));
  useEffect(() => {
    // Save callbacks synthesize pending_change on the pre-save detail. Even an
    // equal version needs the server's current review eligibility and context.
    if (!proposal && retry === 0) return;
    const controller = new AbortController();
    void getTranslationGroup({
      auth: accessToken,
      path: { translation_group_id: detail.id },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (
          !result.data ||
          !completeTranslationDetail(result.data, detail.id) ||
          result.data.product_id !== detail.product_id ||
          result.data.language !== detail.language ||
          (result.data.pending_change?.version ?? 0) < version
        )
          throw new Error("Context unavailable");
        setContext({ input: detail, remote: result.data, failure: false });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setContext((current) => ({
            input: detail,
            remote: current.input === detail ? current.remote : detail,
            failure: true,
          }));
      });
    return () => controller.abort();
  }, [accessToken, detail, version, proposal, retry]);
  const sourceContext = remote.source_context ?? [];
  return (
    <aside
      aria-label="Selected translation context"
      className={`min-w-0 self-start space-y-4 bg-background p-4 ${embedded ? "" : "rounded-lg border xl:sticky xl:top-4"}`}
    >
      <div className="space-y-1">
        <h2 className="text-heading font-semibold">String context</h2>
        <p className="font-mono text-label wrap-anywhere">
          {detail.raw_key} · {detail.language}
        </p>
      </div>
      <section aria-label="Review selected translation" className="space-y-3">
        <p className="text-label font-semibold">
          {remote.pending_change
            ? `Pending: ${remote.pending_change.state} · Version ${remote.pending_change.version}`
            : "No saved proposal yet"}
        </p>
        {!authoritative && !failure && (
          <p role="status">Refreshing saved proposal…</p>
        )}
        {failure && (
          <Alert role="alert">
            <AlertTitle>Saved context could not be refreshed</AlertTitle>
            <AlertDescription>
              <Button
                variant="outline"
                onClick={() => setRetry((value) => value + 1)}
              >
                Retry context
              </Button>
            </AlertDescription>
          </Alert>
        )}
        {authoritative && !failure && (
          <TranslationReviewActions
            accessToken={accessToken}
            principal={principal}
            detail={remote}
            dirty={dirty}
            onChanged={onReviewed}
          />
        )}
      </section>
      <details
        className="rounded-md border p-3"
        onToggle={(event) => setScreenshotsOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer font-semibold">
          Screenshots and code references
        </summary>
        {screenshotsOpen && (
          <TranslationScreenshots
            key={`${detail.id}:${accessToken}`}
            accessToken={accessToken}
            groupId={detail.id}
            dirty={dirty}
            proposalVersion={remote.pending_change?.version}
          />
        )}
      </details>
      <Tabs
        defaultValue="comments"
        value={section === "review" ? "comments" : section}
        onValueChange={(value) =>
          onSectionChange?.(value as "comments" | "history" | "source")
        }
        className="min-w-0"
      >
        <TabsList className="flex h-auto w-full flex-wrap justify-start">
          <TabsTrigger value="comments">Comments</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="source">Source changes</TabsTrigger>
        </TabsList>
        <TabsContent
          value="comments"
          forceMount
          className="min-w-0 data-[state=inactive]:hidden"
        >
          <Discussion
            accessToken={accessToken}
            principal={principal}
            translationGroupId={detail.id}
            language={detail.language}
            onDraftStateChange={onDraftStateChange}
          />
        </TabsContent>
        <TabsContent
          value="history"
          forceMount
          className="min-w-0 data-[state=inactive]:hidden"
        >
          <ActivityHistory
            key={version}
            accessToken={accessToken}
            translationGroupId={detail.id}
            language={detail.language}
          />
        </TabsContent>
        <TabsContent
          value="source"
          forceMount
          className="min-w-0 space-y-4 data-[state=inactive]:hidden"
        >
          <section
            aria-label="Imported values and limits"
            className="space-y-3"
          >
            {remote.values.map((value) => (
              <div key={value.id} className="min-w-0 text-label">
                <p>
                  Actual: {value.constraint.actual} · Maximum:{" "}
                  {value.constraint.maximum ?? "None"}
                </p>
                {value.provenance && (
                  <p className="wrap-anywhere">
                    {value.provenance.repository_name} ·{" "}
                    {value.provenance.branch} · {value.provenance.path}
                  </p>
                )}
                <p dir="auto" className="whitespace-pre-wrap wrap-anywhere">
                  {value.source_text ?? value.display_text}
                </p>
              </div>
            ))}
          </section>
          <p className="text-label text-muted-foreground">
            Latest two source imports
          </p>
          {sourceContext.length === 0 && (
            <p>Source comparison unavailable for this imported entry.</p>
          )}
          {sourceContext.map((source) => (
            <section
              key={source.source_value_id}
              className="min-w-0 space-y-3 border-t pt-3"
              aria-label={`Source variant ${source.source_value_id}`}
            >
              <p className="text-label font-semibold">
                {source.language ?? "Unknown source language"} ·{" "}
                {source.selector_fields
                  ?.map((field) => `${field.name}: ${String(field.value)}`)
                  .join(", ") || source.selector_kind}
              </p>
              {source.provenance && (
                <p className="text-label text-muted-foreground wrap-anywhere">
                  {source.provenance.repository_name} · {source.provenance.path}
                </p>
              )}
              {source.source_comparison ? (
                <>
                  {!source.source_comparison.changed && (
                    <p className="text-label">
                      Source unchanged between these imports.
                    </p>
                  )}
                  <div className="grid min-w-0 gap-3">
                    <div className="min-w-0 rounded-md bg-secondary p-3">
                      <h3 className="text-label font-semibold">
                        Previous imported source · Revision{" "}
                        {source.source_comparison.previous_revision_number}
                      </h3>
                      <p
                        dir="auto"
                        lang={source.language ?? undefined}
                        className="whitespace-pre-wrap wrap-anywhere"
                      >
                        {source.source_comparison.previous_text ||
                          "Empty source text"}
                      </p>
                    </div>
                    <div className="min-w-0 rounded-md border p-3">
                      <h3 className="text-label font-semibold">
                        Current imported source · Revision{" "}
                        {source.source_comparison.current_revision_number}
                      </h3>
                      <p
                        dir="auto"
                        lang={source.language ?? undefined}
                        className="whitespace-pre-wrap wrap-anywhere"
                      >
                        {source.source_comparison.current_text ||
                          "Empty source text"}
                      </p>
                    </div>
                  </div>
                  {(source.source_comparison.previous_truncated ||
                    source.source_comparison.current_truncated) && (
                    <p className="text-label">
                      Excerpt truncated to 4,096 characters; the change
                      indicator compares the full source.
                    </p>
                  )}
                  <details className="text-label text-muted-foreground">
                    <summary className="cursor-pointer">
                      Import references
                    </summary>
                    <p className="wrap-anywhere">
                      Source record: {source.source_value_id}
                    </p>
                    <p className="wrap-anywhere">
                      Previous: {source.source_comparison.previous_commit_hash}{" "}
                      · {source.source_comparison.previous_execution_id}
                    </p>
                    <p className="wrap-anywhere">
                      Current: {source.source_comparison.current_commit_hash} ·{" "}
                      {source.source_comparison.current_execution_id}
                    </p>
                  </details>
                </>
              ) : (
                <p className="text-label">
                  Two source revisions are needed to compare changes.
                </p>
              )}
            </section>
          ))}
        </TabsContent>
      </Tabs>
    </aside>
  );
}

export function TranslationContextPanel(props: Props) {
  return (
    <Context
      key={JSON.stringify([
        props.principal.id,
        props.principal.roles,
        props.accessToken,
        props.detail.product_id,
        props.detail.id,
        props.detail.language,
      ])}
      {...props}
    />
  );
}
