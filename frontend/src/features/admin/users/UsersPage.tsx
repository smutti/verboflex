import { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

import {
  createAdminUser,
  deactivateAdminUser,
  listAdminUsers,
  reactivateAdminUser,
  resetAdminUserPassword,
  updateAdminUser,
  type AdminUserCreateRequest,
  type AdminUserCredentialResponse,
  type AdminUserResponse,
  type AdminUserUpdateRequest,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../../components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../../components/ui/alert-dialog";
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
import { UserDialog, type UserDialogResult } from "./UserDialog";
import { TemporaryPasswordDialog } from "./TemporaryPasswordDialog";
import { USER_ROLE_OPTIONS } from "./userRoles";

export interface UsersPageProps {
  accessToken: string;
  currentUserId: string;
}

type LoadState = "loading" | "ready" | "error";
type StatusFilter = "all" | "active" | "inactive";
type LifecycleAction = "reset" | "deactivate" | "reactivate";

interface LifecycleTarget {
  action: LifecycleAction;
  returnFocus: HTMLButtonElement | null;
  user: AdminUserResponse;
}

interface TemporaryCredential {
  displayName: string;
  temporaryPassword: string;
  userId: string;
}

function responseStatus(result: { response?: Response }) {
  return result.response?.status;
}

function isCreateRequest(
  request: AdminUserCreateRequest | AdminUserUpdateRequest,
): request is AdminUserCreateRequest {
  return "email" in request;
}

function ordinaryUserFromCredential(
  response: AdminUserCredentialResponse,
): AdminUserResponse {
  return {
    display_name: response.display_name,
    email: response.email,
    id: response.id,
    is_active: response.is_active,
    must_change_password: response.must_change_password,
    roles: response.roles,
  };
}

function UserRoles({ user }: { user: AdminUserResponse }) {
  return (
    <div
      className="flex flex-wrap gap-2"
      aria-label={`Roles for ${user.display_name}`}
    >
      {user.roles.map((role) => (
        <Badge key={role} variant="outline" className="rounded-md">
          {USER_ROLE_OPTIONS.find((option) => option.value === role)?.label ??
            role}
        </Badge>
      ))}
    </div>
  );
}

function UserStatus({ user }: { user: AdminUserResponse }) {
  return (
    <Badge variant="outline" className="rounded-md">
      {user.is_active ? "Active" : "Inactive"}
    </Badge>
  );
}

const LIFECYCLE_COPY: Record<
  LifecycleAction,
  {
    body: (displayName: string) => string;
    confirmLabel: string;
    title: (displayName: string) => string;
  }
> = {
  reset: {
    title: (displayName) => `Reset password for ${displayName}?`,
    body: () =>
      "Their current password and sessions will stop working. A new temporary password will be shown once.",
    confirmLabel: "Reset password",
  },
  deactivate: {
    title: (displayName) => `Deactivate ${displayName}?`,
    body: () =>
      "They will immediately lose access. You can reactivate them later with a new temporary password.",
    confirmLabel: "Deactivate user",
  },
  reactivate: {
    title: (displayName) => `Reactivate ${displayName}?`,
    body: () =>
      "A new temporary password will be created and all earlier credentials will remain invalid.",
    confirmLabel: "Reactivate user",
  },
};

function UserActions({
  onEdit,
  onLifecycle,
  user,
}: {
  onEdit: (user: AdminUserResponse) => void;
  onLifecycle: (target: LifecycleTarget) => void;
  user: AdminUserResponse;
}) {
  const actionTriggerRef = useRef<HTMLButtonElement>(null);

  return (
    <div className="flex flex-wrap justify-end gap-2">
      <Button
        type="button"
        variant="outline"
        aria-label={`Edit ${user.display_name}`}
        onClick={() => onEdit(user)}
      >
        Edit
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            ref={actionTriggerRef}
            type="button"
            variant="outline"
            aria-label={`More actions for ${user.display_name}`}
          >
            More actions
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {user.is_active ? (
            <>
              <DropdownMenuItem
                onSelect={() =>
                  onLifecycle({
                    action: "reset",
                    returnFocus: actionTriggerRef.current,
                    user,
                  })
                }
              >
                Reset password
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onSelect={() =>
                  onLifecycle({
                    action: "deactivate",
                    returnFocus: actionTriggerRef.current,
                    user,
                  })
                }
              >
                Deactivate user
              </DropdownMenuItem>
            </>
          ) : (
            <DropdownMenuItem
              onSelect={() =>
                onLifecycle({
                  action: "reactivate",
                  returnFocus: actionTriggerRef.current,
                  user,
                })
              }
            >
              Reactivate user
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export function UsersPage({ accessToken, currentUserId }: UsersPageProps) {
  const loadGeneration = useRef(0);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [users, setUsers] = useState<AdminUserResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUserResponse | null>(
    null,
  );
  const [lifecycleTarget, setLifecycleTarget] =
    useState<LifecycleTarget | null>(null);
  const [lifecyclePending, setLifecyclePending] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<
    "conflict" | "generic" | null
  >(null);
  const lifecycleErrorRef = useRef<HTMLDivElement>(null);
  const [temporaryCredential, setTemporaryCredential] =
    useState<TemporaryCredential | null>(null);

  useEffect(() => {
    if (lifecycleError !== null) {
      lifecycleErrorRef.current?.focus();
    }
  }, [lifecycleError]);

  const loadUsers = useCallback(
    async (cursor: string | null, append: boolean) => {
      const generation = ++loadGeneration.current;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoadState("loading");
      }

      try {
        const result = await listAdminUsers({
          auth: accessToken,
          query: { cursor, limit: 50 },
        });
        if (generation !== loadGeneration.current) {
          return;
        }
        if (result.data === undefined) {
          throw new Error("User list rejected");
        }
        setUsers((current) =>
          append ? [...current, ...result.data.items] : result.data.items,
        );
        setNextCursor(result.data.next_cursor);
        setLoadState("ready");
      } catch {
        if (generation === loadGeneration.current) {
          setLoadState("error");
        }
      } finally {
        if (generation === loadGeneration.current) {
          setLoadingMore(false);
        }
      }
    },
    [accessToken],
  );

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadUsers(null, false);
      }
    });
    return () => {
      active = false;
      loadGeneration.current += 1;
    };
  }, [loadUsers]);

  function openCreate() {
    setSelectedUser(null);
    setDialogOpen(true);
  }

  function openEdit(user: AdminUserResponse) {
    setSelectedUser(user);
    setDialogOpen(true);
  }

  function openLifecycle(target: LifecycleTarget) {
    setLifecycleError(null);
    setLifecycleTarget(target);
  }

  function closeLifecycle() {
    if (!lifecyclePending && lifecycleTarget !== null) {
      const returnFocus = lifecycleTarget.returnFocus;
      setLifecycleError(null);
      setLifecycleTarget(null);
      queueMicrotask(() => returnFocus?.focus());
    }
  }

  function replaceUser(user: AdminUserResponse) {
    setUsers((current) =>
      current.map((existing) => (existing.id === user.id ? user : existing)),
    );
  }

  function revealTemporaryCredential(response: AdminUserCredentialResponse) {
    setTemporaryCredential({
      displayName: response.display_name,
      temporaryPassword: response.temporary_password,
      userId: response.id,
    });
  }

  function acknowledgeTemporaryCredential(credential: TemporaryCredential) {
    flushSync(() => {
      setTemporaryCredential({ ...credential, temporaryPassword: "" });
    });
    setTemporaryCredential(null);
  }

  async function submitUser(
    request: AdminUserCreateRequest | AdminUserUpdateRequest,
  ): Promise<UserDialogResult> {
    if (isCreateRequest(request)) {
      const result = await createAdminUser({
        auth: accessToken,
        body: request,
      });
      if (result.data === undefined) {
        return responseStatus(result) === 409
          ? { status: "conflict", owner: "email" }
          : { status: "error" };
      }
      await loadUsers(null, false);
      revealTemporaryCredential(result.data);
      return { status: "success" };
    }

    if (selectedUser === null) {
      return { status: "error" };
    }
    const result = await updateAdminUser({
      auth: accessToken,
      path: { user_id: selectedUser.id },
      body: request,
    });
    if (result.data === undefined) {
      return responseStatus(result) === 409
        ? { status: "conflict", owner: "dialog" }
        : { status: "error" };
    }
    setUsers((current) =>
      current.map((user) => (user.id === result.data.id ? result.data : user)),
    );
    return { status: "success" };
  }

  async function submitLifecycle(target: LifecycleTarget) {
    setLifecyclePending(true);
    setLifecycleError(null);
    const options = {
      auth: accessToken,
      path: { user_id: target.user.id },
    };

    try {
      if (target.action === "deactivate") {
        const result = await deactivateAdminUser(options);
        if (result.data === undefined) {
          setLifecycleError(
            responseStatus(result) === 409 ? "conflict" : "generic",
          );
          return;
        }
        replaceUser(result.data);
        setLifecycleTarget(null);
        queueMicrotask(() => target.returnFocus?.focus());
      } else {
        const result =
          target.action === "reset"
            ? await resetAdminUserPassword(options)
            : await reactivateAdminUser(options);
        if (result.data !== undefined) {
          replaceUser(ordinaryUserFromCredential(result.data));
          revealTemporaryCredential(result.data);
          setLifecycleTarget(null);
        } else {
          setLifecycleError(
            responseStatus(result) === 409 ? "conflict" : "generic",
          );
        }
      }
    } catch {
      setLifecycleError("generic");
    } finally {
      setLifecyclePending(false);
    }
  }

  const visibleUsers = users.filter((user) => {
    if (statusFilter === "active") {
      return user.is_active;
    }
    if (statusFilter === "inactive") {
      return !user.is_active;
    }
    return true;
  });

  return (
    <section className="grid min-w-0 gap-8" aria-labelledby="admin-users-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid min-w-0 gap-2">
          <h1 id="admin-users-title" className="text-display font-semibold">
            Users
          </h1>
          <p className="text-muted-foreground">
            Manage internal users, roles, and account access.
          </p>
        </div>
        <Button
          type="button"
          className="w-full sm:w-auto"
          disabled={loadState !== "ready"}
          onClick={openCreate}
        >
          Add user
        </Button>
      </div>

      {loadState === "loading" ? (
        <div className="grid gap-4" role="status" aria-live="polite">
          <Skeleton className="h-9 w-48 max-w-full" />
          <Skeleton className="h-48 w-full" />
          <span>Loading users</span>
        </div>
      ) : null}

      {loadState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Users unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => void loadUsers(null, false)}
            >
              Retry loading page
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {loadState === "ready" ? (
        <div className="grid min-w-0 gap-6">
          <div className="grid w-full max-w-xs gap-2">
            <label htmlFor="user-status-filter" className="text-sm font-medium">
              User status
            </label>
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter(value as StatusFilter)}
            >
              <SelectTrigger id="user-status-filter" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All users</SelectItem>
                <SelectItem value="active">Active users</SelectItem>
                <SelectItem value="inactive">Inactive users</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {visibleUsers.length === 0 ? (
            <section className="grid gap-2 rounded-lg border bg-secondary p-6">
              <h2 className="text-heading font-semibold">
                No users match these filters
              </h2>
              <p className="text-muted-foreground">
                Clear the filters to see the full user list.
              </p>
            </section>
          ) : (
            <>
              <div className="hidden min-w-0 md:block">
                <Table aria-label="Internal users">
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Roles</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visibleUsers.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="min-w-0 whitespace-normal">
                          <div className="grid gap-1">
                            <span className="font-medium">
                              {user.display_name}
                            </span>
                            <span className="break-words text-muted-foreground [overflow-wrap:anywhere]">
                              {user.email}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="whitespace-normal">
                          <UserRoles user={user} />
                        </TableCell>
                        <TableCell>
                          <UserStatus user={user} />
                        </TableCell>
                        <TableCell className="text-right">
                          <UserActions
                            user={user}
                            onEdit={openEdit}
                            onLifecycle={openLifecycle}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div
                className="grid gap-4 md:hidden"
                aria-label="Internal users mobile list"
              >
                {visibleUsers.map((user) => (
                  <article key={user.id} className="grid gap-4 border-b pb-4">
                    <div className="grid gap-1">
                      <h2 className="font-semibold">{user.display_name}</h2>
                      <p className="break-words text-muted-foreground [overflow-wrap:anywhere]">
                        {user.email}
                      </p>
                    </div>
                    <UserRoles user={user} />
                    <UserStatus user={user} />
                    <UserActions
                      user={user}
                      onEdit={openEdit}
                      onLifecycle={openLifecycle}
                    />
                  </article>
                ))}
              </div>
            </>
          )}

          {nextCursor !== null ? (
            <Button
              type="button"
              variant="outline"
              className="justify-self-start"
              disabled={loadingMore}
              aria-busy={loadingMore}
              onClick={() => void loadUsers(nextCursor, true)}
            >
              Load more users
            </Button>
          ) : null}
        </div>
      ) : null}

      {dialogOpen ? (
        <UserDialog
          key={selectedUser?.id ?? "new-user"}
          open={dialogOpen}
          user={selectedUser}
          currentUserId={currentUserId}
          onOpenChange={setDialogOpen}
          onSubmit={submitUser}
        />
      ) : null}

      {lifecycleTarget !== null ? (
        <AlertDialog open onOpenChange={closeLifecycle}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {LIFECYCLE_COPY[lifecycleTarget.action].title(
                  lifecycleTarget.user.display_name,
                )}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {LIFECYCLE_COPY[lifecycleTarget.action].body(
                  lifecycleTarget.user.display_name,
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>

            {lifecycleError !== null ? (
              <Alert
                ref={lifecycleErrorRef}
                tabIndex={-1}
                variant="destructive"
              >
                <AlertTitle>We could not update this account</AlertTitle>
                <AlertDescription>
                  {lifecycleError === "conflict" &&
                  lifecycleTarget.action === "deactivate"
                    ? "This account cannot be deactivated because administrator authority must be preserved."
                    : lifecycleError === "conflict"
                      ? "This user changed in another session or administrator authority must be preserved."
                      : "The current user state is unchanged. Try again."}
                </AlertDescription>
              </Alert>
            ) : null}

            <AlertDialogFooter>
              <AlertDialogCancel disabled={lifecyclePending}>
                Cancel
              </AlertDialogCancel>
              <Button
                type="button"
                variant={
                  lifecycleTarget.action === "deactivate"
                    ? "destructive"
                    : "default"
                }
                disabled={lifecyclePending}
                aria-busy={lifecyclePending}
                onClick={() => void submitLifecycle(lifecycleTarget)}
              >
                {LIFECYCLE_COPY[lifecycleTarget.action].confirmLabel}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}

      {temporaryCredential !== null ? (
        <TemporaryPasswordDialog
          key={temporaryCredential.userId}
          displayName={temporaryCredential.displayName}
          temporaryPassword={temporaryCredential.temporaryPassword}
          onAcknowledged={() =>
            acknowledgeTemporaryCredential(temporaryCredential)
          }
        />
      ) : null}
    </section>
  );
}
