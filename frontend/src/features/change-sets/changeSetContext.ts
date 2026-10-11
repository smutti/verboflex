import { createContext, useContext } from "react";
import type {
  ChangeSetCandidate,
  ChangeSetCandidatesResponse,
  MappingDestination,
  MappingTarget,
  SubmissionReviewResponse,
  SubmissionBatchResponse,
  GetChangeSetCandidatesData,
  ChangeSetResponse,
} from "../../api/client";
export interface SubmissionIntake {
  reviewId: string;
  attempt: number;
  digest: string;
  requestKey: string;
  state: "pending" | "uncertain" | "accepted" | "rejected";
  batch?: SubmissionBatchResponse;
}
export interface SelectionEntry {
  candidate: ChangeSetCandidate;
  needsReview: boolean;
}
export interface CandidateMemory {
  filters: NonNullable<GetChangeSetCandidatesData["query"]>;
  items: ChangeSetCandidate[];
  page: ChangeSetCandidatesResponse;
}
export interface HistoryMemory {
  items: ChangeSetResponse[];
  cursor?: string;
  next: string | null;
}
interface Workspace {
  principalId: string;
  accessToken: string;
  productId: string;
  selection: SelectionEntry[];
  destinations: MappingDestination[];
  targets: MappingTarget[];
  canRequest: boolean;
  limit: number;
  review?: SubmissionReviewResponse;
  busy: boolean;
  error?: string;
  observe: (page: ChangeSetCandidatesResponse) => void;
  select: (rows: ChangeSetCandidate[]) => void;
  remove: (id: string) => void;
  requestReview: (targets?: MappingTarget[]) => Promise<void>;
  setReview: (review: SubmissionReviewResponse) => void;
  submissionIntake?: SubmissionIntake;
  setSubmissionIntake: (value: SubmissionIntake) => void;
  candidateMemory?: CandidateMemory;
  setCandidateMemory: (value: Workspace["candidateMemory"]) => void;
  returnFocus?: string;
  setReturnFocus: (value: string | undefined) => void;
  historyMemory?: HistoryMemory;
  setHistoryMemory: (value: HistoryMemory | undefined) => void;
  readSignal: AbortSignal;
  readUnavailable: boolean;
  revokeRead: () => void;
  revokeSubmission: () => void;
}
export const ChangeSetContext = createContext<Workspace | null>(null);
export function useChangeSetWorkspace() {
  const value = useContext(ChangeSetContext);
  if (!value) throw new Error("Change set workspace unavailable");
  return value;
}
