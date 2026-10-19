import { t, useUiLanguage } from "@/i18n";
import {
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type Ref,
} from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  createAdminCandidateMapping,
  getAdminProduct,
  getAdminRepository,
  getAdminRepositoryBranch,
  listAdminCandidateMappings,
  listAdminRepositories,
  listAdminRepositoryBranches,
  updateAdminCandidateMapping,
  type AdminBranchResponse,
  type CodeSourceConfig,
  type AdminDirectMappingWriteRequest,
  type AdminMappingResponse,
  type AdminRepositoryResponse,
  type AdminSeparateMappingWriteRequest,
} from "../../../api/client";
import { useDirtyFormNavigationGuard } from "../../../components/navigation/DirtyFormNavigationGuard";
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
import { Input } from "../../../components/ui/input";
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
import { CodeSourceFields } from "./CodeSourceFields";
import { PublishedMappingImports } from "../imports/PublishedMappingImports";

type Topology = "direct" | "separate";
type RepositorySide = "direct" | "keys" | "translations";
type MappingConflictField =
  | "allowed_target_branches"
  | "candidate_version"
  | "keys_source_branch"
  | "mapping_identity"
  | "source_branch"
  | "translations_source_branch";

interface MappingDraftFingerprintInput {
  codeSource?: CodeSourceConfig | null;
  primaryRoot?: string;
  translationsRoot?: string;
  allowedTargetBranches: string[];
  defaultTargetBranch: string;
  directRepositoryId: string;
  directSourceBranch: string;
  keysRepositoryId: string;
  keysSourceBranch: string;
  topology: Topology;
  translationsRepositoryId: string;
  translationsSourceBranch: string;
}

function mappingDraftFingerprint(input: MappingDraftFingerprintInput) {
  const allowedTargetBranches = Array.from(
    new Set(input.allowedTargetBranches),
  ).sort();
  return JSON.stringify(
    input.topology === "direct"
      ? {
          allowedTargetBranches,
          defaultTargetBranch: input.defaultTargetBranch,
          primaryRepositoryId: input.directRepositoryId,
          primarySourceBranch: input.directSourceBranch,
          primaryRoot: input.primaryRoot ?? "",
          translationsRoot: "",
          topology: input.topology,
          translationsRepositoryId: null,
          translationsSourceBranch: null,
        }
      : {
          allowedTargetBranches,
          defaultTargetBranch: input.defaultTargetBranch,
          primaryRepositoryId: input.keysRepositoryId,
          primarySourceBranch: input.keysSourceBranch,
          primaryRoot: input.primaryRoot ?? "",
          translationsRoot: input.translationsRoot ?? "",
          codeSource: input.codeSource ?? null,
          topology: input.topology,
          translationsRepositoryId: input.translationsRepositoryId,
          translationsSourceBranch: input.translationsSourceBranch,
        },
  );
}

function savedMappingFingerprint(mapping: AdminMappingResponse | null) {
  if (mapping === null) {
    return mappingDraftFingerprint({
      allowedTargetBranches: [],
      defaultTargetBranch: "",
      directRepositoryId: "",
      directSourceBranch: "",
      keysRepositoryId: "",
      keysSourceBranch: "",
      topology: "direct",
      translationsRepositoryId: "",
      translationsSourceBranch: "",
    });
  }
  return mappingDraftFingerprint({
    allowedTargetBranches: mapping.allowed_target_branches,
    defaultTargetBranch: mapping.default_target_branch,
    directRepositoryId:
      mapping.topology === "direct" ? mapping.primary_repository_id : "",
    directSourceBranch:
      mapping.topology === "direct" ? mapping.primary_source_branch : "",
    keysRepositoryId:
      mapping.topology === "separate" ? mapping.primary_repository_id : "",
    keysSourceBranch:
      mapping.topology === "separate" ? mapping.primary_source_branch : "",
    topology: mapping.topology,
    translationsRepositoryId: mapping.translations_repository_id ?? "",
    translationsSourceBranch: mapping.translations_source_branch ?? "",
    primaryRoot: mapping.primary_localization_root ?? "",
    translationsRoot: mapping.translations_localization_root ?? "",
    codeSource: mapping.code_source ?? null,
  });
}

export interface ProductMappingsPageHandle {
  saveAndContinue: () => Promise<boolean>;
}

export interface ProductMappingsPageProps {
  ref?: Ref<ProductMappingsPageHandle>;
  accessToken: string;
  candidateVersion?: number;
  selectedRepositoryIds?: readonly string[];
  embedded?: boolean;
  onCandidateVersionChange?: (version: number) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onContinueRequested?: () => Promise<void>;
  productId: string;
}

function repositoryLabel(repository: AdminRepositoryResponse) {
  const providerIdentity = `${repository.provider === "github" ? t("GitHub · ") : ""}${repository.workspace}/${repository.repository_slug}`;
  return repository.descriptive_name === null
    ? providerIdentity
    : `${repository.descriptive_name} — ${providerIdentity}`;
}

function branchMatchesQuery(branchName: string, query: string) {
  return branchName
    .toLocaleLowerCase()
    .includes(query.trim().toLocaleLowerCase());
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
      return t(
        "The allowed target branches changed. Your selections are still here. Refresh branches and try again.",
      );
    case "candidate_version":
      return t(
        "This draft changed in another session. Your entries are still here.",
      );
    case "keys_source_branch":
      return t(
        "The Keys source branch changed. Your selections are still here. Refresh branches and try again.",
      );
    case "translations_source_branch":
      return t(
        "The Translations source branch changed. Your selections are still here. Refresh branches and try again.",
      );
    case "source_branch":
      return t(
        "The source branch changed. Your selections are still here. Refresh branches and try again.",
      );
    default:
      return t(
        "This mapping conflicts with the current draft. Your selections are still here.",
      );
  }
}

function MappingBranchDetails({ mapping }: { mapping: AdminMappingResponse }) {
  useUiLanguage();
  return (
    <div
      role="region"
      aria-label={t("Mapping branch details")}
      // The UI contract requires local keyboard-focusable overflow for opaque branches.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="w-max min-w-full space-y-1 font-mono text-sm">
        <p>
          {mapping.topology === "direct" ? t("Source") : t("Keys source")}:{" "}
          {mapping.primary_source_branch}
        </p>
        {mapping.translations_source_branch === null ? null : (
          <p>
            <span>{t("Translations source: ")}</span>
            <span>{mapping.translations_source_branch}</span>
          </p>
        )}
        <p>
          <span>{t("Default target: ")}</span>
          <span>{mapping.default_target_branch}</span>
        </p>
        <p>
          <span>{t("Allowed targets: ")}</span>
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
      generationRef.current += 1;
      controller.abort();
    };
  }, [accessToken, namesKey, productId, repositoryId, side]);

  return items;
}

export function ProductMappingsPage({
  ref,
  accessToken,
  candidateVersion: candidateVersionProp,
  embedded = false,
  selectedRepositoryIds,
  onCandidateVersionChange,
  onDirtyChange,
  onContinueRequested,
  productId,
}: ProductMappingsPageProps) {
  useUiLanguage();
  const directId = useId();
  const separateId = useId();
  const defaultTargetId = useId();
  const targetSearchId = useId();
  const targetSearchRef = useRef<HTMLInputElement>(null);
  const versionControllerRef = useRef<AbortController | null>(null);
  const versionGenerationRef = useRef(0);
  const submitPendingRef = useRef(false);
  const formErrorRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLDetailsElement>(null);
  const [importAuthority, setImportAuthority] = useState<{
    productId: string;
    accessToken: string;
    generation: number;
    published: boolean;
    active: boolean;
  } | null>(null);
  const [currentCandidateVersion, setCurrentCandidateVersion] =
    useState(candidateVersionProp);
  const [versionState, setVersionState] = useState<
    "error" | "loading" | "ready" | "published"
  >("loading");
  const [codeSource, setCodeSource] = useState<CodeSourceConfig | null>(null);
  const [topology, setTopology] = useState<Topology>("direct");
  const [pendingTopology, setPendingTopology] = useState<Topology | null>(null);
  const [directRepositoryId, setDirectRepositoryId] = useState("");
  const [keysRepositoryId, setKeysRepositoryId] = useState("");
  const [translationsRepositoryId, setTranslationsRepositoryId] = useState("");
  const [directSourceBranch, setDirectSourceBranch] = useState("");
  const [primaryRoot, setPrimaryRoot] = useState("");
  const [translationsRoot, setTranslationsRoot] = useState("");
  const [keysSourceBranch, setKeysSourceBranch] = useState("");
  const [translationsSourceBranch, setTranslationsSourceBranch] = useState("");
  const [allowedTargetBranches, setAllowedTargetBranches] = useState<string[]>(
    [],
  );
  const [defaultTargetBranch, setDefaultTargetBranch] = useState("");
  const [targetBranchQuery, setTargetBranchQuery] = useState("");
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
  const currentDraftFingerprint = useMemo(
    () =>
      mappingDraftFingerprint({
        primaryRoot,
        translationsRoot,
        codeSource,
        allowedTargetBranches,
        defaultTargetBranch,
        directRepositoryId,
        directSourceBranch,
        keysRepositoryId,
        keysSourceBranch,
        topology,
        translationsRepositoryId,
        translationsSourceBranch,
      }),
    [
      primaryRoot,
      translationsRoot,
      codeSource,
      allowedTargetBranches,
      defaultTargetBranch,
      directRepositoryId,
      directSourceBranch,
      keysRepositoryId,
      keysSourceBranch,
      topology,
      translationsRepositoryId,
      translationsSourceBranch,
    ],
  );
  const baselineDraftFingerprint = useMemo(
    () => savedMappingFingerprint(editingMapping),
    [editingMapping],
  );
  useEffect(() => {
    onDirtyChange?.(currentDraftFingerprint !== baselineDraftFingerprint);
    return () => onDirtyChange?.(false);
  }, [onDirtyChange, currentDraftFingerprint, baselineDraftFingerprint]);
  useDirtyFormNavigationGuard(
    `mapping:${productId}`,
    currentDraftFingerprint !== baselineDraftFingerprint,
  );

  const selectedRepositoriesKey = JSON.stringify(selectedRepositoryIds ?? null);
  const loadRepositoryPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      const selectedIds: string[] | null = JSON.parse(selectedRepositoriesKey);
      if (selectedIds !== null) {
        const items: AdminRepositoryResponse[] = [];
        for (const id of selectedIds) {
          const selected = await getAdminRepository({
            auth: accessToken,
            path: { repository_id: id },
            signal,
          });
          if (!selected.data)
            throw new Error("Selected repository unavailable");
          items.push(selected.data);
        }
        return { items, next_cursor: null };
      }
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
    [accessToken, selectedRepositoriesKey],
  );
  const repositoryCollection = useCursorCollection({
    getItemId: (repository: AdminRepositoryResponse) => repository.id,
    loadPage: loadRepositoryPage,
    queryKey: `mapping-repositories:${productId}:${accessToken}:${selectedRepositoriesKey}`,
  });

  const loadMappingPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      if (
        versionState !== "ready" ||
        importAuthority?.productId !== productId ||
        importAuthority.accessToken !== accessToken
      ) {
        return { items: [], next_cursor: null };
      }
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
    [accessToken, importAuthority, productId, versionState],
  );
  const mappingCollection = useCursorCollection({
    getItemId: (mapping: AdminMappingResponse) => mapping.id,
    loadPage: loadMappingPage,
    queryKey: `candidate-mappings:${productId}:${importAuthority?.productId}:${importAuthority?.generation}:${versionState}:${currentCandidateVersion}:${accessToken}`,
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
      setImportAuthority(null);
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
        if (result.data === undefined) {
          setVersionState("error");
          return;
        }
        setImportAuthority({
          productId,
          accessToken,
          generation,
          published: result.data.active_revision != null,
          active: result.data.is_active === true,
        });
        const version =
          result.data.candidate_revision == null
            ? undefined
            : (candidateVersionProp ?? result.data.candidate_revision.version);
        if (version === undefined) {
          setCurrentCandidateVersion(undefined);
          setVersionState(
            result.data.active_revision != null ? "published" : "error",
          );
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
        : versionState === "published"
          ? "published"
          : "ready";
  const repositories = repositoryCollection.items;
  const githubTarget = repositories.some(
    (repository) =>
      repository.provider === "github" &&
      repository.id ===
        (topology === "direct" ? directRepositoryId : translationsRepositoryId),
  );
  const mappings = mappingCollection.items;

  function chooseRepository(side: RepositorySide, repositoryId: string) {
    setFormError(null);
    if (side === "direct") {
      setDirectRepositoryId(repositoryId);
      setDirectSourceBranch("");
      setAllowedTargetBranches([]);
      setDefaultTargetBranch("");
      setTargetBranchQuery("");
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
      setTargetBranchQuery("");
      setConfiguredTranslationsBranches([]);
    }
  }

  function clearMappingSelection() {
    setCodeSource(null);
    setPrimaryRoot("");
    setTranslationsRoot("");
    setDirectRepositoryId("");
    setKeysRepositoryId("");
    setTranslationsRepositoryId("");
    setDirectSourceBranch("");
    setKeysSourceBranch("");
    setTranslationsSourceBranch("");
    setAllowedTargetBranches([]);
    setDefaultTargetBranch("");
    setTargetBranchQuery("");
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
    const next = checked
      ? Array.from(new Set([...allowedTargetBranches, branch]))
      : allowedTargetBranches.filter((item) => item !== branch);
    setAllowedTargetBranches(next);
    setDefaultTargetBranch((current) =>
      next.includes(current) ? current : (next[0] ?? ""),
    );
  }

  function beginEdit(mapping: AdminMappingResponse) {
    setCodeSource(mapping.code_source ?? null);
    setPrimaryRoot(mapping.primary_localization_root ?? "");
    setTranslationsRoot(mapping.translations_localization_root ?? "");
    setEditingMapping(mapping);
    setTopology(mapping.topology);
    setCurrentCandidateVersion(mapping.candidate_version);
    setAllowedTargetBranches(mapping.allowed_target_branches);
    setDefaultTargetBranch(mapping.default_target_branch);
    setTargetBranchQuery("");
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

  async function saveMapping(): Promise<boolean> {
    if (submitPendingRef.current) {
      return false;
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
      return false;
    }

    const body:
      AdminDirectMappingWriteRequest | AdminSeparateMappingWriteRequest =
      topology === "direct"
        ? {
            topology: "direct",
            repository_id: directRepositoryId,
            source_branch: directSourceBranch,
            ...(primaryRoot ? { localization_root: primaryRoot } : {}),
            allowed_target_branches: normalizedAllowedTargetBranches,
            default_target_branch: defaultTargetBranch,
            expected_candidate_version: currentCandidateVersion,
          }
        : {
            topology: "separate",
            ...(codeSource ? { code_source: codeSource } : {}),
            sides: [
              {
                role: "keys",
                repository_id: keysRepositoryId,
                source_branch: keysSourceBranch,
                ...(primaryRoot ? { localization_root: primaryRoot } : {}),
              },
              {
                role: "translations",
                repository_id: translationsRepositoryId,
                source_branch: translationsSourceBranch,
                ...(translationsRoot
                  ? { localization_root: translationsRoot }
                  : {}),
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
        toast.success(t("Draft saved"));
        return true;
      }
      if (responseStatus(result) === 409) {
        setFormError({
          kind: "conflict",
          field: conflictField(result.error),
        });
        return false;
      }
      setFormError({ kind: "generic" });
    } catch {
      setFormError({ kind: "generic" });
    } finally {
      submitPendingRef.current = false;
      setSubmitPending(false);
    }
    return false;
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
  const filteredTargetBranchItems = targetBranchItems.filter((branch) =>
    branchMatchesQuery(branch.name, targetBranchQuery),
  );
  const availableTargetBranchItems = filteredTargetBranchItems.filter(
    (branch) => !allowedTargetBranches.includes(branch.name),
  );
  const targetSearchActive = targetBranchQuery.trim().length > 0;
  const targetRepositorySelected =
    topology === "direct"
      ? directRepositoryId.length > 0
      : translationsRepositoryId.length > 0;
  const {
    isPartial: targetBranchesPartial,
    loadMore: loadMoreTargetBranches,
    loadMoreError: targetBranchesLoadMoreError,
    loadingMore: loadingMoreTargetBranches,
    status: targetBranchesStatus,
  } = targetBranchCollection;

  useEffect(() => {
    if (
      targetSearchActive &&
      targetBranchesStatus === "ready" &&
      targetBranchesPartial &&
      !loadingMoreTargetBranches &&
      !targetBranchesLoadMoreError
    ) {
      void loadMoreTargetBranches();
    }
  }, [
    loadMoreTargetBranches,
    loadingMoreTargetBranches,
    targetSearchActive,
    targetBranchesLoadMoreError,
    targetBranchesPartial,
    targetBranchesStatus,
  ]);
  useEffect(() => {
    if (formError !== null) {
      if (editorRef.current) editorRef.current.open = true;
      formErrorRef.current?.focus();
    }
  }, [formError]);

  useImperativeHandle(ref, () => ({
    async saveAndContinue() {
      if (
        submitPendingRef.current ||
        pendingTopology !== null ||
        pageState !== "ready"
      )
        return false;
      if (
        mappings.length > 0 &&
        currentDraftFingerprint === baselineDraftFingerprint
      )
        return true;
      return saveMapping();
    },
  }));

  function renderTargetBranchOption(branchName: string) {
    const checkboxId = `${defaultTargetId}-${branchName}`;
    const selected = allowedTargetBranches.includes(branchName);
    return (
      <div
        key={branchName}
        className="relative flex min-h-11 min-w-0 flex-wrap items-center gap-3 rounded-md border bg-background px-3 py-2"
      >
        <Checkbox
          id={checkboxId}
          checked={selected}
          aria-label={t("Allow target {{v0}}", { v0: branchName })}
          onCheckedChange={(checked) => {
            toggleAllowedTarget(branchName, checked === true);
            targetSearchRef.current?.focus();
          }}
        />
        <Label
          htmlFor={checkboxId}
          className="min-w-0 break-words font-mono [overflow-wrap:anywhere]"
        >
          {branchName}
        </Label>
        {selected && defaultTargetBranch === branchName ? (
          <span className="ml-auto rounded-full bg-success/15 px-2 py-1 text-xs font-semibold text-success">
            {t("Default")}
          </span>
        ) : selected ? (
          <Button
            type="button"
            variant="ghost"
            className="ml-auto"
            aria-label={t("Make {{v0}} the default target", { v0: branchName })}
            onClick={() => {
              setDefaultTargetBranch(branchName);
              setFormError(null);
            }}
          >
            {t("Make default")}
          </Button>
        ) : null}
      </div>
    );
  }

  const Heading = embedded ? "h2" : "h1";

  function retryPage() {
    void repositoryCollection.reload();
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
          {t("Translation sources")}
        </Heading>
        <p className="text-muted-foreground">
          {t("Select the repository and branch with your translations.")}
        </p>
      </div>

      {pageState === "loading" ? (
        <section className="grid gap-3" role="status" aria-live="polite">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <span>{t("Loading mappings")}</span>
        </section>
      ) : null}

      {pageState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>{t("Mappings unavailable")}</AlertTitle>
          <AlertDescription>
            <Button type="button" variant="outline" onClick={retryPage}>
              {t("Retry loading page")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {pageState === "published" ? (
        <Alert>
          <AlertTitle>{t("No draft changes")}</AlertTitle>
          <AlertDescription className="grid gap-3">
            <p>
              {t("Edit the configuration to change repositories or branches.")}
            </p>
            <Button asChild variant="outline" className="w-fit">
              <Link
                to={`/admin/products/${encodeURIComponent(productId)}/edit`}
              >
                {t("Edit product configuration")}
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {pageState === "ready" && mappings.length > 0 ? (
        <section className="grid min-w-0 max-w-full gap-4 overflow-x-clip">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-heading font-semibold">
              {t("Saved translation sources")}
            </h3>
            {!embedded ? (
              <Button asChild>
                <Link
                  to={`/admin/products/${encodeURIComponent(productId)}/preview`}
                >
                  {t("Preview and import")}
                </Link>
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t("Continue to preview when all sources are saved.")}
              </p>
            )}
          </div>
          <div className="hidden min-w-0 max-w-full md:block">
            <Table
              aria-label={t("Translation sources")}
              className="table-fixed"
            >
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Source setup")}</TableHead>
                  <TableHead>{t("Repositories")}</TableHead>
                  <TableHead>{t("Branches")}</TableHead>
                  <TableHead>{t("Draft")}</TableHead>
                  <TableHead>{t("Action")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.map((mapping) => (
                  <TableRow key={mapping.id}>
                    <TableCell className="capitalize">
                      {mapping.topology === "direct"
                        ? t("One repository")
                        : t("Two repositories")}
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
                      {t("Draft version ")}
                      {mapping.candidate_version}
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => beginEdit(mapping)}
                      >
                        {t("Edit mapping")}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div
            className="grid min-w-0 max-w-full divide-y md:hidden"
            aria-label={t("Translation sources mobile list")}
          >
            {mappings.map((mapping) => (
              <article key={mapping.id} className="grid min-w-0 gap-3 py-4">
                <strong>
                  {mapping.topology === "direct"
                    ? t("One repository")
                    : t("Two repositories")}
                </strong>
                <p className="break-words [overflow-wrap:anywhere]">
                  {repositoryName(mapping.primary_repository_id)}
                  {mapping.translations_repository_id === null
                    ? null
                    : ` / ${repositoryName(mapping.translations_repository_id)}`}
                </p>
                <MappingBranchDetails mapping={mapping} />
                <p>
                  {t("Draft version ")}
                  {mapping.candidate_version}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => beginEdit(mapping)}
                >
                  {t("Edit mapping")}
                </Button>
              </article>
            ))}
          </div>
          <CursorCollectionControls
            collection={mappingCollection}
            noun="mapping"
            loadMoreLabel={t("Load more mappings")}
          />
        </section>
      ) : null}

      {pageState === "ready" ? (
        <details
          ref={editorRef}
          open={editingMapping !== null || mappings.length === 0}
          className="min-w-0 w-full rounded-lg border bg-secondary"
        >
          <summary className="cursor-pointer px-6 py-4 text-heading font-semibold">
            {editingMapping === null
              ? mappings.length === 0
                ? t("Configure a translation source")
                : t("Add another translation source")
              : t("Edit translation source")}
          </summary>
          <form
            className="p-6 pt-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (embedded) void onContinueRequested?.();
              else void saveMapping();
            }}
          >
            <fieldset disabled={submitPending} className="grid min-w-0 gap-6">
              <h3 className="sr-only">
                {editingMapping === null ? t("Add mapping") : t("Edit mapping")}
              </h3>
              {repositoryCollection.isPartial ||
              repositoryCollection.loadMoreError ? (
                <CursorCollectionControls
                  collection={repositoryCollection}
                  noun="repository"
                  loadMoreLabel={t("Load more repositories for mappings")}
                />
              ) : null}

              {topology === "direct" ? (
                <div className="grid items-start gap-4 md:grid-cols-2">
                  <RepositorySelect
                    label={t("Repository")}
                    repositories={repositories}
                    value={directRepositoryId}
                    onValueChange={(value) => chooseRepository("direct", value)}
                  />
                  <BranchSelect
                    key={`direct-source:${directRepositoryId}`}
                    label={t("Source branch")}
                    branchItems={directBranchItems}
                    collection={directBranches}
                    repositoryId={directRepositoryId}
                    value={directSourceBranch}
                    onValueChange={(value) => {
                      setDirectSourceBranch(value);
                      if (githubTarget) {
                        setAllowedTargetBranches([value]);
                        setDefaultTargetBranch(value);
                      }
                      setFormError(null);
                    }}
                  />
                </div>
              ) : (
                <div className="grid gap-6">
                  <fieldset className="grid items-start gap-4 rounded-md border p-4 md:grid-cols-2">
                    <legend className="px-1 text-sm font-semibold">
                      {t("Keys repository")}
                    </legend>
                    <RepositorySelect
                      label={t("Keys repository")}
                      repositories={repositories}
                      value={keysRepositoryId}
                      onValueChange={(value) => chooseRepository("keys", value)}
                    />
                    <BranchSelect
                      key={`keys-source:${keysRepositoryId}`}
                      label={t("Keys source branch")}
                      branchItems={keysBranchItems}
                      collection={keysBranches}
                      repositoryId={keysRepositoryId}
                      value={keysSourceBranch}
                      onValueChange={(value) => {
                        setKeysSourceBranch(value);
                        setFormError(null);
                      }}
                    />
                  </fieldset>
                  <fieldset className="grid items-start gap-4 rounded-md border p-4 md:grid-cols-2">
                    <legend className="px-1 text-sm font-semibold">
                      {t("Translations repository")}
                    </legend>
                    <RepositorySelect
                      label={t("Translations repository")}
                      repositories={repositories}
                      value={translationsRepositoryId}
                      onValueChange={(value) =>
                        chooseRepository("translations", value)
                      }
                    />
                    <BranchSelect
                      key={`translations-source:${translationsRepositoryId}`}
                      label={t("Translations source branch")}
                      branchItems={translationsBranchItems}
                      collection={translationsBranches}
                      repositoryId={translationsRepositoryId}
                      value={translationsSourceBranch}
                      onValueChange={(value) => {
                        setTranslationsSourceBranch(value);
                        if (githubTarget) {
                          setAllowedTargetBranches([value]);
                          setDefaultTargetBranch(value);
                        }
                        setFormError(null);
                      }}
                    />
                  </fieldset>
                </div>
              )}

              <details
                className="rounded-md border p-4"
                open={topology === "separate"}
              >
                <summary className="cursor-pointer text-sm font-semibold">
                  {t("Advanced repository settings")}
                </summary>
                <div className="pt-4">
                  <fieldset className="grid gap-3">
                    <legend className="text-sm font-semibold">
                      {t("Where are keys and translations stored?")}
                    </legend>
                    <RadioGroup
                      value={topology}
                      onValueChange={(value) => {
                        if (value !== topology) {
                          setPendingTopology(value as Topology);
                        }
                      }}
                      className="grid gap-3 md:grid-cols-2"
                    >
                      <div className="flex min-h-11 items-center gap-3 rounded-md border p-3 has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5">
                        <RadioGroupItem id={directId} value="direct" />
                        <div className="grid gap-1">
                          <Label htmlFor={directId}>
                            {t("Same repository")}
                          </Label>
                          <p className="text-sm text-muted-foreground">
                            {t("Keys and translated files live together.")}
                          </p>
                        </div>
                      </div>
                      <div className="flex min-h-11 items-center gap-3 rounded-md border p-3 has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5">
                        <RadioGroupItem id={separateId} value="separate" />
                        <div className="grid gap-1">
                          <Label htmlFor={separateId}>
                            {t("Separate repositories")}
                          </Label>
                          <p className="text-sm text-muted-foreground">
                            {t(
                              "Separate repositories for keys and translations.",
                            )}
                          </p>
                        </div>
                      </div>
                    </RadioGroup>
                  </fieldset>
                </div>
              </details>

              {topology === "separate" && (
                <CodeSourceFields value={codeSource} onChange={setCodeSource} />
              )}

              <details
                className="rounded-md border p-4"
                open={primaryRoot !== "" || translationsRoot !== ""}
              >
                <summary className="cursor-pointer text-sm font-semibold">
                  {t("Limit the search to a folder (optional)")}
                </summary>
                <div className="pt-4">
                  <div className="grid gap-3">
                    <Label htmlFor={`${directId}-root`}>
                      {topology === "direct"
                        ? t("Localization root (optional)")
                        : t("Keys localization root (optional)")}
                    </Label>
                    <Input
                      id={`${directId}-root`}
                      maxLength={4096}
                      value={primaryRoot}
                      onChange={(event) => setPrimaryRoot(event.target.value)}
                      placeholder={t("shared/src/commonMain/moko-resources")}
                    />
                    <p className="text-sm text-muted-foreground">
                      {t(
                        "Relative directory, without leading or trailing slashes. Leave empty for the repository root.",
                      )}
                    </p>
                    {topology === "separate" ? (
                      <>
                        <Label htmlFor={`${separateId}-root`}>
                          {t("Translations localization root (optional)")}
                        </Label>
                        <Input
                          id={`${separateId}-root`}
                          maxLength={4096}
                          value={translationsRoot}
                          onChange={(event) =>
                            setTranslationsRoot(event.target.value)
                          }
                        />
                      </>
                    ) : null}
                  </div>
                </div>
              </details>

              {githubTarget ? (
                <Alert>
                  <AlertTitle>{t("GitHub · Import only")}</AlertTitle>
                  <AlertDescription>
                    {t(
                      "Translations can be imported, refreshed and edited locally. Sending commits or pull requests to GitHub is not available.",
                    )}
                  </AlertDescription>
                </Alert>
              ) : (
                <>
                  <fieldset className="grid gap-3">
                    <legend className="text-sm font-semibold">
                      {t("Where should future translation changes go?")}
                    </legend>
                    <p className="text-sm text-muted-foreground">
                      {t(
                        "Pull request targets. The first selected branch is the default.",
                      )}
                    </p>
                    <div className="grid gap-2">
                      <Label htmlFor={targetSearchId}>
                        {t("Search target branches")}
                      </Label>
                      <Input
                        ref={targetSearchRef}
                        id={targetSearchId}
                        type="search"
                        autoComplete="off"
                        value={targetBranchQuery}
                        disabled={!targetRepositorySelected}
                        placeholder={t("Type part of a branch name")}
                        aria-describedby={`${targetSearchId}-hint`}
                        onChange={(event) =>
                          setTargetBranchQuery(event.target.value)
                        }
                      />
                      <p
                        id={`${targetSearchId}-hint`}
                        className="text-sm text-muted-foreground"
                      >
                        {targetRepositorySelected
                          ? t(
                              "Type to find branches. Your selections stay below.",
                            )
                          : t(
                              "Choose a repository above to search its branches.",
                            )}
                      </p>
                    </div>
                    {targetSearchActive &&
                    targetBranchCollection.status === "loading" ? (
                      <p role="status">{t("Searching branches…")}</p>
                    ) : null}
                    {targetRepositorySelected &&
                    targetBranchCollection.status === "error" ? (
                      <Alert variant="destructive">
                        <AlertTitle>{t("Branches unavailable")}</AlertTitle>
                        <AlertDescription>
                          {t("We could not load branches. Retry your search.")}
                        </AlertDescription>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void targetBranchCollection.reload()}
                        >
                          {t("Retry target branch search")}
                        </Button>
                      </Alert>
                    ) : null}
                    {targetSearchActive &&
                    targetBranchCollection.status === "ready" ? (
                      <div className="grid min-w-0 gap-2">
                        <p
                          className="text-sm text-muted-foreground"
                          role="status"
                        >
                          {targetBranchCollection.isPartial
                            ? targetBranchCollection.loadMoreError
                              ? t(
                                  "Search incomplete. Retry to find more branches.",
                                )
                              : t("Searching branches…")
                            : t("{{v0}} matching {{v1}}", {
                                v0: filteredTargetBranchItems.length,
                                v1:
                                  filteredTargetBranchItems.length === 1
                                    ? t("branch")
                                    : t("branches"),
                              })}
                        </p>
                        {availableTargetBranchItems.length > 0 ? (
                          <div
                            role="group"
                            aria-label={t("Target branch search results")}
                            className="grid max-h-64 min-w-0 gap-2 overflow-y-auto overscroll-contain rounded-md border p-2"
                          >
                            {availableTargetBranchItems.map((branch) =>
                              renderTargetBranchOption(branch.name),
                            )}
                          </div>
                        ) : !targetBranchCollection.isPartial ? (
                          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                            {filteredTargetBranchItems.length > 0
                              ? t("All matching branches are already selected.")
                              : t("No live branches match “{{v0}}”.", {
                                  v0: targetBranchQuery.trim(),
                                })}
                          </p>
                        ) : null}
                        {targetBranchCollection.loadMoreError ? (
                          <Button
                            type="button"
                            variant="outline"
                            className="justify-self-start"
                            onClick={() => void loadMoreTargetBranches()}
                          >
                            {t("Retry target branch search")}
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                    {allowedTargetBranches.length > 0 ? (
                      <div className="grid min-w-0 gap-2">
                        <p className="text-sm font-semibold">
                          {t("Selected target branches")}
                        </p>
                        <div
                          role="group"
                          aria-label={t("Selected target branches")}
                          className="grid max-h-48 min-w-0 gap-2 overflow-y-auto overscroll-contain p-1"
                        >
                          {allowedTargetBranches.map(renderTargetBranchOption)}
                        </div>
                      </div>
                    ) : null}
                  </fieldset>

                  {allowedTargetBranches.length > 0 ? (
                    <p
                      className="rounded-md border border-success/40 bg-success/10 px-4 py-3 font-mono text-sm text-success"
                      aria-live="polite"
                    >
                      {defaultTargetBranch} {t(" is the default target")}
                    </p>
                  ) : null}
                </>
              )}

              {formError !== null ? (
                <Alert ref={formErrorRef} variant="destructive" tabIndex={-1}>
                  <AlertTitle>{t("Mapping not saved")}</AlertTitle>
                  <AlertDescription>
                    {formError.kind === "conflict"
                      ? conflictCopy(formError.field)
                      : formError.kind === "invalid"
                        ? t(
                            "Choose every repository and source branch, at least one allowed target, and a default target from that set.",
                          )
                        : t(
                            "We could not save this draft. Your entries are still here. Review the error and try again.",
                          )}
                  </AlertDescription>
                </Alert>
              ) : null}

              {!embedded || editingMapping !== null ? (
                <div className="flex flex-wrap justify-end gap-3">
                  {editingMapping === null ? null : (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => resetForm()}
                    >
                      {t("Cancel edit")}
                    </Button>
                  )}
                  {!embedded ? (
                    <Button
                      type="submit"
                      disabled={submitPending}
                      aria-busy={submitPending}
                    >
                      {t("Save mapping")}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </fieldset>
          </form>
        </details>
      ) : null}

      {!embedded &&
      importAuthority?.productId === productId &&
      importAuthority.accessToken === accessToken ? (
        importAuthority.published && importAuthority.active ? (
          <PublishedMappingImports
            key={`${productId}:${accessToken}`}
            accessToken={accessToken}
            compact
            headingLevel={embedded ? "h3" : "h2"}
            productId={productId}
            repositories={repositories}
          />
        ) : (
          <Alert>
            <AlertTitle>{t("Published mapping imports")}</AlertTitle>
            <AlertDescription>
              {importAuthority.published
                ? t(
                    "Reactivate this product before running or refreshing imports.",
                  )
                : t("Publish a validated mapping before running an import.")}
            </AlertDescription>
          </Alert>
        )
      ) : null}

      {pendingTopology === null ? null : (
        <AlertDialog
          open
          onOpenChange={(open) => !open && setPendingTopology(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("Change mapping topology?")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {t(
                  "Changing topology clears the repository and branch selections in this unsaved mapping.",
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("Cancel")}</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                onClick={applyTopologyChange}
              >
                {t("Change topology")}
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
  useUiLanguage();
  const id = useId();
  return (
    <div className="grid min-w-0 content-start gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger id={id} className="w-full min-w-0">
          <SelectValue placeholder={t("Select a repository")} />
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
  useUiLanguage();
  if (collection.status !== "ready") {
    return null;
  }
  const itemNoun =
    noun === "mapping"
      ? collection.items.length === 1
        ? t("mapping")
        : t("mappings")
      : collection.items.length === 1
        ? t("repository")
        : t("repositories");
  return (
    <div className="grid min-w-0 gap-2 sm:flex sm:flex-wrap sm:items-center sm:justify-between">
      <p className="min-w-0 text-sm text-muted-foreground" aria-live="polite">
        {collection.isPartial
          ? t("{{v0}} {{v1}} loaded — more available", {
              v0: collection.items.length,
              v1: itemNoun,
            })
          : t("All {{v0}} {{v1}} loaded", {
              v0: collection.items.length,
              v1: itemNoun,
            })}
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
          {t("Load more")}
        </Button>
      ) : null}
      {collection.loadMoreError ? (
        <Alert variant="destructive" className="sm:basis-full">
          <AlertTitle>
            {noun === "mapping"
              ? t("More mappings unavailable")
              : t("More repositories unavailable")}
          </AlertTitle>
          <AlertDescription>
            {t("The items already loaded are unchanged. Retry this page only.")}
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
  repositoryId,
  value,
}: {
  branchItems: readonly AdminBranchResponse[];
  collection: CursorCollectionState<AdminBranchResponse>;
  label: string;
  onValueChange: (value: string) => void;
  repositoryId: string;
  value: string;
}) {
  useUiLanguage();
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const repositorySelected = repositoryId.length > 0;
  const searchActive = query.trim().length > 0;
  const filteredBranches = branchItems.filter((branch) =>
    branchMatchesQuery(branch.name, query),
  );
  const selectedIsLive =
    value.length > 0 && branchItems.some((branch) => branch.name === value);
  const resultsVisible =
    searchActive &&
    collection.status === "ready" &&
    filteredBranches.length > 0;
  const activeOptionId =
    resultsVisible && activeIndex >= 0 && activeIndex < filteredBranches.length
      ? `${id}-option-${activeIndex}`
      : undefined;
  const {
    isPartial: branchesPartial,
    loadMore: loadMoreBranches,
    loadMoreError: branchesLoadMoreError,
    loadingMore: loadingMoreBranches,
    status: branchesStatus,
  } = collection;

  useEffect(() => {
    if (
      searchActive &&
      branchesStatus === "ready" &&
      branchesPartial &&
      !loadingMoreBranches &&
      !branchesLoadMoreError
    ) {
      void loadMoreBranches();
    }
  }, [
    branchesLoadMoreError,
    branchesPartial,
    branchesStatus,
    loadMoreBranches,
    loadingMoreBranches,
    searchActive,
  ]);

  useEffect(() => {
    if (activeOptionId)
      document
        .getElementById(activeOptionId)
        ?.scrollIntoView({ block: "nearest" });
  }, [activeOptionId]);

  function chooseBranch(branchName: string) {
    onValueChange(branchName);
    setQuery("");
    setActiveIndex(-1);
    inputRef.current?.focus();
  }

  return (
    <div className="grid min-w-0 content-start gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        ref={inputRef}
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={resultsVisible}
        aria-controls={resultsVisible ? `${id}-results` : undefined}
        aria-activedescendant={activeOptionId}
        aria-describedby={selectedIsLive ? `${id}-selected` : `${id}-hint`}
        autoComplete="off"
        value={query}
        disabled={!repositorySelected}
        placeholder={t("Search branches")}
        onChange={(event) => {
          setQuery(event.target.value);
          setActiveIndex(-1);
        }}
        onKeyDown={(event) => {
          if (
            resultsVisible &&
            (event.key === "ArrowDown" || event.key === "ArrowUp")
          ) {
            event.preventDefault();
            setActiveIndex((current) =>
              event.key === "ArrowDown"
                ? (current + 1) % filteredBranches.length
                : current <= 0
                  ? filteredBranches.length - 1
                  : current - 1,
            );
          } else if (event.key === "Enter" && searchActive) {
            event.preventDefault();
            if (
              resultsVisible &&
              activeIndex >= 0 &&
              activeIndex < filteredBranches.length
            ) {
              chooseBranch(filteredBranches[activeIndex].name);
            }
          } else if (event.key === "Escape" && searchActive) {
            event.preventDefault();
            event.stopPropagation();
            setQuery("");
            setActiveIndex(-1);
          }
        }}
      />
      {selectedIsLive ? (
        <p
          id={`${id}-selected`}
          className="min-w-0 rounded-md border bg-primary/5 px-3 py-2 text-sm break-words [overflow-wrap:anywhere]"
        >
          {t("Selected branch:")}{" "}
          <span className="font-mono font-semibold">{value}</span>
        </p>
      ) : (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {repositorySelected
            ? t("Type to find a source branch.")
            : t("Choose a repository first.")}
        </p>
      )}
      {searchActive && collection.status === "loading" ? (
        <p role="status">{t("Searching branches…")}</p>
      ) : null}
      {searchActive && collection.status === "ready" ? (
        <>
          <p className="text-sm text-muted-foreground" role="status">
            {collection.isPartial
              ? collection.loadMoreError
                ? t("Search incomplete. Retry to find more branches.")
                : t("Searching branches…")
              : t("{{v0}} matching {{v1}}", {
                  v0: filteredBranches.length,
                  v1:
                    filteredBranches.length === 1 ? t("branch") : t("branches"),
                })}
          </p>
          {resultsVisible ? (
            <div
              id={`${id}-results`}
              role="listbox"
              aria-label={t("{{v0}} search results", { v0: label })}
              className="grid max-h-64 min-w-0 gap-1 overflow-y-auto overscroll-contain rounded-md border bg-background p-1"
            >
              {filteredBranches.map((branch, index) => (
                <button
                  key={branch.name}
                  id={`${id}-option-${index}`}
                  type="button"
                  role="option"
                  aria-selected={branch.name === value}
                  tabIndex={-1}
                  data-active={index === activeIndex}
                  className="min-h-11 min-w-0 rounded-sm px-3 py-2 text-left font-mono text-sm break-words [overflow-wrap:anywhere] hover:bg-primary/5 data-[active=true]:bg-primary/10 aria-selected:font-semibold"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => chooseBranch(branch.name)}
                >
                  {branch.name}
                </button>
              ))}
            </div>
          ) : !collection.isPartial ? (
            <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
              {t("No live branches match “")}
              {query.trim()}”.
            </p>
          ) : null}
          {collection.loadMoreError ? (
            <Button
              type="button"
              variant="outline"
              className="justify-self-start"
              onClick={() => void loadMoreBranches()}
            >
              {t("Retry search for ")}
              {label}
            </Button>
          ) : null}
        </>
      ) : null}
      {repositorySelected && collection.status === "error" ? (
        <div className="grid gap-2">
          <p className="text-sm text-destructive">
            {t("Live branches are unavailable for this repository.")}
          </p>
          <Button
            type="button"
            variant="outline"
            className="justify-self-start"
            onClick={() => void collection.reload()}
          >
            {t("Retry search for ")}
            {label}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
