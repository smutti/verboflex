import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getAdminImport,
  type AdminPublishedMappingImportResponse,
} from "../../../api/client";

export interface UseImportPollingOptions {
  accessToken: string;
  initialImport: AdminPublishedMappingImportResponse;
  onAnnouncement?: (state: string) => void;
  productId: string;
}

const POLLING_STATES = new Set<AdminPublishedMappingImportResponse["state"]>([
  "queued",
  "running",
]);

const STATE_LABELS: Record<
  AdminPublishedMappingImportResponse["state"],
  string
> = {
  current: "Current",
  import_failed: "Import failed",
  may_be_stale: "May be stale",
  not_imported: "Not imported",
  queued: "Queued",
  review_required: "Review required",
  running: "Running",
};

export function nextImportPollDelay(elapsedMs: number) {
  if (elapsedMs < 30_000) {
    return Math.min(2_000, 30_000 - elapsedMs);
  }
  if (elapsedMs < 90_000) {
    return Math.min(5_000, 90_000 - elapsedMs);
  }
  return null;
}

export function importPollingIdentity(
  productId: string,
  importRecord: AdminPublishedMappingImportResponse,
) {
  return JSON.stringify({
    activeRevisionId: importRecord.active_revision_id,
    executionNumber: importRecord.execution_number,
    id: importRecord.id,
    mappingId: importRecord.mapping_id,
    productId,
  });
}

export function useImportPolling({
  accessToken,
  initialImport,
  onAnnouncement,
  productId,
}: UseImportPollingOptions) {
  const initialIdentity = useMemo(
    () => importPollingIdentity(productId, initialImport),
    [initialImport, productId],
  );
  const initialProjectionKey = JSON.stringify(initialImport);
  const identityRef = useRef(initialIdentity);
  const requestGenerationRef = useRef(0);
  const lastStateRef = useRef(initialImport.state);
  const announcementRef = useRef(onAnnouncement);
  const mountedRef = useRef(true);
  const [pollState, setPollState] = useState({
    automaticUpdatesPaused: false,
    identity: initialIdentity,
    importRecord: initialImport,
    pollingError: false,
    sourceProjectionKey: initialProjectionKey,
  });
  const stateMatchesIncomingProjection =
    pollState.identity === initialIdentity &&
    pollState.sourceProjectionKey === initialProjectionKey;
  const importRecord = stateMatchesIncomingProjection
    ? pollState.importRecord
    : initialImport;
  const automaticUpdatesPaused = stateMatchesIncomingProjection
    ? pollState.automaticUpdatesPaused
    : false;
  const pollingError = stateMatchesIncomingProjection
    ? pollState.pollingError
    : false;

  useEffect(() => {
    announcementRef.current = onAnnouncement;
  }, [onAnnouncement]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestGenerationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    identityRef.current = initialIdentity;
    requestGenerationRef.current += 1;
    lastStateRef.current = initialImport.state;
  }, [accessToken, initialIdentity, initialImport.state, initialProjectionKey]);

  const requestStatus = useCallback(
    async (manual: boolean) => {
      const importId = initialImport.id;
      if (importId === null) {
        return;
      }
      const expectedIdentity = initialIdentity;
      const expectedGeneration = requestGenerationRef.current;
      try {
        const result = await getAdminImport({
          auth: accessToken,
          path: { import_id: importId, product_id: productId },
        });
        if (
          !mountedRef.current ||
          requestGenerationRef.current !== expectedGeneration ||
          identityRef.current !== expectedIdentity ||
          result.data === undefined ||
          importPollingIdentity(productId, result.data) !== expectedIdentity
        ) {
          return;
        }
        if (result.data.state !== lastStateRef.current) {
          lastStateRef.current = result.data.state;
          announcementRef.current?.(STATE_LABELS[result.data.state]);
        }
        const latestExecutionAt = Date.parse(
          result.data.latest_execution_at ?? "",
        );
        const cutoffReached =
          Number.isFinite(latestExecutionAt) &&
          Date.now() - latestExecutionAt >= 90_000;
        setPollState({
          automaticUpdatesPaused: manual || cutoffReached,
          identity: expectedIdentity,
          importRecord: result.data,
          pollingError: false,
          sourceProjectionKey: initialProjectionKey,
        });
      } catch {
        if (
          mountedRef.current &&
          requestGenerationRef.current === expectedGeneration &&
          identityRef.current === expectedIdentity
        ) {
          setPollState({
            automaticUpdatesPaused: true,
            identity: expectedIdentity,
            importRecord,
            pollingError: true,
            sourceProjectionKey: initialProjectionKey,
          });
        }
      }
    },
    [
      accessToken,
      importRecord,
      initialIdentity,
      initialImport.id,
      initialProjectionKey,
      productId,
    ],
  );

  useEffect(() => {
    if (
      !POLLING_STATES.has(importRecord.state) ||
      automaticUpdatesPaused ||
      importRecord.id === null
    ) {
      return;
    }
    const parsedLatestExecutionAt = Date.parse(
      importRecord.latest_execution_at ?? "",
    );
    const elapsed = Number.isFinite(parsedLatestExecutionAt)
      ? Date.now() - parsedLatestExecutionAt
      : 0;
    const delay = nextImportPollDelay(elapsed);
    if (delay === null) {
      const pauseTimer = window.setTimeout(() => {
        setPollState((current) => ({
          ...current,
          automaticUpdatesPaused: true,
        }));
      }, 0);
      return () => window.clearTimeout(pauseTimer);
    }
    const timer = window.setTimeout(() => {
      void requestStatus(false);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [automaticUpdatesPaused, importRecord, pollState, requestStatus]);

  const refreshStatus = useCallback(async () => {
    await requestStatus(true);
  }, [requestStatus]);

  return {
    automaticUpdatesPaused,
    importRecord,
    pollingError,
    refreshStatus,
  };
}
