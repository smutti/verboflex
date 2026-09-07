import { KeyRound, UserRound } from "lucide-react";

import type { CurrentUserResponse } from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { PasswordChangeForm } from "./ChangePasswordPage";
import { ROLE_LABELS } from "./roleLabels";

export function ProfilePage({ principal }: { principal: CurrentUserResponse }) {
  return (
    <div className="grid min-w-0 max-w-4xl gap-8">
      <header className="grid gap-2">
        <h1 className="text-display font-semibold">Profile</h1>
        <p className="text-muted-foreground">
          Review your account information and manage your password.
        </p>
      </header>

      <section
        aria-labelledby="profile-identity-title"
        className="grid gap-6 rounded-lg border bg-secondary p-6 shadow-sm sm:grid-cols-[auto_minmax(0,1fr)]"
      >
        <span
          aria-hidden="true"
          className="grid size-14 place-items-center rounded-full bg-primary/10 text-primary"
        >
          <UserRound className="size-8" />
        </span>
        <div className="grid min-w-0 gap-4">
          <div className="grid gap-1">
            <h2
              id="profile-identity-title"
              className="text-heading font-semibold"
            >
              Account details
            </h2>
            <p className="text-lg font-semibold">{principal.display_name}</p>
            <p className="break-words text-muted-foreground [overflow-wrap:anywhere]">
              {principal.email}
            </p>
          </div>
          <div className="flex flex-wrap gap-2" aria-label="Assigned roles">
            {principal.roles.map((role) => (
              <Badge key={role} variant="outline" className="rounded-md">
                {ROLE_LABELS[role]}
              </Badge>
            ))}
          </div>
        </div>
      </section>

      <section
        aria-labelledby="profile-password-title"
        className="grid max-w-2xl gap-6 rounded-lg border bg-secondary p-6 shadow-sm"
      >
        <div className="flex items-start gap-3">
          <KeyRound aria-hidden="true" className="mt-0.5 size-6 text-primary" />
          <div className="grid gap-1">
            <h2
              id="profile-password-title"
              className="text-heading font-semibold"
            >
              Change password
            </h2>
            <p className="text-muted-foreground">
              After changing your password, you will sign in again with the new
              credential.
            </p>
          </div>
        </div>
        <PasswordChangeForm submitLabel="Change password" />
      </section>
    </div>
  );
}
