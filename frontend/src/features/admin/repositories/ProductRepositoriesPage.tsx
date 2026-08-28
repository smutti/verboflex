import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import {
  createAdminRepository,
  listAdminRepositories,
  type AdminRepositoryResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Skeleton } from "../../../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";

type CollectionState = "error" | "loading" | "ready";

export interface ProductRepositoriesPageProps {
  accessToken: string;
  embedded?: boolean;
  onRepositorySelected?: (repository: AdminRepositoryResponse) => void;
  selectedRepositoryIds?: readonly string[];
}

function repositoryLabel(repository: AdminRepositoryResponse) {
  return (
    repository.descriptive_name ??
    `${repository.workspace}/${repository.repository_slug}`
  );
}

function RepositoryIdentity({
  repository,
}: {
  repository: AdminRepositoryResponse;
}) {
  return (
    <span className="break-words [overflow-wrap:anywhere]">
      <span>{repository.workspace}</span>
      <span aria-hidden="true">/</span>
      <span>{repository.repository_slug}</span>
    </span>
  );
}

export function ProductRepositoriesPage({
  accessToken,
  embedded = false,
  onRepositorySelected,
  selectedRepositoryIds = [],
}: ProductRepositoriesPageProps) {
  const workspaceId = useId();
  const slugId = useId();
  const descriptiveNameId = useId();
  const workspaceRef = useRef<HTMLInputElement>(null);
  const registerPendingRef = useRef(false);
  const loadGenerationRef = useRef(0);
  const [collectionState, setCollectionState] =
    useState<CollectionState>("loading");
  const [repositories, setRepositories] = useState<AdminRepositoryResponse[]>(
    [],
  );
  const [selectedIds, setSelectedIds] = useState(
    () => new Set(selectedRepositoryIds),
  );
  const [workspace, setWorkspace] = useState("");
  const [repositorySlug, setRepositorySlug] = useState("");
  const [descriptiveName, setDescriptiveName] = useState("");
  const [workspaceError, setWorkspaceError] = useState(false);
  const [slugError, setSlugError] = useState(false);
  const [registerPending, setRegisterPending] = useState(false);
  const [registerError, setRegisterError] = useState(false);
  const [selectedIdentity, setSelectedIdentity] = useState<string | null>(null);

  function loadRepositories() {
    const generation = ++loadGenerationRef.current;

    queueMicrotask(async () => {
      if (loadGenerationRef.current !== generation) {
        return;
      }
      setCollectionState("loading");
      try {
        const result = await listAdminRepositories({
          auth: accessToken,
          query: { cursor: null, limit: 50 },
        });
        if (loadGenerationRef.current !== generation) {
          return;
        }
        if (result.data === undefined) {
          setCollectionState("error");
          return;
        }
        setRepositories(result.data.items);
        setCollectionState("ready");
      } catch {
        if (loadGenerationRef.current === generation) {
          setCollectionState("error");
        }
      }
    });
  }

  useEffect(() => {
    loadRepositories();
    return () => {
      loadGenerationRef.current += 1;
    };
    // loadRepositories is deliberately generation-bound to the current token.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  function selectRepository(repository: AdminRepositoryResponse) {
    setSelectedIds((current) => new Set(current).add(repository.id));
    setSelectedIdentity(
      `${repository.workspace}/${repository.repository_slug}`,
    );
    onRepositorySelected?.(repository);
  }

  async function registerRepository(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (registerPendingRef.current) {
      return;
    }

    const missingWorkspace = workspace.trim().length === 0;
    const missingSlug = repositorySlug.trim().length === 0;
    setWorkspaceError(missingWorkspace);
    setSlugError(missingSlug);
    setRegisterError(false);
    if (missingWorkspace || missingSlug) {
      (missingWorkspace ? workspaceRef.current : null)?.focus();
      return;
    }

    registerPendingRef.current = true;
    setRegisterPending(true);
    try {
      const result = await createAdminRepository({
        auth: accessToken,
        body: {
          workspace,
          repository_slug: repositorySlug,
          descriptive_name:
            descriptiveName.trim().length === 0 ? null : descriptiveName,
        },
      });
      if (result.data === undefined) {
        setRegisterError(true);
        return;
      }

      const registered = result.data;
      setRepositories((current) => [...current, registered]);
      selectRepository(registered);
      setWorkspace("");
      setRepositorySlug("");
      setDescriptiveName("");
    } catch {
      setRegisterError(true);
    } finally {
      registerPendingRef.current = false;
      setRegisterPending(false);
    }
  }

  const Heading = embedded ? "h2" : "h1";

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
          Repositories
        </Heading>
        <p className="text-muted-foreground">
          Reuse a registered Bitbucket repository or register its provider
          identity without storing credentials here.
        </p>
      </div>

      {collectionState === "loading" ? (
        <section className="grid gap-3" role="status" aria-live="polite">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <span>Loading repositories</span>
        </section>
      ) : null}

      {collectionState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Repositories unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button type="button" variant="outline" onClick={loadRepositories}>
              Retry loading page
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {collectionState === "ready" && repositories.length === 0 ? (
        <section className="grid gap-2 rounded-lg border bg-secondary p-6">
          <h3 className="text-heading font-semibold">No repositories added</h3>
          <p className="text-muted-foreground">
            Add or reuse a Bitbucket repository before configuring a mapping.
          </p>
        </section>
      ) : null}

      {collectionState === "ready" && repositories.length > 0 ? (
        <section
          className="min-w-0 max-w-full overflow-x-clip"
          aria-label="Reusable repositories"
        >
          <div className="hidden md:block">
            <Table aria-label="Repositories">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Workspace / repository</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {repositories.map((repository) => {
                  const label = repositoryLabel(repository);
                  const selected = selectedIds.has(repository.id);
                  return (
                    <TableRow key={repository.id}>
                      <TableCell className="whitespace-normal break-words [overflow-wrap:anywhere]">
                        {repository.descriptive_name ?? "No descriptive name"}
                      </TableCell>
                      <TableCell className="whitespace-normal">
                        <RepositoryIdentity repository={repository} />
                      </TableCell>
                      <TableCell>
                        <Button
                          type="button"
                          variant="outline"
                          disabled={selected}
                          aria-label={
                            selected ? `${label} selected` : `Use ${label}`
                          }
                          onClick={() => selectRepository(repository)}
                        >
                          {selected ? "Selected" : "Use repository"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <div
            className="grid min-w-0 max-w-full divide-y md:hidden"
            aria-label="Repositories mobile list"
          >
            {repositories.map((repository) => {
              const label = repositoryLabel(repository);
              const selected = selectedIds.has(repository.id);
              return (
                <article
                  key={repository.id}
                  className="grid min-w-0 gap-3 py-4"
                >
                  <strong className="break-words [overflow-wrap:anywhere]">
                    {repository.descriptive_name ?? "No descriptive name"}
                  </strong>
                  <RepositoryIdentity repository={repository} />
                  <Button
                    type="button"
                    variant="outline"
                    disabled={selected}
                    aria-label={selected ? `${label} selected` : `Use ${label}`}
                    onClick={() => selectRepository(repository)}
                  >
                    {selected ? "Selected" : "Use repository"}
                  </Button>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      <p className="sr-only" aria-live="polite">
        {selectedIdentity}
      </p>

      <form
        className="grid gap-6 rounded-lg border bg-secondary p-6"
        onSubmit={(event) => void registerRepository(event)}
      >
        <div className="grid gap-2">
          <h3 className="text-heading font-semibold">Register repository</h3>
          <p className="text-muted-foreground">
            Enter the exact Bitbucket provider identity. Connection credentials
            remain organization-wide settings.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor={workspaceId}>Workspace</Label>
            <Input
              ref={workspaceRef}
              id={workspaceId}
              value={workspace}
              aria-invalid={workspaceError}
              onChange={(event) => {
                setWorkspace(event.target.value);
                setWorkspaceError(false);
                setRegisterError(false);
              }}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor={slugId}>Repository slug</Label>
            <Input
              id={slugId}
              value={repositorySlug}
              aria-invalid={slugError}
              onChange={(event) => {
                setRepositorySlug(event.target.value);
                setSlugError(false);
                setRegisterError(false);
              }}
            />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor={descriptiveNameId}>Descriptive name</Label>
          <Input
            id={descriptiveNameId}
            value={descriptiveName}
            onChange={(event) => {
              setDescriptiveName(event.target.value);
              setRegisterError(false);
            }}
          />
          <p className="text-sm text-muted-foreground">Optional</p>
        </div>
        {registerError ? (
          <Alert variant="destructive">
            <AlertTitle>Repository not registered</AlertTitle>
            <AlertDescription>
              We could not register this repository. Your entries are still
              here. Review the provider identity and try again.
            </AlertDescription>
          </Alert>
        ) : null}
        <Button
          type="submit"
          className="justify-self-start"
          disabled={registerPending}
          aria-busy={registerPending}
        >
          Register repository
        </Button>
      </form>
    </section>
  );
}
