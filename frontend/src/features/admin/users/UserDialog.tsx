import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import type {
  AdminUserCreateRequest,
  AdminUserResponse,
  AdminUserUpdateRequest,
  RoleName,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Button } from "../../../components/ui/button";
import { Checkbox } from "../../../components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../../components/ui/dialog";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { CREATE_DEFAULT_ROLES, USER_ROLE_OPTIONS } from "./userRoles";

export type UserDialogResult =
  | { status: "success" }
  | { status: "conflict"; owner: "email" | "dialog" }
  | { status: "error" };

export interface UserDialogProps {
  currentUserId: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    request: AdminUserCreateRequest | AdminUserUpdateRequest,
  ) => Promise<UserDialogResult>;
  open: boolean;
  user: AdminUserResponse | null;
}

export function UserDialog({
  currentUserId,
  onOpenChange,
  onSubmit,
  open,
  user,
}: UserDialogProps) {
  const emailId = useId();
  const displayNameId = useId();
  const roleGroupId = useId();
  const roleErrorId = useId();
  const conflictId = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const displayNameRef = useRef<HTMLInputElement>(null);
  const roleGroupRef = useRef<HTMLFieldSetElement>(null);
  const conflictRef = useRef<HTMLDivElement>(null);
  const [email, setEmail] = useState(user?.email ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [roles, setRoles] = useState<RoleName[]>(
    user?.roles ?? CREATE_DEFAULT_ROLES,
  );
  const [pending, setPending] = useState(false);
  const [roleError, setRoleError] = useState(false);
  const [emailConflict, setEmailConflict] = useState(false);
  const [fieldError, setFieldError] = useState<"email" | "display_name" | null>(
    null,
  );
  const [submissionError, setSubmissionError] = useState<
    "conflict" | "generic" | null
  >(null);

  const isEditing = user !== null;
  const isEditingSelf = user?.id === currentUserId;

  useEffect(() => {
    if (submissionError === "conflict") {
      conflictRef.current?.focus();
    }
  }, [submissionError]);

  useEffect(() => {
    if (roleError) {
      roleGroupRef.current?.focus();
    }
  }, [roleError]);

  function toggleRole(role: RoleName, checked: boolean) {
    setRoleError(false);
    setRoles((current) => {
      if (checked) {
        return USER_ROLE_OPTIONS.filter(
          (option) => current.includes(option.value) || option.value === role,
        ).map((option) => option.value);
      }
      return current.filter((currentRole) => currentRole !== role);
    });
  }

  function validate() {
    if (!isEditing && email.trim().length === 0) {
      setFieldError("email");
      emailRef.current?.focus();
      return false;
    }
    if (displayName.trim().length === 0) {
      setFieldError("display_name");
      displayNameRef.current?.focus();
      return false;
    }
    if (roles.length === 0) {
      setRoleError(true);
      return false;
    }
    setFieldError(null);
    setRoleError(false);
    return true;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !validate()) {
      return;
    }
    setPending(true);
    setEmailConflict(false);
    setSubmissionError(null);
    const request = isEditing
      ? ({ display_name: displayName, roles } satisfies AdminUserUpdateRequest)
      : ({
          email,
          display_name: displayName,
          roles,
        } satisfies AdminUserCreateRequest);

    let result: UserDialogResult;
    try {
      result = await onSubmit(request);
    } catch {
      result = { status: "error" };
    }

    if (result.status === "success") {
      setPending(false);
      onOpenChange(false);
      return;
    }
    setPending(false);
    if (result.status === "conflict") {
      if (result.owner === "email") {
        setEmailConflict(true);
        setFieldError("email");
        emailRef.current?.focus();
      } else {
        setSubmissionError("conflict");
      }
      return;
    }
    setSubmissionError("generic");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        onEscapeKeyDown={(event) => pending && event.preventDefault()}
        onPointerDownOutside={(event) => pending && event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>
            {isEditing ? `Edit ${user.display_name}` : "Add user"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the display name and additive roles for this account."
              : "Create an internal account with a fixed set of additive roles."}
          </DialogDescription>
        </DialogHeader>

        <form className="grid gap-5" onSubmit={(event) => void submit(event)}>
          {submissionError !== null ? (
            <Alert
              ref={conflictRef}
              tabIndex={-1}
              variant="destructive"
              aria-describedby={conflictId}
            >
              <AlertTitle>We could not save this user</AlertTitle>
              <AlertDescription id={conflictId}>
                {submissionError === "conflict"
                  ? "This user changed in another session or the administrator role must be preserved."
                  : "Your entries are still here. Review them and try again."}
              </AlertDescription>
            </Alert>
          ) : null}

          {isEditing ? (
            <div className="grid gap-2">
              <span className="text-sm font-medium">Corporate email</span>
              <p className="break-words text-sm [overflow-wrap:anywhere]">
                {user.email}
              </p>
              <p className="text-sm text-muted-foreground">
                Email cannot be changed. Create a new account to correct it.
              </p>
            </div>
          ) : (
            <div className="grid gap-2">
              <Label htmlFor={emailId}>Corporate email</Label>
              <Input
                ref={emailRef}
                id={emailId}
                type="email"
                autoComplete="off"
                value={email}
                aria-invalid={fieldError === "email"}
                aria-describedby={
                  fieldError === "email" ? `${emailId}-error` : undefined
                }
                onChange={(event) => {
                  setEmail(event.target.value);
                  setEmailConflict(false);
                  setFieldError(null);
                }}
              />
              {fieldError === "email" ? (
                <p
                  id={`${emailId}-error`}
                  role={emailConflict ? "alert" : undefined}
                  className="text-sm text-destructive"
                >
                  {emailConflict
                    ? "An account already uses this corporate email."
                    : "Enter a corporate email."}
                </p>
              ) : null}
            </div>
          )}

          <div className="grid gap-2">
            <Label htmlFor={displayNameId}>Display name</Label>
            <Input
              ref={displayNameRef}
              id={displayNameId}
              value={displayName}
              aria-invalid={fieldError === "display_name"}
              aria-describedby={
                fieldError === "display_name"
                  ? `${displayNameId}-error`
                  : undefined
              }
              onChange={(event) => {
                setDisplayName(event.target.value);
                setFieldError(null);
              }}
            />
            {fieldError === "display_name" ? (
              <p
                id={`${displayNameId}-error`}
                className="text-sm text-destructive"
              >
                Enter a display name.
              </p>
            ) : null}
          </div>

          <fieldset
            ref={roleGroupRef}
            role="group"
            tabIndex={roleError ? -1 : undefined}
            aria-labelledby={roleGroupId}
            aria-describedby={roleError ? roleErrorId : undefined}
            className="grid gap-3 rounded-lg border p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <legend id={roleGroupId} className="px-1 text-sm font-medium">
              Roles
            </legend>
            {USER_ROLE_OPTIONS.map((option) => {
              const checkboxId = `${roleGroupId}-${option.value}`;
              const protectsSelfAdmin =
                isEditingSelf && option.value === "admin";
              return (
                <div key={option.value} className="grid gap-1">
                  <div className="flex items-center gap-3">
                    <Checkbox
                      id={checkboxId}
                      checked={roles.includes(option.value)}
                      disabled={protectsSelfAdmin}
                      onCheckedChange={(checked) =>
                        toggleRole(option.value, checked === true)
                      }
                    />
                    <Label htmlFor={checkboxId}>{option.label}</Label>
                  </div>
                  {protectsSelfAdmin ? (
                    <p className="pl-7 text-sm text-muted-foreground">
                      You cannot remove your own administrator role.
                    </p>
                  ) : null}
                </div>
              );
            })}
            {roleError ? (
              <p id={roleErrorId} className="text-sm text-destructive">
                Select at least one role.
              </p>
            ) : null}
          </fieldset>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={pending} aria-busy={pending}>
              {isEditing ? "Save user" : "Create user"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
