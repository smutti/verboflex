import { useCallback, useId, useRef, useState, type FormEvent } from "react";

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
import { useCursorCollection } from "../useCursorCollection";
import { MappedProductRepositories } from "./MappedProductRepositories";

export interface ProductRepositoriesPageProps {
  accessToken: string;
  embedded?: boolean;
  onRepositorySelected?: (repository: AdminRepositoryResponse) => void;
  productId?: string;
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
  productId,
  selectedRepositoryIds = [],
}: ProductRepositoriesPageProps) {
  if (productId !== undefined) {
    return (
      <MappedProductRepositories
        accessToken={accessToken}
        productId={productId}
      />
    );
  }
  return (
    <RepositoryCatalogue
      accessToken={accessToken}
      embedded={embedded}
      onRepositorySelected={onRepositorySelected}
      selectedRepositoryIds={selectedRepositoryIds}
    />
  );
}

function RepositoryCatalogue({
  accessToken,
  embedded = false,
  onRepositorySelected,
  selectedRepositoryIds = [],
}: Omit<ProductRepositoriesPageProps, "productId">) {
  const workspaceId = useId();
  const slugId = useId();
  const descriptiveNameId = useId();
  const workspaceRef = useRef<HTMLInputElement>(null);
  const registerPendingRef = useRef(false);
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

  const loadRepositoryPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      const result = await listAdminRepositories({
        auth: accessToken,
        query: { cursor, limit: 50 },
        signal,
      });
      if (result.data === undefined) {
        throw new Error("Repository page rejected");
      }
      return result.data;
    },
    [accessToken],
  );
  const repositoryCollection = useCursorCollection({
    getItemId: (repository: AdminRepositoryResponse) => repository.id,
    loadPage: loadRepositoryPage,
    queryKey: JSON.stringify(["repositories", accessToken]),
  });
  const repositories = repositoryCollection.items;

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
      repositoryCollection.appendItems([registered]);
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
          Repository catalogue
        </Heading>
        <p className="text-muted-foreground">
          Choose a reusable Bitbucket repository or register its provider
          identity. Credentials remain in the organization-wide connection.
        </p>
      </div>

      {embedded ? (
        <aside
          role="note"
          className="border-primary/25 bg-primary/5 grid gap-1 rounded-xl border p-5"
        >
          <strong>Repository selection prepares the mapping</strong>
          <p className="text-sm text-muted-foreground">
            The product association is saved only when you save a mapping in the
            next step.
          </p>
        </aside>
      ) : null}

      {repositoryCollection.status === "loading" ? (
        <section className="grid gap-3" role="status" aria-live="polite">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <span>Loading repositories</span>
        </section>
      ) : null}

      {repositoryCollection.status === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Repositories unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => void repositoryCollection.reload()}
            >
              Retry loading page
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {repositoryCollection.isEmpty ? (
        <section className="grid gap-2 rounded-lg border bg-secondary p-6">
          <h3 className="text-heading font-semibold">No repositories added</h3>
          <p className="text-muted-foreground">
            Add or reuse a Bitbucket repository before configuring a mapping.
          </p>
        </section>
      ) : null}

      {repositoryCollection.status === "ready" && repositories.length > 0 ? (
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

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {repositoryCollection.isPartial
                ? `${repositories.length} repositories loaded — more available`
                : `All ${repositories.length} ${repositories.length === 1 ? "repository" : "repositories"} loaded`}
            </p>
            {repositoryCollection.isPartial ? (
              <Button
                type="button"
                variant="outline"
                disabled={repositoryCollection.loadingMore}
                aria-busy={repositoryCollection.loadingMore}
                aria-label="Load more repositories"
                onClick={() => void repositoryCollection.loadMore()}
              >
                {repositoryCollection.loadingMore
                  ? "Loading more repositories"
                  : "Load more"}
              </Button>
            ) : null}
          </div>
          {repositoryCollection.loadMoreError ? (
            <Alert variant="destructive" className="mt-4">
              <AlertTitle>More repositories unavailable</AlertTitle>
              <AlertDescription>
                <p>
                  The loaded repositories remain available. Retry this page.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void repositoryCollection.loadMore()}
                >
                  Retry loading repositories
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}
        </section>
      ) : null}

      <p className="sr-only" aria-live="polite">
        {selectedIdentity}
      </p>

      <form
        className="grid gap-6 rounded-lg border bg-secondary p-6"
        aria-label="Register a Bitbucket repository"
        noValidate
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
              aria-describedby={
                workspaceError ? `${workspaceId}-error` : undefined
              }
              required
              onChange={(event) => {
                setWorkspace(event.target.value);
                setWorkspaceError(false);
                setRegisterError(false);
              }}
            />
            {workspaceError ? (
              <p
                id={`${workspaceId}-error`}
                className="text-sm text-destructive"
              >
                Enter the Bitbucket workspace.
              </p>
            ) : null}
          </div>
          <div className="grid gap-2">
            <Label htmlFor={slugId}>Repository slug</Label>
            <Input
              id={slugId}
              value={repositorySlug}
              aria-invalid={slugError}
              aria-describedby={slugError ? `${slugId}-error` : undefined}
              required
              onChange={(event) => {
                setRepositorySlug(event.target.value);
                setSlugError(false);
                setRegisterError(false);
              }}
            />
            {slugError ? (
              <p id={`${slugId}-error`} className="text-sm text-destructive">
                Enter the repository slug.
              </p>
            ) : null}
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
          {registerPending ? "Registering repository" : "Register repository"}
        </Button>
      </form>
    </section>
  );
}
