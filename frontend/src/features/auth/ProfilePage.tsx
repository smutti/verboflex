import { t, useUiLanguage } from "@/i18n";
import { LanguagePicker } from "@/i18n/LanguagePicker";
import { KeyRound, Languages, UserRound } from "lucide-react";

import type { CurrentUserResponse } from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { PasswordChangeForm } from "./ChangePasswordPage";
import { ROLE_LABELS } from "./roleLabels";

export function ProfilePage({ principal }: { principal: CurrentUserResponse }) {
  useUiLanguage();
  return (
    <div className="grid min-w-0 max-w-4xl gap-8">
      <header className="grid gap-2">
        <h1 className="text-display font-semibold">{t("Profile")}</h1>
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
              {t("Account details")}
            </h2>
            <p className="text-lg font-semibold">{principal.display_name}</p>
            <p className="break-words text-muted-foreground [overflow-wrap:anywhere]">
              {principal.email}
            </p>
          </div>
          <div
            className="flex flex-wrap gap-2"
            aria-label={t("Assigned roles")}
          >
            {principal.roles.map((role) => (
              <Badge key={role} variant="outline" className="rounded-md">
                {ROLE_LABELS[role]}
              </Badge>
            ))}
          </div>
        </div>
      </section>

      <section
        aria-labelledby="profile-language-title"
        className="grid max-w-2xl gap-3 rounded-lg border bg-secondary p-6 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <Languages aria-hidden="true" className="size-6 text-primary" />
          <h2
            id="profile-language-title"
            className="text-heading font-semibold"
          >
            {t("Interface language")}
          </h2>
        </div>
        <LanguagePicker />
        <p className="text-muted-foreground">
          {t(
            "Choose your interface language. This preference is saved in this browser. Workspace language selections choose the translation content you work on.",
          )}
        </p>
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
              {t("Change password")}
            </h2>
            <p className="text-muted-foreground">
              {t("Sign in again after changing your password.")}
            </p>
          </div>
        </div>
        <PasswordChangeForm submitLabel={t("Change password")} />
      </section>
    </div>
  );
}
