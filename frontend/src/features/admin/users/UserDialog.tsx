import { t, useUiLanguage } from "@/i18n";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import type {
  AdminUserCreateRequest,
  AdminUserResponse,
  AdminUserUpdateRequest,
  AdminUserProductChange,
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
import { UserProductAssignments } from "./UserProductAssignments";

export type UserDialogResult =
  | { status: "success" }
  | { status: "conflict"; owner: "email" | "dialog" }
  | { status: "products-unavailable" }
  | { status: "products-conflict" }
  | { status: "error" };

export interface UserDialogProps {
  accessToken: string;
  currentUserId: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    request: AdminUserCreateRequest | AdminUserUpdateRequest,
  ) => Promise<UserDialogResult>;
  open: boolean;
  user: AdminUserResponse | null;
}

export function UserDialog({
  accessToken,
  currentUserId,
  onOpenChange,
  onSubmit,
  open,
  user,
}: UserDialogProps) {
  useUiLanguage();
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
  const [productAssignments, setProductAssignments] = useState<
    AdminUserProductChange[]
  >([]);
  const [roleError, setRoleError] = useState(false);
  const [emailConflict, setEmailConflict] = useState(false);
  const [fieldError, setFieldError] = useState<"email" | "display_name" | null>(
    null,
  );
  const [submissionError, setSubmissionError] = useState<
    "conflict" | "generic" | "products" | "products-conflict" | null
  >(null);

  const isEditing = user !== null;
  const isEditingSelf = user?.id === currentUserId;

  useEffect(() => {
    if (submissionError !== null) {
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
      ? ({
          display_name: displayName,
          roles,
          ...(productAssignments.length > 0
            ? { product_assignments: productAssignments }
            : {}),
        } satisfies AdminUserUpdateRequest)
      : ({
          email,
          display_name: displayName,
          roles,
          ...(productAssignments.length > 0
            ? {
                product_assignments: productAssignments.flatMap(
                  ({ product_id, role }) =>
                    role === null ? [] : [{ product_id, role }],
                ),
              }
            : {}),
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
    setSubmissionError(
      result.status === "products-unavailable"
        ? "products"
        : result.status === "products-conflict"
          ? "products-conflict"
          : "generic",
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto">
        <DialogHeader className="min-w-0">
          <DialogTitle className="[overflow-wrap:anywhere]">
            {isEditing
              ? t("Edit {{v0}}", { v0: user.display_name })
              : t("Add user")}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? t(
                  "Update this account's display name, global roles and product access.",
                )
              : t(
                  "Create an internal account and choose their product access.",
                )}
          </DialogDescription>
        </DialogHeader>

        <form
          className="grid min-w-0 gap-5 [overflow-wrap:anywhere]"
          onSubmit={(event) => void submit(event)}
        >
          {submissionError !== null ? (
            <Alert
              ref={conflictRef}
              tabIndex={-1}
              variant="destructive"
              aria-describedby={conflictId}
            >
              <AlertTitle>{t("We could not save this user")}</AlertTitle>
              <AlertDescription id={conflictId}>
                {submissionError === "conflict"
                  ? t(
                      "This user changed in another session or the administrator role must be preserved.",
                    )
                  : submissionError === "products-conflict"
                    ? t(
                        "Product access changed in another session, or a product or account is no longer available. No changes were saved. Reopen this form to review current roles before trying again.",
                      )
                    : submissionError === "products"
                      ? t(
                          "One or more selected products are no longer available. Remove their assignments or reopen this form to refresh the list. No account was created.",
                        )
                      : t(
                          "Your entries are still here. Review them and try again.",
                        )}
              </AlertDescription>
            </Alert>
          ) : null}

          {isEditing ? (
            <div className="grid min-w-0 grid-cols-1 gap-2">
              <span className="text-sm font-medium">
                {t("Corporate email")}
              </span>
              <p className="min-w-0 text-sm [overflow-wrap:anywhere]">
                {user.email}
              </p>
              <p className="text-sm text-muted-foreground">
                {t(
                  "Email cannot be changed. Create a new account to correct it.",
                )}
              </p>
            </div>
          ) : (
            <div className="grid gap-2">
              <Label htmlFor={emailId}>{t("Corporate email")}</Label>
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
                    ? t("An account already uses this corporate email.")
                    : t("Enter a corporate email.")}
                </p>
              ) : null}
            </div>
          )}

          <div className="grid gap-2">
            <Label htmlFor={displayNameId}>{t("Display name")}</Label>
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
                {t("Enter a display name.")}
              </p>
            ) : null}
          </div>

          <fieldset
            ref={roleGroupRef}
            role="group"
            tabIndex={roleError ? -1 : undefined}
            aria-labelledby={roleGroupId}
            aria-describedby={roleError ? roleErrorId : undefined}
            className="grid min-w-0 gap-3 rounded-lg border p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <legend id={roleGroupId} className="px-1 text-sm font-medium">
              {t("Roles")}
            </legend>
            <p className="text-sm text-muted-foreground">
              {t(
                "Administrator grants access to all products. Other global roles require a separate product assignment.",
              )}
            </p>
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
                      {t("You cannot remove your own administrator role.")}
                    </p>
                  ) : null}
                </div>
              );
            })}
            {roleError ? (
              <p id={roleErrorId} className="text-sm text-destructive">
                {t("Select at least one role.")}
              </p>
            ) : null}
          </fieldset>

          <UserProductAssignments
            accessToken={accessToken}
            disabled={pending}
            user={user}
            value={productAssignments}
            onChange={setProductAssignments}
          />

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t("Cancel")}
            </Button>
            <Button type="submit" disabled={pending} aria-busy={pending}>
              {isEditing ? t("Save user") : t("Create user")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
