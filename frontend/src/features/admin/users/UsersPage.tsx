import { useCallback, useEffect, useRef, useState } from "react";

import {
  createAdminUser,
  listAdminUsers,
  updateAdminUser,
  type AdminUserCreateRequest,
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
import { USER_ROLE_OPTIONS } from "./userRoles";

export interface UsersPageProps {
  accessToken: string;
  currentUserId: string;
}

type LoadState = "loading" | "ready" | "error";
type StatusFilter = "all" | "active" | "inactive";

function responseStatus(result: { response?: Response }) {
  return result.response?.status;
}

function isCreateRequest(
  request: AdminUserCreateRequest | AdminUserUpdateRequest,
): request is AdminUserCreateRequest {
  return "email" in request;
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
                          <Button
                            type="button"
                            variant="outline"
                            aria-label={`Edit ${user.display_name}`}
                            onClick={() => openEdit(user)}
                          >
                            Edit
                          </Button>
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
                    <Button
                      type="button"
                      variant="outline"
                      aria-label={`Edit ${user.display_name}`}
                      onClick={() => openEdit(user)}
                    >
                      Edit user
                    </Button>
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
    </section>
  );
}
