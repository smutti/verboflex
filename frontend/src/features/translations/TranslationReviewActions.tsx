import { rolesForProduct } from "../auth/productRoles";
import { useEffect, useRef, useState } from "react";
import {
  transitionTranslationProposal,
  type RoleName,
  type ReviewTransitionConflictResponse,
  type TranslationGroupDetailResponse,
  type TranslationProposalResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";

interface Props {
  accessToken: string;
  principal: { id: string; roles: readonly RoleName[] };
  detail: TranslationGroupDetailResponse;
  proposal?: TranslationProposalResponse | null;
  dirty: boolean;
  onChanged: (proposal: TranslationProposalResponse) => void;
}

function completeProjection(
  fresh: TranslationProposalResponse,
  detail: TranslationGroupDetailResponse,
  version: number,
) {
  if (
    !fresh ||
    fresh.translation_group_id !== detail.id ||
    fresh.language !== detail.language ||
    !Number.isSafeInteger(fresh.version) ||
    fresh.version < version ||
    !["draft", "approved", "rejected"].includes(fresh.state) ||
    !Array.isArray(fresh.pending) ||
    !Array.isArray(fresh.published)
  )
    return false;
  return [fresh.pending, fresh.published].every(
    (values) =>
      values.length === detail.values.length &&
      new Set(values.map((value) => value.translation_value_id)).size ===
        values.length &&
      values.every((value) =>
        detail.values.some(
          (member) =>
            member.id === value.translation_value_id &&
            member.selector_version === value.selector_version &&
            member.selector_digest === value.selector_digest,
        ),
      ),
  );
}

function ReviewController({
  accessToken,
  principal,
  detail,
  proposal,
  dirty,
  onChanged,
}: Props) {
  const [reviewing, setReviewing] = useState(false);
  const [failure, setFailure] = useState<"general" | "conflict" | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const active = useRef<AbortController | null>(null);
  const [latest, setLatest] = useState<TranslationProposalResponse | null>(
    null,
  );
  const override =
    latest ??
    (proposal && proposal.version > (detail.pending_change?.version ?? 0)
      ? proposal
      : null);
  const pending = override?.pending ?? detail.pending_change?.values ?? [];
  const state = override?.state ?? detail.pending_change?.state;
  const version = override?.version ?? detail.pending_change?.version ?? 0;
  const reconciliation =
    override?.reconciliation_required ??
    detail.pending_change?.reconciliation_required ??
    false;
  const membersComplete =
    pending.length === detail.values.length &&
    new Set(pending.map((value) => value.translation_value_id)).size ===
      pending.length &&
    detail.values.every(
      (value) =>
        !value.is_deleted &&
        pending.some(
          (member) =>
            member.translation_value_id === value.id &&
            member.selector_version === value.selector_version &&
            member.selector_digest === value.selector_digest,
        ),
    );
  const eligible = override
    ? !reconciliation &&
      membersComplete &&
      pending.every((value) => value.approval_eligible)
    : detail.review_eligible;
  const authorized = rolesForProduct(principal, detail.product_id).some(
    (role) => role === "admin" || role === "product_manager_reviewer",
  );
  const blocked = pending.some(
    (value) => value.is_over_limit || !value.approval_eligible,
  );
  const hasLengthViolation = pending.some((value) => value.is_over_limit);
  const canReview =
    authorized && !detail.is_deleted && !!state && eligible && membersComplete;
  useEffect(() => () => active.current?.abort(), []);

  async function transition(target: "draft" | "approved" | "rejected") {
    if (
      active.current ||
      !canReview ||
      dirty ||
      reconciliation ||
      (target === "approved" && blocked)
    )
      return;
    const controller = new AbortController();
    active.current = controller;
    setReviewing(true);
    setFailure(null);
    try {
      const result = await transitionTranslationProposal({
        auth: accessToken,
        path: { translation_group_id: detail.id },
        body: {
          expected_version: version,
          target_state: target,
          reason: target === "rejected" ? reason.trim() || null : null,
        },
        signal: controller.signal,
      });
      if (controller.signal.aborted || active.current !== controller) return;
      if (result.response?.status === 409 && result.error) {
        const fresh = (result.error as ReviewTransitionConflictResponse).latest;
        if (!fresh || !completeProjection(fresh, detail, version))
          throw new Error("Invalid review conflict");
        setLatest(fresh);
        setFailure("conflict");
        // Keep the latest complete projection visible for an explicit second action.
        return;
      }
      const fresh = result.data;
      if (
        !fresh ||
        !completeProjection(fresh, detail, version + 1) ||
        fresh.state !== target
      )
        throw new Error("Invalid review projection");
      setRejectOpen(false);
      setReason("");
      onChanged(fresh);
    } catch {
      if (!controller.signal.aborted) setFailure("general");
    } finally {
      if (!controller.signal.aborted && active.current === controller) {
        active.current = null;
        setReviewing(false);
      }
    }
  }
  if (!authorized || detail.is_deleted || !state) return null;
  return (
    <div className="space-y-3" aria-label="Translation review actions">
      {dirty && (
        <p className="text-label text-warning">
          Save your changes before reviewing this proposal.
        </p>
      )}
      {hasLengthViolation && (
        <Alert className="border-warning bg-warning/10 text-warning">
          <AlertTitle>Approval blocked</AlertTitle>
          <AlertDescription>
            Resolve every maximum-length violation before approval.
          </AlertDescription>
        </Alert>
      )}
      {(reconciliation || !membersComplete) && (
        <Alert>
          <AlertTitle>Reconciliation required</AlertTitle>
          <AlertDescription>
            Edit and reconcile this proposal before changing its review state.
          </AlertDescription>
        </Alert>
      )}
      {failure && (
        <Alert role="alert">
          <AlertTitle>
            {failure === "conflict"
              ? "Review state changed in another session"
              : "Review action did not complete"}
          </AlertTitle>
          <AlertDescription>
            {failure === "conflict"
              ? "The latest saved proposal is shown. Review it before trying again."
              : "Your proposal is unchanged. Retry the review action."}
          </AlertDescription>
        </Alert>
      )}
      {latest && (
        <section
          aria-label="Latest saved review proposal"
          className="space-y-2 rounded-md border p-3"
        >
          <p className="text-label font-semibold">
            Latest saved proposal · {latest.state} · Version {latest.version}
          </p>
          {latest.pending.map((value) => (
            <p
              key={value.translation_value_id}
              dir="auto"
              lang={detail.language}
              className="whitespace-pre-wrap wrap-anywhere"
            >
              {value.text || "Empty translation"}
            </p>
          ))}
        </section>
      )}
      {canReview && (
        <div className="flex flex-wrap gap-2">
          {state !== "approved" && (
            <Button
              disabled={reviewing || blocked || reconciliation || dirty}
              onClick={() => void transition("approved")}
            >
              Approve translation
            </Button>
          )}
          {state !== "rejected" && (
            <Button
              variant="outline"
              disabled={reviewing || reconciliation || dirty}
              onClick={() => setRejectOpen(true)}
            >
              Reject translation
            </Button>
          )}
          {state !== "draft" && (
            <Button
              variant="outline"
              disabled={reviewing || reconciliation || dirty}
              onClick={() => void transition("draft")}
            >
              Return to Draft
            </Button>
          )}
        </div>
      )}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent aria-describedby={undefined}>
          <DialogHeader>
            <DialogTitle>Reject this translation?</DialogTitle>
          </DialogHeader>
          <Label htmlFor="translation-rejection-reason">
            Reason (optional)
          </Label>
          <Textarea
            id="translation-rejection-reason"
            value={reason}
            disabled={reviewing}
            onChange={(event) => setReason(event.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={reviewing || dirty}
              onClick={() => void transition("rejected")}
            >
              Reject translation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function TranslationReviewActions(props: Props) {
  const key = JSON.stringify([
    props.principal.id,
    props.principal.roles,
    props.accessToken,
    props.detail.product_id,
    props.detail.id,
    props.detail.language,
    props.detail.constraint_version,
    props.detail.review_eligible,
    props.detail.pending_change?.version,
    props.proposal?.version,
    props.dirty,
  ]);
  return <ReviewController key={key} {...props} />;
}
