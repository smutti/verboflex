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
      className="min-h-11 rounded-md border bg-background px-3"
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
  save: (role: Role) => void;
  remove: () => void;
}) {
  const [role, setRole] = useState<Role>(member.role);
  const protectedMember = member.role === "product_owner" && !admin;
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div className="min-w-0">
        <p className="font-semibold break-all">{member.display_name}</p>
        <p className="break-all text-sm text-muted-foreground">
          {member.email}
          {!member.account_active && " · Account disabled"}
        </p>
      </div>
      {protectedMember ? (
        <span>Product Owner · Managed by admin</span>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
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
            onClick={() => save(role)}
          >
            Save role
          </Button>
          <Button
            variant="outline"
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
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await operation();
      if (!result.response?.ok) {
        setError(errorMessage(result.error));
        return;
      }
      setNotice(success);
      setRemoval(null);
      setRevision((value) => value + 1);
    } catch {
      setError("Unable to update the team. Your changes were not confirmed.");
    } finally {
      setBusy(false);
    }
  }
  const admin = team?.access.role === "admin";
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
    <section className="grid max-w-5xl gap-6" aria-labelledby="team-title">
      <div>
        <h1 id="team-title" className="text-heading font-semibold">
          Product team
        </h1>
        <p className="text-muted-foreground">
          Manage access to this product. Only an administrator can appoint or
          remove Product Owners.
        </p>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Team unavailable</AlertTitle>
          <AlertDescription>
            {error}{" "}
            <Button variant="outline" onClick={() => setRevision((r) => r + 1)}>
              Refresh team
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {notice && <p role="status">{notice}</p>}
      {!team && !error && <p role="status">Loading team…</p>}
      {team && (
        <>
          {!team.has_active_owner && (
            <Alert>
              <AlertTitle>No active Product Owner</AlertTitle>
              <AlertDescription>
                An administrator can appoint an existing account below.
              </AlertDescription>
            </Alert>
          )}
          {admin && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void mutate(
                  () =>
                    setProductMember({
                      ...auth,
                      body: { email: ownerEmail, role: "product_owner" },
                    }),
                  "Product Owner appointed.",
                );
              }}
              className="grid gap-3 rounded-lg border p-4"
            >
              <Label htmlFor="owner-email">Appoint a Product Owner</Label>
              <p className="text-sm text-muted-foreground">
                Enter an existing account email. To promote a current team
                member, change their role in the list.
              </p>
              <div className="flex flex-wrap gap-2">
                <Input
                  id="owner-email"
                  type="email"
                  required
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="max-w-sm"
                />
                <Button disabled={busy}>Appoint owner</Button>
              </div>
            </form>
          )}
          <form
            onSubmit={(event) => void submitCollaborator(event)}
            className="grid gap-3 rounded-lg border p-4"
          >
            <h2 className="font-semibold">Add a collaborator</h2>
            <p className="text-sm text-muted-foreground">
              New accounts receive a temporary password to share privately and
              must change it at first sign-in. Existing accounts keep their
              current name and credentials.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="collaborator-email">Collaborator email</Label>
                <Input
                  id="collaborator-email"
                  type="email"
                  required
                  maxLength={320}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                  onChange={(e) => setDisplayName(e.target.value)}
                  disabled={busy}
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <RoleSelect
                label="Collaborator role"
                owner={false}
                value={role}
                onChange={(value) => setRole(value as AddMemberInput["role"])}
                disabled={busy}
              />
              <Button disabled={busy}>Add collaborator</Button>
            </div>
          </form>
          <div>
            <h2 className="mb-3 font-semibold">Members</h2>
            <ul className="grid gap-3">
              {team.members.map((member) => (
                <MemberRow
                  key={`${member.user_id}:${member.version}`}
                  member={member}
                  admin={admin}
                  busy={busy}
                  save={(nextRole) =>
                    void mutate(
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
              ))}
            </ul>
          </div>
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
