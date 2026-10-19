import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import {
  getProductTeam,
  addProductMember,
  setProductMember,
  removeProductMember,
  type TeamResponse,
  type TeamMember,
  type MemberInput,
  type AddMemberInput,
  type MemberAdded,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";

import { TemporaryPasswordDialog } from "../admin/users/TemporaryPasswordDialog";

const labels = {
  viewer: "Viewer",
  translator: "Translator",
  product_manager_reviewer: "Reviewer",
  product_owner: "Product Owner",
};
type Role = MemberInput["role"];
const operational: Role[] = [
  "viewer",
  "translator",
  "product_manager_reviewer",
];

function errorMessage(error: unknown): string {
  if (
    error &&
    typeof error === "object" &&
    "detail" in error &&
    typeof error.detail === "string"
  )
    return error.detail;
  return "Unable to update the team. Refresh and try again.";
}

function RoleSelect({
  value,
  onChange,
  owner,
  label,
  disabled,
}: {
  value: Role;
  onChange: (role: Role) => void;
  owner: boolean;
  label: string;
  disabled?: boolean;
}) {
  return (
    <select
      aria-label={label}
      className="min-h-11 max-w-full rounded-md border bg-background px-3"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as Role)}
    >
      {(owner ? [...operational, "product_owner" as const] : operational).map(
        (role) => (
          <option key={role} value={role}>
            {labels[role]}
          </option>
        ),
      )}
    </select>
  );
}

function MemberRow({
  member,
  admin,
  busy,
  save,
  remove,
}: {
  member: TeamMember;
  admin: boolean;
  busy: boolean;
  save: (role: Role) => Promise<boolean>;
  remove: () => void;
}) {
  const [role, setRole] = useState<Role>(member.role);
  const [editing, setEditing] = useState(false);
  const protectedMember = member.role === "product_owner" && !admin;
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-background p-4">
      <div className="min-w-0">
        <p className="font-semibold break-all">{member.display_name}</p>
        <p className="break-all text-sm text-muted-foreground">
          {member.email}
          {!member.account_active && " · Account disabled"}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{labels[member.role]}</Badge>
        {!protectedMember && !editing && (
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => setEditing(true)}
            aria-label={`Edit ${member.email}`}
          >
            Edit
          </Button>
        )}
      </div>
      {!protectedMember && editing && (
        <div className="flex w-full flex-wrap items-center gap-2 border-t pt-3">
          <RoleSelect
            label={`Role for ${member.email}`}
            owner={admin}
            value={role}
            onChange={setRole}
            disabled={busy || !member.account_active}
          />
          <Button
            variant="outline"
            disabled={busy || role === member.role || !member.account_active}
            onClick={async () => {
              if (await save(role)) setEditing(false);
            }}
          >
            Save role
          </Button>
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setRole(member.role);
              setEditing(false);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="ghost"
            className="text-destructive"
            disabled={busy}
            onClick={remove}
            aria-label={`Remove ${member.email} from product`}
          >
            Remove
          </Button>
        </div>
      )}
    </li>
  );
}

export function ProductTeamPage({ accessToken }: { accessToken: string }) {
  const productId = useParams<"productId">().productId ?? "";
  return (
    <TeamEditor
      key={`${productId}:${accessToken}`}
      productId={productId}
      accessToken={accessToken}
    />
  );
}

function TeamEditor({
  productId,
  accessToken,
}: {
  productId: string;
  accessToken: string;
}) {
  const [team, setTeam] = useState<TeamResponse | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [credential, setCredential] = useState<MemberAdded | null>(null);
  const [role, setRole] = useState<AddMemberInput["role"]>("translator");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [addingOwner, setAddingOwner] = useState(false);
  const [addingCollaborator, setAddingCollaborator] = useState(false);
  const [removal, setRemoval] = useState<TeamMember | null>(null);
  const auth = { auth: accessToken, path: { product_id: productId } };
  useEffect(() => {
    const controller = new AbortController();
    getProductTeam({
      auth: accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.data) {
          setTeam(result.data);
          setError("");
        } else {
          setTeam(null);
          setError(errorMessage(result.error));
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setTeam(null);
          setError("Unable to load the product team.");
        }
      });
    return () => controller.abort();
  }, [productId, accessToken, revision]);
  async function mutate(
    operation: () => Promise<{ error?: unknown; response?: Response }>,
    success: string,
  ) {
    if (busy) return false;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await operation();
      if (!result.response?.ok) {
        setError(errorMessage(result.error));
        return false;
      }
      setNotice(success);
      setRemoval(null);
      setRevision((value) => value + 1);
      return true;
    } catch {
      setError("Unable to update the team. Your changes were not confirmed.");
      return false;
    } finally {
      setBusy(false);
    }
  }
  const admin = team?.access.role === "admin";
  const owners =
    team?.members.filter((member) => member.role === "product_owner") ?? [];
  const collaborators =
    team?.members.filter((member) => member.role !== "product_owner") ?? [];
  function memberRow(member: TeamMember) {
    return (
      <MemberRow
        key={`${member.user_id}:${member.version}`}
        member={member}
        admin={admin}
        busy={busy}
        save={(nextRole) =>
          mutate(
            () =>
              setProductMember({
                ...auth,
                body: {
                  email: member.email,
                  role: nextRole,
                  expected_version: member.version,
                },
              }),
            "Role updated.",
          )
        }
        remove={() => setRemoval(member)}
      />
    );
  }
  async function submitCollaborator(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await addProductMember({
        ...auth,
        body: { email, display_name: displayName, role },
      });
      if (!result.response?.ok || !result.data) {
        setError(errorMessage(result.error));
        return;
      }
      if (result.data.temporary_password) setCredential(result.data);
      setNotice(
        result.data.account_created
          ? "Collaborator added. Share their temporary password privately."
          : "Existing account added. They can sign in with their current credentials.",
      );
      setEmail("");
      setDisplayName("");
      setAddingCollaborator(false);
      setRevision((value) => value + 1);
    } catch {
      setError(
        "Account creation was not confirmed. Refresh the team before retrying. If the account was created but its password was lost, ask an administrator to reset it.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="grid min-w-0 gap-6" aria-labelledby="team-title">
      <h1 id="team-title" className="text-heading font-semibold">
        Product team
      </h1>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Team update unavailable</AlertTitle>
          <AlertDescription>
            {error}{" "}
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setRevision((r) => r + 1)}
            >
              Refresh team
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {notice && <p role="status">{notice}</p>}
      {!team && !error && <p role="status">Loading team…</p>}
      {team && (
        <>
          <section
            aria-labelledby="owners-title"
            className="grid gap-4 rounded-lg border bg-card p-4 sm:p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="owners-title" className="font-semibold">
                Product Owner
              </h2>
              {admin && (
                <Button
                  variant="outline"
                  disabled={busy}
                  aria-expanded={addingOwner}
                  aria-controls="owner-form"
                  onClick={() => setAddingOwner((value) => !value)}
                >
                  Assign Product Owner
                </Button>
              )}
            </div>
            {owners.length > 0 && (
              <ul className="grid gap-3">{owners.map(memberRow)}</ul>
            )}
            {!team.has_active_owner && (
              <p className="text-sm text-muted-foreground">
                No active Product Owner
              </p>
            )}
            {admin && addingOwner && (
              <form
                id="owner-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  const saved = await mutate(
                    () =>
                      setProductMember({
                        ...auth,
                        body: { email: ownerEmail, role: "product_owner" },
                      }),
                    "Product Owner appointed.",
                  );
                  if (saved) {
                    setOwnerEmail("");
                    setAddingOwner(false);
                  }
                }}
                className="grid gap-3 border-t pt-4"
              >
                <Label htmlFor="owner-email">Account email</Label>
                <p
                  id="owner-email-help"
                  className="text-sm text-muted-foreground"
                >
                  Use an existing account. To promote a collaborator, edit their
                  role below.
                </p>
                <Input
                  id="owner-email"
                  type="email"
                  required
                  maxLength={320}
                  value={ownerEmail}
                  onChange={(event) => setOwnerEmail(event.target.value)}
                  placeholder="name@example.com"
                  aria-describedby="owner-email-help"
                  disabled={busy}
                  className="max-w-md"
                />
                <div className="flex flex-wrap gap-2">
                  <Button disabled={busy}>Appoint owner</Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => setAddingOwner(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </section>
          <section
            aria-labelledby="collaborators-title"
            className="grid gap-4 rounded-lg border bg-card p-4 sm:p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="collaborators-title" className="font-semibold">
                Collaborators
              </h2>
              <Button
                variant="outline"
                disabled={busy}
                aria-expanded={addingCollaborator}
                aria-controls="collaborator-form"
                onClick={() => setAddingCollaborator((value) => !value)}
              >
                Add collaborator
              </Button>
            </div>
            {collaborators.length > 0 ? (
              <ul className="grid gap-3">{collaborators.map(memberRow)}</ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No collaborators yet.
              </p>
            )}
            {addingCollaborator && (
              <form
                id="collaborator-form"
                onSubmit={(event) => void submitCollaborator(event)}
                className="grid gap-3 border-t pt-4"
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="collaborator-email">
                      Collaborator email
                    </Label>
                    <Input
                      id="collaborator-email"
                      type="email"
                      required
                      maxLength={320}
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="name@example.com"
                      disabled={busy}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="collaborator-name">Display name</Label>
                    <Input
                      id="collaborator-name"
                      required
                      maxLength={200}
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                      disabled={busy}
                    />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <RoleSelect
                    label="Collaborator role"
                    owner={false}
                    value={role}
                    onChange={(value) =>
                      setRole(value as AddMemberInput["role"])
                    }
                    disabled={busy}
                  />
                  <Button disabled={busy}>Add to team</Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => setAddingCollaborator(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </section>
          {removal && (
            <Alert>
              <AlertTitle>
                Remove {removal.display_name} from this product?
              </AlertTitle>
              <AlertDescription>
                <p>
                  Their account and access to other products will remain
                  available.
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="destructive"
                    disabled={busy}
                    onClick={() =>
                      void mutate(
                        () =>
                          removeProductMember({
                            ...auth,
                            path: { ...auth.path, user_id: removal.user_id },
                            query: { expected_version: removal.version },
                          }),
                        "Product access removed.",
                      )
                    }
                  >
                    Confirm removal
                  </Button>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => setRemoval(null)}
                  >
                    Cancel
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}
        </>
      )}
      {credential?.temporary_password && (
        <TemporaryPasswordDialog
          displayName={credential.email}
          temporaryPassword={credential.temporary_password}
          onAcknowledged={() => setCredential(null)}
        />
      )}
    </section>
  );
}
