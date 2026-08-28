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
    flushSync(() => setSecret(""));
    onAcknowledged();
  }

  return (
    <Dialog open onOpenChange={() => undefined}>
      <DialogContent
        showCloseButton={false}
        onEscapeKeyDown={(event) => event.preventDefault()}
        onPointerDownOutside={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Temporary password created</DialogTitle>
          <DialogDescription>
            Save this temporary password for {displayName}. It is shown only
            once and must be changed at the next sign-in.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div
            aria-label="Temporary password"
            className="select-all break-all rounded-lg border bg-muted p-4 font-mono text-sm [overflow-wrap:anywhere]"
          >
            {secret}
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => void copyTemporaryPassword()}
          >
            Copy temporary password
          </Button>
          <p role="status" aria-live="polite" className="min-h-5 text-sm">
            {copyStatus}
          </p>
        </div>

        <DialogFooter>
          <Button type="button" onClick={acknowledgeTemporaryPassword}>
            I saved the password
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
