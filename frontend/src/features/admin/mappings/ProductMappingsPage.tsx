import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import {
  createAdminCandidateMapping,
  getAdminProduct,
  listAdminCandidateMappings,
  listAdminRepositories,
  listAdminRepositoryBranches,
  updateAdminCandidateMapping,
  type AdminBranchResponse,
  type AdminDirectMappingWriteRequest,
  type AdminMappingResponse,
  type AdminRepositoryResponse,
  type AdminSeparateMappingWriteRequest,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../../components/ui/alert-dialog";
import { Button } from "../../../components/ui/button";
import { Checkbox } from "../../../components/ui/checkbox";
import { Label } from "../../../components/ui/label";
import { RadioGroup, RadioGroupItem } from "../../../components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../components/ui/select";
import { Skeleton } from "../../../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";

type Topology = "direct" | "separate";
type RepositorySide = "direct" | "keys" | "translations";
type PageState = "error" | "loading" | "ready";
type BranchState =
  | { status: "idle" | "loading" | "error"; items: AdminBranchResponse[] }
  | { status: "ready"; items: AdminBranchResponse[] };
type MappingConflictField =
  | "allowed_target_branches"
  | "candidate_version"
  | "keys_source_branch"
  | "mapping_identity"
  | "source_branch"
  | "translations_source_branch";

export interface ProductMappingsPageProps {
  accessToken: string;
  candidateVersion?: number;
  embedded?: boolean;
  onCandidateVersionChange?: (version: number) => void;
  productId: string;
}

const EMPTY_BRANCH_STATE: BranchState = { status: "idle", items: [] };

function repositoryLabel(repository: AdminRepositoryResponse) {
  const providerIdentity = `${repository.workspace}/${repository.repository_slug}`;
  return repository.descriptive_name === null
    ? providerIdentity
    : `${repository.descriptive_name} — ${providerIdentity}`;
}

function responseStatus(result: { response?: Response }) {
  return result.response?.status;
}

function conflictField(error: unknown): MappingConflictField | null {
  if (typeof error !== "object" || error === null || !("field" in error)) {
    return null;
  }
  const field = error.field;
  return field === "allowed_target_branches" ||
    field === "candidate_version" ||
    field === "keys_source_branch" ||
    field === "mapping_identity" ||
    field === "source_branch" ||
    field === "translations_source_branch"
    ? field
    : null;
}

function conflictCopy(field: MappingConflictField | null) {
  switch (field) {
    case "allowed_target_branches":
      return "The allowed target branches changed. Your selections are still here. Refresh branches and try again.";
    case "candidate_version":
      return "This draft changed in another session. Your entries are still here.";
    case "keys_source_branch":
      return "The Keys source branch changed. Your selections are still here. Refresh branches and try again.";
    case "translations_source_branch":
      return "The Translations source branch changed. Your selections are still here. Refresh branches and try again.";
    case "source_branch":
      return "The source branch changed. Your selections are still here. Refresh branches and try again.";
    default:
      return "This mapping conflicts with the current draft. Your selections are still here.";
  }
}

function MappingBranchDetails({ mapping }: { mapping: AdminMappingResponse }) {
  return (
    <div
      role="region"
      aria-label="Mapping branch details"
      // The UI contract requires local keyboard-focusable overflow for opaque branches.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="w-max min-w-full space-y-1 font-mono text-sm">
        <p>
          {mapping.topology === "direct" ? "Source" : "Keys source"}:{" "}
          {mapping.primary_source_branch}
        </p>
        {mapping.translations_source_branch === null ? null : (
          <p>
            <span>Translations source: </span>
            <span>{mapping.translations_source_branch}</span>
          </p>
        )}
        <p>
          <span>Default target: </span>
          <span>{mapping.default_target_branch}</span>
        </p>
        <p>
          <span>Allowed targets: </span>
          {mapping.allowed_target_branches.map((branch, index) => (
            <span key={branch}>
              {index === 0 ? null : ", "}
              <span>{branch}</span>
            </span>
          ))}
        </p>
      </div>
    </div>
  );
}

export function ProductMappingsPage({
  accessToken,
  candidateVersion: candidateVersionProp,
  embedded = false,
  onCandidateVersionChange,
  productId,
}: ProductMappingsPageProps) {
  const directId = useId();
  const separateId = useId();
  const defaultTargetId = useId();
  const pageGenerationRef = useRef(0);
  const branchGenerationRef = useRef<Record<RepositorySide, number>>({
    direct: 0,
    keys: 0,
    translations: 0,
  });
  const submitPendingRef = useRef(false);
  const [pageState, setPageState] = useState<PageState>("loading");
  const [repositories, setRepositories] = useState<AdminRepositoryResponse[]>(
    [],
  );
  const [mappings, setMappings] = useState<AdminMappingResponse[]>([]);
  const [currentCandidateVersion, setCurrentCandidateVersion] =
    useState(candidateVersionProp);
  const [topology, setTopology] = useState<Topology>("direct");
  const [pendingTopology, setPendingTopology] = useState<Topology | null>(null);
  const [directRepositoryId, setDirectRepositoryId] = useState("");
  const [keysRepositoryId, setKeysRepositoryId] = useState("");
  const [translationsRepositoryId, setTranslationsRepositoryId] = useState("");
  const [directSourceBranch, setDirectSourceBranch] = useState("");
  const [keysSourceBranch, setKeysSourceBranch] = useState("");
  const [translationsSourceBranch, setTranslationsSourceBranch] = useState("");
  const [allowedTargetBranches, setAllowedTargetBranches] = useState<string[]>(
    [],
  );
  const [defaultTargetBranch, setDefaultTargetBranch] = useState("");
  const [branches, setBranches] = useState<Record<RepositorySide, BranchState>>(
    {
      direct: EMPTY_BRANCH_STATE,
      keys: EMPTY_BRANCH_STATE,
      translations: EMPTY_BRANCH_STATE,
    },
  );
  const [editingMapping, setEditingMapping] =
    useState<AdminMappingResponse | null>(null);
  const [submitPending, setSubmitPending] = useState(false);
  const [formError, setFormError] = useState<
    | { kind: "conflict"; field: MappingConflictField | null }
    | { kind: "generic" | "invalid" }
    | null
  >(null);

  function loadPage() {
    const generation = ++pageGenerationRef.current;

    queueMicrotask(async () => {
      if (pageGenerationRef.current !== generation) {
        return;
      }
      setPageState("loading");
      try {
        const [repositoryResult, mappingResult, productResult] =
          await Promise.all([
            listAdminRepositories({
              auth: accessToken,
              query: { cursor: null, limit: 50 },
            }),
            listAdminCandidateMappings({
              auth: accessToken,
              path: { product_id: productId },
              query: { cursor: null, limit: 50 },
            }),
            candidateVersionProp === undefined
              ? getAdminProduct({
                  auth: accessToken,
                  path: { product_id: productId },
                })
              : Promise.resolve(null),
          ]);
        if (pageGenerationRef.current !== generation) {
          return;
        }
        if (
          repositoryResult.data === undefined ||
          mappingResult.data === undefined ||
          (productResult !== null && productResult.data === undefined)
        ) {
          setPageState("error");
          return;
        }
        const loadedVersion =
          candidateVersionProp ??
          productResult?.data?.candidate_revision?.version ??
          undefined;
        if (loadedVersion === undefined) {
          setPageState("error");
          return;
        }
        setRepositories(repositoryResult.data.items);
        setMappings(mappingResult.data.items);
        setCurrentCandidateVersion(loadedVersion);
        setPageState("ready");
      } catch {
        if (pageGenerationRef.current === generation) {
          setPageState("error");
        }
      }
    });
  }

  useEffect(() => {
    const branchGenerations = branchGenerationRef.current;
    loadPage();
    return () => {
      pageGenerationRef.current += 1;
      branchGenerations.direct += 1;
      branchGenerations.keys += 1;
      branchGenerations.translations += 1;
    };
    // loadPage is deliberately generation-bound to these exact authorities.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, productId]);

  async function requestBranches(side: RepositorySide, repositoryId: string) {
    const generation = ++branchGenerationRef.current[side];
    setBranches((current) => ({
      ...current,
      [side]: { status: "loading", items: [] },
    }));
    try {
      const result = await listAdminRepositoryBranches({
        auth: accessToken,
        path: { repository_id: repositoryId },
        query: { cursor: null, limit: 100 },
      });
      if (branchGenerationRef.current[side] !== generation) {
        return;
      }
      setBranches((current) => ({
        ...current,
        [side]:
          result.data === undefined
            ? { status: "error", items: [] }
            : { status: "ready", items: result.data.items },
      }));
    } catch {
      if (branchGenerationRef.current[side] === generation) {
        setBranches((current) => ({
          ...current,
          [side]: { status: "error", items: [] },
        }));
      }
    }
  }

  function chooseRepository(side: RepositorySide, repositoryId: string) {
    setFormError(null);
    if (side === "direct") {
      setDirectRepositoryId(repositoryId);
      setDirectSourceBranch("");
      setAllowedTargetBranches([]);
      setDefaultTargetBranch("");
    } else if (side === "keys") {
      setKeysRepositoryId(repositoryId);
      setKeysSourceBranch("");
    } else {
      setTranslationsRepositoryId(repositoryId);
      setTranslationsSourceBranch("");
      setAllowedTargetBranches([]);
      setDefaultTargetBranch("");
    }
    void requestBranches(side, repositoryId);
  }

  function invalidateBranchRequests() {
    branchGenerationRef.current.direct += 1;
    branchGenerationRef.current.keys += 1;
    branchGenerationRef.current.translations += 1;
  }

  function clearMappingSelection() {
    setDirectRepositoryId("");
    setKeysRepositoryId("");
    setTranslationsRepositoryId("");
    setDirectSourceBranch("");
    setKeysSourceBranch("");
    setTranslationsSourceBranch("");
    setAllowedTargetBranches([]);
    setDefaultTargetBranch("");
    setBranches({
      direct: EMPTY_BRANCH_STATE,
      keys: EMPTY_BRANCH_STATE,
      translations: EMPTY_BRANCH_STATE,
    });
  }

  function applyTopologyChange() {
    if (pendingTopology === null) {
      return;
    }
    invalidateBranchRequests();
    setTopology(pendingTopology);
    clearMappingSelection();
    setFormError(null);
    setPendingTopology(null);
  }

  function toggleAllowedTarget(branch: string, checked: boolean) {
    setFormError(null);
    setAllowedTargetBranches((current) => {
      const next = checked
        ? [...current, branch]
        : current.filter((item) => item !== branch);
      if (!next.includes(defaultTargetBranch)) {
        setDefaultTargetBranch("");
      }
      return next;
    });
  }

  function beginEdit(mapping: AdminMappingResponse) {
    setEditingMapping(mapping);
    setTopology(mapping.topology);
    setCurrentCandidateVersion(mapping.candidate_version);
    setAllowedTargetBranches(mapping.allowed_target_branches);
    setDefaultTargetBranch(mapping.default_target_branch);
    setFormError(null);
    if (mapping.topology === "direct") {
      setDirectRepositoryId(mapping.primary_repository_id);
      setDirectSourceBranch(mapping.primary_source_branch);
      setKeysRepositoryId("");
      setTranslationsRepositoryId("");
      setKeysSourceBranch("");
      setTranslationsSourceBranch("");
      void requestBranches("direct", mapping.primary_repository_id);
    } else {
      setDirectRepositoryId("");
      setDirectSourceBranch("");
      setKeysRepositoryId(mapping.primary_repository_id);
      setKeysSourceBranch(mapping.primary_source_branch);
      setTranslationsRepositoryId(mapping.translations_repository_id ?? "");
      setTranslationsSourceBranch(mapping.translations_source_branch ?? "");
      void requestBranches("keys", mapping.primary_repository_id);
      if (mapping.translations_repository_id !== null) {
        void requestBranches(
          "translations",
          mapping.translations_repository_id,
        );
      }
    }
  }

  function resetForm(version = currentCandidateVersion) {
    invalidateBranchRequests();
    setEditingMapping(null);
    setTopology("direct");
    clearMappingSelection();
    setCurrentCandidateVersion(version);
    setFormError(null);
  }

  async function saveMapping(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitPendingRef.current) {
      return;
    }
    const targetIsMember = allowedTargetBranches.includes(defaultTargetBranch);
    const valid =
      currentCandidateVersion !== undefined &&
      allowedTargetBranches.length > 0 &&
      defaultTargetBranch.length > 0 &&
      targetIsMember &&
      (topology === "direct"
        ? directRepositoryId.length > 0 && directSourceBranch.length > 0
        : keysRepositoryId.length > 0 &&
          keysSourceBranch.length > 0 &&
          translationsRepositoryId.length > 0 &&
          translationsSourceBranch.length > 0);
    if (!valid || currentCandidateVersion === undefined) {
      setFormError({ kind: "invalid" });
      return;
    }

    const body:
      AdminDirectMappingWriteRequest | AdminSeparateMappingWriteRequest =
      topology === "direct"
        ? {
            topology: "direct",
            repository_id: directRepositoryId,
            source_branch: directSourceBranch,
            allowed_target_branches: allowedTargetBranches,
            default_target_branch: defaultTargetBranch,
            expected_candidate_version: currentCandidateVersion,
          }
        : {
            topology: "separate",
            sides: [
              {
                role: "keys",
                repository_id: keysRepositoryId,
                source_branch: keysSourceBranch,
              },
              {
                role: "translations",
                repository_id: translationsRepositoryId,
                source_branch: translationsSourceBranch,
              },
            ],
            allowed_target_branches: allowedTargetBranches,
            default_target_branch: defaultTargetBranch,
            expected_candidate_version: currentCandidateVersion,
          };

    submitPendingRef.current = true;
    setSubmitPending(true);
    setFormError(null);
    try {
      const result =
        editingMapping === null
          ? await createAdminCandidateMapping({
              auth: accessToken,
              path: { product_id: productId },
              body,
            })
          : await updateAdminCandidateMapping({
              auth: accessToken,
              path: {
                product_id: productId,
                mapping_id: editingMapping.id,
              },
              body,
            });
      if (result.data !== undefined) {
        const savedMapping = result.data;
        setMappings((current) =>
          editingMapping === null
            ? [...current, savedMapping]
            : current.map((mapping) =>
                mapping.id === savedMapping.id ? savedMapping : mapping,
              ),
        );
        onCandidateVersionChange?.(savedMapping.candidate_version);
        resetForm(savedMapping.candidate_version);
        toast.success("Draft saved");
        return;
      }
      if (responseStatus(result) === 409) {
        setFormError({
          kind: "conflict",
          field: conflictField(result.error),
        });
        return;
      }
      setFormError({ kind: "generic" });
    } catch {
      setFormError({ kind: "generic" });
    } finally {
      submitPendingRef.current = false;
      setSubmitPending(false);
    }
  }

  const targetBranches =
    topology === "direct" ? branches.direct : branches.translations;
  const Heading = embedded ? "h2" : "h1";

  function repositoryName(repositoryId: string) {
    return (
      repositories.find((repository) => repository.id === repositoryId)
        ?.descriptive_name ?? repositoryId
    );
  }

  return (
    <section className="grid min-w-0 max-w-full gap-8 overflow-x-clip">
      <div className="grid gap-2">
        <Heading
          className={
            embedded
              ? "text-heading font-semibold"
              : "text-display font-semibold"
          }
        >
          Mappings
        </Heading>
        <p className="text-muted-foreground">
          Configure exact repository sides and live Bitbucket branches for the
          current candidate draft.
        </p>
      </div>

      {pageState === "loading" ? (
        <section className="grid gap-3" role="status" aria-live="polite">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <span>Loading mappings</span>
        </section>
      ) : null}

      {pageState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Mappings unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button type="button" variant="outline" onClick={loadPage}>
              Retry loading page
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {pageState === "ready" && mappings.length === 0 ? (
        <section className="grid gap-2 rounded-lg border bg-secondary p-6">
          <h3 className="text-heading font-semibold">No mappings configured</h3>
          <p className="text-muted-foreground">
            Add a mapping that represents one localization format and layout.
          </p>
        </section>
      ) : null}

      {pageState === "ready" && mappings.length > 0 ? (
        <section className="min-w-0 max-w-full overflow-x-clip">
          <div className="hidden md:block">
            <Table aria-label="Mappings">
              <TableHeader>
                <TableRow>
                  <TableHead>Topology</TableHead>
                  <TableHead>Repository sides</TableHead>
                  <TableHead>Branches</TableHead>
                  <TableHead>Draft</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.map((mapping) => (
                  <TableRow key={mapping.id}>
                    <TableCell className="capitalize">
                      {mapping.topology}
                    </TableCell>
                    <TableCell className="whitespace-normal break-words [overflow-wrap:anywhere]">
                      {repositoryName(mapping.primary_repository_id)}
                      {mapping.translations_repository_id === null
                        ? null
                        : ` / ${repositoryName(mapping.translations_repository_id)}`}
                    </TableCell>
                    <TableCell className="max-w-sm whitespace-normal">
                      <MappingBranchDetails mapping={mapping} />
                    </TableCell>
                    <TableCell>
                      Draft version {mapping.candidate_version}
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => beginEdit(mapping)}
                      >
                        Edit mapping
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div
            className="grid min-w-0 max-w-full divide-y md:hidden"
            aria-label="Mappings mobile list"
          >
            {mappings.map((mapping) => (
              <article key={mapping.id} className="grid min-w-0 gap-3 py-4">
                <strong className="capitalize">{mapping.topology}</strong>
                <p className="break-words [overflow-wrap:anywhere]">
                  {repositoryName(mapping.primary_repository_id)}
                  {mapping.translations_repository_id === null
                    ? null
                    : ` / ${repositoryName(mapping.translations_repository_id)}`}
                </p>
                <MappingBranchDetails mapping={mapping} />
                <p>Draft version {mapping.candidate_version}</p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => beginEdit(mapping)}
                >
                  Edit mapping
                </Button>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {pageState === "ready" ? (
        <form
          className="grid gap-6 rounded-lg border bg-secondary p-6"
          onSubmit={(event) => void saveMapping(event)}
        >
          <div className="grid gap-2">
            <h3 className="text-heading font-semibold">
              {editingMapping === null ? "Add mapping" : "Edit mapping"}
            </h3>
            <p className="text-muted-foreground">
              Branch controls contain only current live provider results.
            </p>
          </div>

          <fieldset className="grid gap-3">
            <legend className="text-sm font-semibold">Topology</legend>
            <RadioGroup
              value={topology}
              onValueChange={(value) => {
                if (value !== topology) {
                  setPendingTopology(value as Topology);
                }
              }}
              className="grid gap-3 md:grid-cols-2"
            >
              <div className="flex min-h-11 items-center gap-3 rounded-md border p-3">
                <RadioGroupItem id={directId} value="direct" />
                <Label htmlFor={directId}>Direct</Label>
              </div>
              <div className="flex min-h-11 items-center gap-3 rounded-md border p-3">
                <RadioGroupItem id={separateId} value="separate" />
                <Label htmlFor={separateId}>Separate</Label>
              </div>
            </RadioGroup>
          </fieldset>

          {topology === "direct" ? (
            <div className="grid gap-4 md:grid-cols-2">
              <RepositorySelect
                label="Repository"
                repositories={repositories}
                value={directRepositoryId}
                onValueChange={(value) => chooseRepository("direct", value)}
              />
              <BranchSelect
                label="Source branch"
                branchState={branches.direct}
                value={directSourceBranch}
                onValueChange={(value) => {
                  setDirectSourceBranch(value);
                  setFormError(null);
                }}
              />
            </div>
          ) : (
            <div className="grid gap-6">
              <fieldset className="grid gap-4 rounded-md border p-4 md:grid-cols-2">
                <legend className="px-1 text-sm font-semibold">
                  Keys repository
                </legend>
                <RepositorySelect
                  label="Keys repository"
                  repositories={repositories}
                  value={keysRepositoryId}
                  onValueChange={(value) => chooseRepository("keys", value)}
                />
                <BranchSelect
                  label="Keys source branch"
                  branchState={branches.keys}
                  value={keysSourceBranch}
                  onValueChange={(value) => {
                    setKeysSourceBranch(value);
                    setFormError(null);
                  }}
                />
              </fieldset>
              <fieldset className="grid gap-4 rounded-md border p-4 md:grid-cols-2">
                <legend className="px-1 text-sm font-semibold">
                  Translations repository
                </legend>
                <RepositorySelect
                  label="Translations repository"
                  repositories={repositories}
                  value={translationsRepositoryId}
                  onValueChange={(value) =>
                    chooseRepository("translations", value)
                  }
                />
                <BranchSelect
                  label="Translations source branch"
                  branchState={branches.translations}
                  value={translationsSourceBranch}
                  onValueChange={(value) => {
                    setTranslationsSourceBranch(value);
                    setFormError(null);
                  }}
                />
              </fieldset>
            </div>
          )}

          <fieldset className="grid gap-3">
            <legend className="text-sm font-semibold">Allowed targets</legend>
            {targetBranches.status === "loading" ? (
              <p role="status">Loading live branches</p>
            ) : null}
            {targetBranches.status === "error" ? (
              <Alert variant="destructive">
                <AlertTitle>Branches unavailable</AlertTitle>
                <AlertDescription>
                  The repository or branch is no longer available. Refresh
                  branches and update this mapping.
                </AlertDescription>
              </Alert>
            ) : null}
            {targetBranches.status === "ready" ? (
              <div className="grid gap-2">
                {targetBranches.items.map((branch) => {
                  const checkboxId = `${defaultTargetId}-${branch.name}`;
                  return (
                    <div
                      key={branch.name}
                      className="flex min-h-11 min-w-0 items-center gap-3"
                    >
                      <Checkbox
                        id={checkboxId}
                        checked={allowedTargetBranches.includes(branch.name)}
                        aria-label={`Allow target ${branch.name}`}
                        onCheckedChange={(checked) =>
                          toggleAllowedTarget(branch.name, checked === true)
                        }
                      />
                      <Label
                        htmlFor={checkboxId}
                        className="min-w-0 break-words font-mono [overflow-wrap:anywhere]"
                      >
                        {branch.name}
                      </Label>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </fieldset>

          <div className="grid gap-2">
            <Label htmlFor={defaultTargetId}>Default target</Label>
            <Select
              value={defaultTargetBranch}
              disabled={allowedTargetBranches.length === 0}
              onValueChange={(value) => {
                if (allowedTargetBranches.includes(value)) {
                  setDefaultTargetBranch(value);
                  setFormError(null);
                }
              }}
            >
              <SelectTrigger id={defaultTargetId} className="w-full">
                <SelectValue placeholder="Select an allowed target" />
              </SelectTrigger>
              <SelectContent>
                {allowedTargetBranches.map((branch) => (
                  <SelectItem key={branch} value={branch}>
                    {branch}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {formError !== null ? (
            <Alert variant="destructive" tabIndex={-1}>
              <AlertTitle>Mapping not saved</AlertTitle>
              <AlertDescription>
                {formError.kind === "conflict"
                  ? conflictCopy(formError.field)
                  : formError.kind === "invalid"
                    ? "Choose every repository and source branch, at least one allowed target, and a default target from that set."
                    : "We could not save this draft. Your entries are still here. Review the error and try again."}
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap justify-end gap-3">
            {editingMapping === null ? null : (
              <Button
                type="button"
                variant="outline"
                onClick={() => resetForm()}
              >
                Cancel edit
              </Button>
            )}
            <Button
              type="submit"
              disabled={submitPending}
              aria-busy={submitPending}
            >
              Save mapping
            </Button>
          </div>
        </form>
      ) : null}

      {pendingTopology === null ? null : (
        <AlertDialog
          open
          onOpenChange={(open) => !open && setPendingTopology(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Change mapping topology?</AlertDialogTitle>
              <AlertDialogDescription>
                Changing topology clears the repository and branch selections in
                this unsaved mapping.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                onClick={applyTopologyChange}
              >
                Change topology
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </section>
  );
}

function RepositorySelect({
  label,
  onValueChange,
  repositories,
  value,
}: {
  label: string;
  onValueChange: (value: string) => void;
  repositories: AdminRepositoryResponse[];
  value: string;
}) {
  const id = useId();
  return (
    <div className="grid min-w-0 gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger id={id} className="w-full min-w-0">
          <SelectValue placeholder="Select a registered repository" />
        </SelectTrigger>
        <SelectContent>
          {repositories.map((repository) => (
            <SelectItem key={repository.id} value={repository.id}>
              {repositoryLabel(repository)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function BranchSelect({
  branchState,
  label,
  onValueChange,
  value,
}: {
  branchState: BranchState;
  label: string;
  onValueChange: (value: string) => void;
  value: string;
}) {
  const id = useId();
  return (
    <div className="grid min-w-0 gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select
        value={value}
        disabled={branchState.status !== "ready"}
        onValueChange={onValueChange}
      >
        <SelectTrigger id={id} className="w-full min-w-0">
          <SelectValue
            placeholder={
              branchState.status === "loading"
                ? "Loading live branches"
                : "Select a live branch"
            }
          />
        </SelectTrigger>
        <SelectContent>
          {branchState.items.map((branch) => (
            <SelectItem key={branch.name} value={branch.name}>
              {branch.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
