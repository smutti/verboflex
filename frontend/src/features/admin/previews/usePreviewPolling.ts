import { t } from "@/i18n";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getAdminPreviewJob,
  type AdminPreviewJobResponse,
} from "../../../api/client";

export interface UsePreviewPollingOptions {
  accessToken: string;
  initialJob: AdminPreviewJobResponse;
  onAnnouncement?: (state: string) => void;
}

const TERMINAL_STATES = new Set<AdminPreviewJobResponse["state"]>([
  "failed",
  "succeeded",
  "timed_out",
]);

const STATE_LABELS: Record<AdminPreviewJobResponse["state"], string> = {
  get failed() {
    return t("Failed");
  },
  get queued() {
    return t("Queued");
  },
  get running() {
    return t("Running");
  },
  get succeeded() {
    return t("Succeeded");
  },
  get timed_out() {
    return t("Timed out");
  },
};

export function nextPreviewPollDelay(elapsedMs: number) {
  if (elapsedMs < 30_000) {
    return Math.min(2_000, 30_000 - elapsedMs);
  }
  if (elapsedMs < 90_000) {
    return Math.min(5_000, 90_000 - elapsedMs);
  }
  return null;
}

export function previewJobIdentity(job: AdminPreviewJobResponse) {
  return JSON.stringify({
    attempt: job.attempt,
    candidateRevisionId: job.candidate_revision_id,
    candidateRevisionVersion: job.candidate_revision_version,
    connectionGeneration: job.connection_generation,
    detectorVersion: job.detector_version,
    id: job.id,
    inputDigest: job.input_digest,
    mappingId: job.mapping_id,
    productId: job.product_id,
    repositorySides: job.repository_sides.map((side) => ({
      commitHash: side.commit_hash,
      repositoryId: side.repository_id,
      role: side.role,
      sourceBranch: side.source_branch,
    })),
  });
}

export function usePreviewPolling({
  accessToken,
  initialJob,
  onAnnouncement,
}: UsePreviewPollingOptions) {
  const initialIdentity = useMemo(
    () => previewJobIdentity(initialJob),
    [initialJob],
  );
  const identityRef = useRef(initialIdentity);
  const lastStateRef = useRef(initialJob.state);
  const announcementRef = useRef(onAnnouncement);
  const mountedRef = useRef(true);
  const [pollState, setPollState] = useState({
    automaticUpdatesPaused: false,
    identity: initialIdentity,
    job: initialJob,
    pollingError: false,
  });
  const stateMatchesIncomingIdentity = pollState.identity === initialIdentity;
  const job = stateMatchesIncomingIdentity ? pollState.job : initialJob;
  const automaticUpdatesPaused = stateMatchesIncomingIdentity
    ? pollState.automaticUpdatesPaused
    : false;
  const pollingError = stateMatchesIncomingIdentity
    ? pollState.pollingError
    : false;

  useEffect(() => {
    announcementRef.current = onAnnouncement;
  }, [onAnnouncement]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    identityRef.current = initialIdentity;
    lastStateRef.current = initialJob.state;
  }, [initialIdentity, initialJob]);

  const requestStatus = useCallback(
    async (manual: boolean) => {
      const expectedIdentity = initialIdentity;
      try {
        const result = await getAdminPreviewJob({
          auth: accessToken,
          path: { job_id: job.id },
        });
        if (
          !mountedRef.current ||
          identityRef.current !== expectedIdentity ||
          result.data === undefined ||
          previewJobIdentity(result.data) !== expectedIdentity
        ) {
          return;
        }
        if (result.data.state !== lastStateRef.current) {
          lastStateRef.current = result.data.state;
          announcementRef.current?.(STATE_LABELS[result.data.state]);
        }
        const createdAt = Date.parse(result.data.created_at);
        const cutoffReached =
          Number.isFinite(createdAt) && Date.now() - createdAt >= 90_000;
        setPollState({
          automaticUpdatesPaused: manual || cutoffReached,
          identity: expectedIdentity,
          job: result.data,
          pollingError: false,
        });
      } catch {
        if (mountedRef.current && identityRef.current === expectedIdentity) {
          setPollState({
            automaticUpdatesPaused: true,
            identity: expectedIdentity,
            job,
            pollingError: true,
          });
        }
      }
    },
    [accessToken, initialIdentity, job],
  );

  useEffect(() => {
    if (TERMINAL_STATES.has(job.state) || automaticUpdatesPaused) {
      return;
    }
    const createdAt = Date.parse(job.created_at);
    const elapsed = Number.isFinite(createdAt) ? Date.now() - createdAt : 0;
    const delay = nextPreviewPollDelay(elapsed);
    if (delay === null) {
      return;
    }
    const timer = window.setTimeout(() => {
      void requestStatus(false);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [automaticUpdatesPaused, job, pollState, requestStatus]);

  const refreshStatus = useCallback(async () => {
    await requestStatus(true);
  }, [requestStatus]);

  return {
    automaticUpdatesPaused,
    job,
    pollingError,
    refreshStatus,
  };
}
