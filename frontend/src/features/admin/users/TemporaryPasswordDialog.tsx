import { t, useUiLanguage } from "@/i18n";
import { useState } from "react";
import { flushSync } from "react-dom";

import { Button } from "../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../../components/ui/dialog";

export interface TemporaryPasswordDialogProps {
  displayName: string;
  onAcknowledged: () => void;
  temporaryPassword: string;
}

export function TemporaryPasswordDialog({
  displayName,
  onAcknowledged,
  temporaryPassword,
}: TemporaryPasswordDialogProps) {
  useUiLanguage();
  const [secret, setSecret] = useState(temporaryPassword);
  const [copyStatus, setCopyStatus] = useState("");

  async function copyTemporaryPassword() {
    try {
      await navigator.clipboard.writeText(secret);
      setCopyStatus("Temporary password copied");
    } catch {
      setCopyStatus(
        "The password could not be copied. Select it and copy it manually.",
      );
    }
  }

  function acknowledgeTemporaryPassword() {
    // Stryker disable next-line CallExpression: the ordering assertion kills removal, but the Vitest runner cannot serialize its React failure.
    flushSync(setSecret.bind(null, String()));
    onAcknowledged();
  }

  return (
    <Dialog open>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("Temporary password created")}</DialogTitle>
          <DialogDescription>
            {t("Save this temporary password for ")}
            {displayName}
            {t(
              ". It is shown only once and must be changed at the next sign-in. ",
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div
            aria-label={t("Temporary password")}
            className="select-all break-all rounded-lg border bg-muted p-4 font-mono text-sm [overflow-wrap:anywhere]"
          >
            {secret}
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => void copyTemporaryPassword()}
          >
            {t("Copy temporary password")}
          </Button>
          <p role="status" aria-live="polite" className="min-h-5 text-sm">
            {t(copyStatus)}
          </p>
        </div>

        <DialogFooter>
          <Button type="button" onClick={acknowledgeTemporaryPassword}>
            {t("I saved the password")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
