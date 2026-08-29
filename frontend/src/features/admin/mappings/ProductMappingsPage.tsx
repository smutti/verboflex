import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { toast } from "sonner";

import {
  createAdminCandidateMapping,
  getAdminProduct,
  getAdminRepositoryBranch,
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
import {
  useCursorCollection,
  type CursorCollectionState,
} from "../useCursorCollection";

type Topology = "direct" | "separate";
type RepositorySide = "direct" | "keys" | "translations";
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

function mergeBranches(
  listed: readonly AdminBranchResponse[],
  exact: readonly AdminBranchResponse[],
) {
  const seen = new Set(listed.map((branch) => branch.name));
  return [
    ...listed,
    ...exact.filter((branch) => {
      if (seen.has(branch.name)) {
        return false;
      }
      seen.add(branch.name);
      return true;
    }),
  ];
}

function useRepositoryBranchCollection({
  accessToken,
  productId,
  repositoryId,
  side,
}: {
  accessToken: string;
  productId: string;
  repositoryId: string;
  side: RepositorySide;
}) {
  const loadPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      if (repositoryId.length === 0) {
        return { items: [], next_cursor: null };
      }
      const result = await listAdminRepositoryBranches({
        auth: accessToken,
        path: { repository_id: repositoryId },
        query: { cursor, limit: 100 },
        signal,
      });
      if (result.data === undefined) {
        throw new Error("branches unavailable");
      }
      return result.data;
    },
    [accessToken, repositoryId],
  );

  return useCursorCollection({
    getItemId: (branch: AdminBranchResponse) => branch.name,
    loadPage,
    queryKey: `branches:${productId}:${side}:${repositoryId}:${accessToken}`,
  });
}

function useExactConfiguredBranches({
  accessToken,
  branchNames,
  productId,
  repositoryId,
  side,
}: {
  accessToken: string;
  branchNames: readonly string[];
  productId: string;
  repositoryId: string;
  side: RepositorySide;
}) {
  const generationRef = useRef(0);
  const [items, setItems] = useState<readonly AdminBranchResponse[]>([]);
  const namesKey = Array.from(new Set(branchNames.filter(Boolean))).join(
    "\u0000",
  );

  useEffect(() => {
    const generation = ++generationRef.current;
    const controller = new AbortController();
    const names = namesKey.length === 0 ? [] : namesKey.split("\u0000");

    queueMicrotask(async () => {
      if (generationRef.current !== generation) {
        return;
      }
      setItems([]);
      if (repositoryId.length === 0 || names.length === 0) {
        return;
      }
      try {
        const results = await Promise.all(
          names.map((branchName) =>
            getAdminRepositoryBranch({
              auth: accessToken,
              path: { repository_id: repositoryId },
              query: { branch_name: branchName },
              signal: controller.signal,
            }),
          ),
        );
        if (
          controller.signal.aborted ||
          generationRef.current !== generation ||
          results.some((result) => result.data === undefined)
        ) {
          return;
        }
        setItems(
          results.flatMap((result) =>
            result.data === undefined ? [] : [result.data],
          ),
        );
      } catch {
        // Exact configured values fail closed by remaining absent from live controls.
      }
    });

    return () => {
      if (generationRef.current === generation) {
        generationRef.current += 1;
      }
      controller.abort();
    };
  }, [accessToken, namesKey, productId, repositoryId, side]);

  return items;
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
  const versionControllerRef = useRef<AbortController | null>(null);
  const versionGenerationRef = useRef(0);
  const submitPendingRef = useRef(false);
  const [currentCandidateVersion, setCurrentCandidateVersion] =
    useState(candidateVersionProp);
  const [versionState, setVersionState] = useState<
    "error" | "loading" | "ready"
  >(candidateVersionProp === undefined ? "loading" : "ready");
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
  const [configuredDirectBranches, setConfiguredDirectBranches] = useState<
    string[]
  >([]);
  const [configuredKeysBranches, setConfiguredKeysBranches] = useState<
    string[]
  >([]);
  const [configuredTranslationsBranches, setConfiguredTranslationsBranches] =
    useState<string[]>([]);
  const [editingMapping, setEditingMapping] =
    useState<AdminMappingResponse | null>(null);
  const [submitPending, setSubmitPending] = useState(false);
  const [formError, setFormError] = useState<
    | { kind: "conflict"; field: MappingConflictField | null }
    | { kind: "generic" | "invalid" }
    | null
  >(null);

  const loadRepositoryPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      const result = await listAdminRepositories({
        auth: accessToken,
        query: { cursor, limit: 50 },
        signal,
      });
      if (result.data === undefined) {
        throw new Error("repositories unavailable");
      }
      return result.data;
    },
    [accessToken],
  );
  const repositoryCollection = useCursorCollection({
    getItemId: (repository: AdminRepositoryResponse) => repository.id,
    loadPage: loadRepositoryPage,
    queryKey: `mapping-repositories:${productId}:${accessToken}`,
  });

  const loadMappingPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      const result = await listAdminCandidateMappings({
        auth: accessToken,
        path: { product_id: productId },
        query: { cursor, limit: 50 },
        signal,
      });
      if (result.data === undefined) {
        throw new Error("mappings unavailable");
      }
      return result.data;
    },
    [accessToken, productId],
  );
  const mappingCollection = useCursorCollection({
    getItemId: (mapping: AdminMappingResponse) => mapping.id,
    loadPage: loadMappingPage,
    queryKey: `candidate-mappings:${productId}:current-candidate:${accessToken}`,
  });

  const directBranches = useRepositoryBranchCollection({
    accessToken,
    productId,
    repositoryId: directRepositoryId,
    side: "direct",
  });
  const keysBranches = useRepositoryBranchCollection({
    accessToken,
    productId,
    repositoryId: keysRepositoryId,
    side: "keys",
  });
  const translationsBranches = useRepositoryBranchCollection({
    accessToken,
    productId,
    repositoryId: translationsRepositoryId,
    side: "translations",
  });
  const exactDirectBranches = useExactConfiguredBranches({
    accessToken,
    branchNames: configuredDirectBranches,
    productId,
    repositoryId: directRepositoryId,
    side: "direct",
  });
  const exactKeysBranches = useExactConfiguredBranches({
    accessToken,
    branchNames: configuredKeysBranches,
    productId,
    repositoryId: keysRepositoryId,
    side: "keys",
  });
  const exactTranslationsBranches = useExactConfiguredBranches({
    accessToken,
    branchNames: configuredTranslationsBranches,
    productId,
    repositoryId: translationsRepositoryId,
    side: "translations",
  });

  const loadCandidateVersion = useCallback(() => {
    const generation = ++versionGenerationRef.current;
    versionControllerRef.current?.abort();
    const controller = new AbortController();
    versionControllerRef.current = controller;
    queueMicrotask(async () => {
      if (versionGenerationRef.current !== generation) {
        return;
      }
      if (candidateVersionProp !== undefined) {
        setCurrentCandidateVersion(candidateVersionProp);
        setVersionState("ready");
        return;
      }
      setVersionState("loading");
      try {
        const result = await getAdminProduct({
          auth: accessToken,
          path: { product_id: productId },
          signal: controller.signal,
        });
        if (
          controller.signal.aborted ||
          versionGenerationRef.current !== generation
        ) {
          return;
        }
        const version = result.data?.candidate_revision?.version;
        if (version === undefined) {
          setVersionState("error");
          return;
        }
        setCurrentCandidateVersion(version);
        setVersionState("ready");
      } catch {
        if (
          !controller.signal.aborted &&
          versionGenerationRef.current === generation
        ) {
          setVersionState("error");
        }
      }
    });
  }, [accessToken, candidateVersionProp, productId]);

  useEffect(() => {
    loadCandidateVersion();
    return () => {
      versionGenerationRef.current += 1;
      versionControllerRef.current?.abort();
    };
  }, [loadCandidateVersion]);

  const pageState =
    repositoryCollection.status === "error" ||
    mappingCollection.status === "error" ||
    versionState === "error"
      ? "error"
      : repositoryCollection.status === "loading" ||
          mappingCollection.status === "loading" ||
          versionState === "loading"
        ? "loading"
        : "ready";
  const repositories = repositoryCollection.items;
  const mappings = mappingCollection.items;

  function chooseRepository(side: RepositorySide, repositoryId: string) {
    setFormError(null);
    if (side === "direct") {
      setDirectRepositoryId(repositoryId);
      setDirectSourceBranch("");
      setAllowedTargetBranches([]);
      setDefaultTargetBranch("");
      setConfiguredDirectBranches([]);
    } else if (side === "keys") {
      setKeysRepositoryId(repositoryId);
      setKeysSourceBranch("");
      setConfiguredKeysBranches([]);
    } else {
      setTranslationsRepositoryId(repositoryId);
      setTranslationsSourceBranch("");
      setAllowedTargetBranches([]);
      setDefaultTargetBranch("");
      setConfiguredTranslationsBranches([]);
    }
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
    setConfiguredDirectBranches([]);
    setConfiguredKeysBranches([]);
    setConfiguredTranslationsBranches([]);
  }

  function applyTopologyChange() {
    if (pendingTopology === null) {
      return;
    }
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
      setConfiguredDirectBranches([
        mapping.primary_source_branch,
        ...mapping.allowed_target_branches,
      ]);
      setConfiguredKeysBranches([]);
      setConfiguredTranslationsBranches([]);
    } else {
      setDirectRepositoryId("");
      setDirectSourceBranch("");
      setKeysRepositoryId(mapping.primary_repository_id);
      setKeysSourceBranch(mapping.primary_source_branch);
      setTranslationsRepositoryId(mapping.translations_repository_id ?? "");
      setTranslationsSourceBranch(mapping.translations_source_branch ?? "");
      setConfiguredDirectBranches([]);
      setConfiguredKeysBranches([mapping.primary_source_branch]);
      setConfiguredTranslationsBranches([
        mapping.translations_source_branch ?? "",
        ...mapping.allowed_target_branches,
      ]);
    }
  }

  function resetForm(version = currentCandidateVersion) {
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
    const normalizedAllowedTargetBranches = Array.from(
      new Set(allowedTargetBranches),
    );
    const targetIsMember =
      normalizedAllowedTargetBranches.includes(defaultTargetBranch);
    const allowedTargetsAreLive = normalizedAllowedTargetBranches.every(
      (branch) => targetBranchItems.some((item) => item.name === branch),
    );
    const valid =
      currentCandidateVersion !== undefined &&
      normalizedAllowedTargetBranches.length > 0 &&
      defaultTargetBranch.length > 0 &&
      targetIsMember &&
      allowedTargetsAreLive &&
      (topology === "direct"
        ? directRepositoryId.length > 0 &&
          directSourceBranch.length > 0 &&
          directBranchItems.some((branch) => branch.name === directSourceBranch)
        : keysRepositoryId.length > 0 &&
          keysSourceBranch.length > 0 &&
          keysBranchItems.some((branch) => branch.name === keysSourceBranch) &&
          translationsRepositoryId.length > 0 &&
          translationsSourceBranch.length > 0 &&
          translationsBranchItems.some(
            (branch) => branch.name === translationsSourceBranch,
          ));
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
            allowed_target_branches: normalizedAllowedTargetBranches,
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
            allowed_target_branches: normalizedAllowedTargetBranches,
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
        mappingCollection.upsertItems([savedMapping]);
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

  const directBranchItems = mergeBranches(
    directBranches.items,
    exactDirectBranches,
  );
  const keysBranchItems = mergeBranches(keysBranches.items, exactKeysBranches);
  const translationsBranchItems = mergeBranches(
    translationsBranches.items,
    exactTranslationsBranches,
  );
  const targetBranchCollection =
    topology === "direct" ? directBranches : translationsBranches;
  const targetBranchItems =
    topology === "direct" ? directBranchItems : translationsBranchItems;
  const Heading = embedded ? "h2" : "h1";

  function retryPage() {
    void repositoryCollection.reload();
    void mappingCollection.reload();
    loadCandidateVersion();
  }

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
            <Button type="button" variant="outline" onClick={retryPage}>
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
        <section className="grid min-w-0 max-w-full gap-4 overflow-x-clip">
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
          <CursorCollectionControls
            collection={mappingCollection}
            noun="mapping"
            loadMoreLabel="Load more mappings"
          />
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
            <CursorCollectionControls
              collection={repositoryCollection}
              noun="repository"
              loadMoreLabel="Load more repositories for mappings"
            />
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
                branchItems={directBranchItems}
                collection={directBranches}
                repositorySelected={directRepositoryId.length > 0}
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
                  branchItems={keysBranchItems}
                  collection={keysBranches}
                  repositorySelected={keysRepositoryId.length > 0}
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
                  branchItems={translationsBranchItems}
                  collection={translationsBranches}
                  repositorySelected={translationsRepositoryId.length > 0}
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
            {targetBranchCollection.status === "loading" ? (
              <p role="status">Loading live branches</p>
            ) : null}
            {targetBranchCollection.status === "error" ? (
              <Alert variant="destructive">
                <AlertTitle>Branches unavailable</AlertTitle>
                <AlertDescription>
                  The repository or branch is no longer available. Refresh
                  branches and update this mapping.
                </AlertDescription>
              </Alert>
            ) : null}
            {targetBranchCollection.status === "ready" ? (
              <div className="grid gap-2">
                {targetBranchItems.map((branch) => {
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
  repositories: readonly AdminRepositoryResponse[];
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

function CursorCollectionControls<TItem>({
  collection,
  loadMoreLabel,
  noun,
}: {
  collection: CursorCollectionState<TItem>;
  loadMoreLabel: string;
  noun: string;
}) {
  if (collection.status !== "ready") {
    return null;
  }
  const pluralNoun = noun.endsWith("y")
    ? `${noun.slice(0, -1)}ies`
    : /(ch|sh|s|x|z)$/.test(noun)
      ? `${noun}es`
      : `${noun}s`;
  const itemNoun = collection.items.length === 1 ? noun : pluralNoun;
  return (
    <div className="grid min-w-0 gap-2 sm:flex sm:flex-wrap sm:items-center sm:justify-between">
      <p className="min-w-0 text-sm text-muted-foreground" aria-live="polite">
        {collection.isPartial
          ? `${collection.items.length} ${itemNoun} loaded — more available`
          : `All ${collection.items.length} ${itemNoun} loaded`}
      </p>
      {collection.isPartial ? (
        <Button
          type="button"
          variant="outline"
          disabled={collection.loadingMore}
          aria-busy={collection.loadingMore}
          aria-label={loadMoreLabel}
          onClick={() => void collection.loadMore()}
        >
          Load more
        </Button>
      ) : null}
      {collection.loadMoreError ? (
        <Alert variant="destructive" className="sm:basis-full">
          <AlertTitle>More {noun}s unavailable</AlertTitle>
          <AlertDescription>
            The items already loaded are unchanged. Retry this page only.
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}

function BranchSelect({
  branchItems,
  collection,
  label,
  onValueChange,
  repositorySelected,
  value,
}: {
  branchItems: readonly AdminBranchResponse[];
  collection: CursorCollectionState<AdminBranchResponse>;
  label: string;
  onValueChange: (value: string) => void;
  repositorySelected: boolean;
  value: string;
}) {
  const id = useId();
  return (
    <div className="grid min-w-0 gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select
        key={`${value}:${branchItems.some((branch) => branch.name === value) ? "live" : "missing"}`}
        value={value}
        disabled={!repositorySelected || collection.status !== "ready"}
        onValueChange={onValueChange}
      >
        <SelectTrigger id={id} className="w-full min-w-0">
          <SelectValue
            placeholder={
              repositorySelected && collection.status === "loading"
                ? "Loading live branches"
                : "Select a live branch"
            }
          >
            {value.length > 0 &&
            branchItems.some((branch) => branch.name === value)
              ? value
              : undefined}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {branchItems.map((branch) => (
            <SelectItem key={branch.name} value={branch.name}>
              {branch.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {repositorySelected ? (
        <CursorCollectionControls
          collection={collection}
          noun="branch"
          loadMoreLabel={`Load more branches for ${label}`}
        />
      ) : null}
      {repositorySelected && collection.status === "error" ? (
        <p className="text-sm text-destructive">
          Live branches are unavailable for this repository.
        </p>
      ) : null}
    </div>
  );
}
