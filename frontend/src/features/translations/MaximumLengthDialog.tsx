import { t, useUiLanguage } from "@/i18n";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  deleteTranslationConstraint,
  getTranslationGroup,
  putTranslationConstraint,
  type RoleName,
  type TranslationGroupDetailResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../components/ui/alert-dialog";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { completeTranslationDetail } from "./translationDetailAuthority";

export type ConstraintMutationMode = "create" | "edit" | "remove";
export interface MaximumLengthDialogProps {
  accessToken: string;
  detail: TranslationGroupDetailResponse;
  roles: readonly RoleName[];
  mode: ConstraintMutationMode;
  onClose: () => void;
  onChanged: (detail: TranslationGroupDetailResponse) => void;
  triggerElement: HTMLButtonElement | null;
  fallbackElement?: HTMLElement | null;
}
type Action = "save" | "remove" | "reload";
type Failure = "general" | "conflict" | "refresh" | null;
const actionClass = "h-auto min-h-[44px] whitespace-normal";

function AuthorizedDialog({
  accessToken,
  detail,
  mode,
  onClose,
  onChanged,
  triggerElement,
  fallbackElement,
}: MaximumLengthDialogProps) {
  useUiLanguage();
  const [authority, setAuthority] = useState(detail);
  const [input, setInput] = useState(
    String(
      detail.explicit_maximum ?? detail.values[0].constraint.maximum ?? "",
    ),
  );
  const [pending, setPending] = useState<Action | null>(null);
  const [failure, setFailure] = useState<Failure>(null);
  const [fieldError, setFieldError] = useState(false);
  const [replaceConfirmation, setReplaceConfirmation] = useState(false);
  const [open, setOpen] = useState(true);
  const generation = useRef(0);
  const active = useRef<{
    controller: AbortController;
    generation: number;
    identity: string;
  } | null>(null);
  const mounted = useRef(true);
  const committed = useRef(false);
  const intentionalClose = useRef(false);
  const field = useRef<HTMLInputElement>(null);
  const alert = useRef<HTMLDivElement>(null);
  const fieldId = useId();
  const identity = JSON.stringify([
    accessToken,
    authority.id,
    authority.language,
    authority.constraint_version,
  ]);
  const identityRef = useRef(identity);
  useLayoutEffect(() => {
    identityRef.current = identity;
  }, [identity]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      active.current?.controller.abort();
      active.current = null;
    };
  }, []);
  useEffect(() => {
    if (failure) alert.current?.focus();
  }, [failure, pending]);
  useEffect(() => {
    if (fieldError && pending === null) field.current?.focus();
  }, [fieldError, pending]);
  const isBase = authority.language === authority.base_language;
  const removing = mode === "remove";
  const successCopy = removing
    ? t("Maximum length removed")
    : t("Maximum length saved");
  const cancelLabel = removing
    ? isBase
      ? t("Keep base limit")
      : t("Keep language override")
    : t("Discard max length changes");
  const submitLabel = removing
    ? isBase
      ? t("Remove base limit")
      : t("Remove language override")
    : t("Save max length");
  const title = removing
    ? isBase
      ? t("Remove the base-language limit?")
      : t("Remove the {{v0}} override?", { v0: authority.language })
    : mode === "edit"
      ? t("Edit maximum length")
      : t("Set maximum length");
  const description = removing
    ? isBase
      ? t(
          "Languages without their own override will have no maximum length. Existing language overrides will remain.",
        )
      : authority.base_maximum === null
        ? t("This language will have no maximum length.")
        : t(
            "This language will inherit the current {{v0}} maximum of {{v1}} characters.",
            { v0: authority.base_language, v1: authority.base_maximum },
          )
    : t(
        "Maximum length counts visible characters. A combined emoji or composed character counts as one.",
      );

  function finishClose() {
    if (intentionalClose.current) return;
    intentionalClose.current = true;
    setOpen(false);
    onClose();
  }
  function requestClose(next: boolean) {
    if (!next && !active.current) finishClose();
  }
  function restoreFocus(event: Event) {
    event.preventDefault();
    if (!intentionalClose.current) return;
    const target = triggerElement?.isConnected
      ? triggerElement
      : fallbackElement;
    if (target?.isConnected) target.focus({ preventScroll: true });
  }

  async function execute(action: Action) {
    if (
      active.current ||
      intentionalClose.current ||
      (action !== "reload" && (failure === "conflict" || committed.current))
    )
      return;
    if (
      action === "save" &&
      (!/^\d+$/.test(input) ||
        !Number.isInteger(Number(input)) ||
        Number(input) > 1048576)
    ) {
      setFieldError(true);
      field.current?.focus();
      return;
    }
    const request = {
      controller: new AbortController(),
      generation: ++generation.current,
      identity,
    };
    active.current = request;
    setPending(action);
    setFieldError(false);
    const isLive = () =>
      mounted.current &&
      active.current === request &&
      generation.current === request.generation &&
      !request.controller.signal.aborted &&
      identityRef.current === request.identity;
    const path = {
      translation_group_id: authority.id,
      language: authority.language,
    };
    try {
      if (action !== "reload") {
        const result =
          action === "save"
            ? await putTranslationConstraint({
                auth: accessToken,
                path,
                body: {
                  max_chars: Number(input),
                  expected_version: authority.constraint_version ?? 0,
                },
                signal: request.controller.signal,
              })
            : await deleteTranslationConstraint({
                auth: accessToken,
                path,
                body: { expected_version: authority.constraint_version ?? 0 },
                signal: request.controller.signal,
              });
        if (!isLive()) return;
        if (!result.data) {
          if (result.response?.status === 422) {
            setFieldError(true);
            field.current?.focus();
          } else
            setFailure(
              result.response?.status === 409 ? "conflict" : "general",
            );
          return;
        }
        // A success may already be durable even if the following detail read fails.
        // Never expose a write retry in that state.
        committed.current = true;
        if (
          result.data.translation_group_id !== authority.id ||
          result.data.language !== authority.language
        )
          throw new Error("Mutation projection mismatch");
      }
      const result = await getTranslationGroup({
        auth: accessToken,
        path: { translation_group_id: authority.id },
        signal: request.controller.signal,
      });
      if (!isLive()) return;
      if (
        !result.data ||
        !completeTranslationDetail(result.data, authority.id) ||
        result.data.language !== authority.language
      )
        throw new Error("Detail unavailable");
      if (committed.current) {
        onChanged(result.data);
        if (!isLive()) return;
        toast.success(successCopy);
        finishClose();
      } else {
        setAuthority(result.data);
        setInput(
          String(
            result.data.explicit_maximum ??
              result.data.values[0].constraint.maximum ??
              "",
          ),
        );
        setFailure(null);
        setReplaceConfirmation(false);
        field.current?.focus();
      }
    } catch {
      if (isLive()) {
        setFailure(
          committed.current
            ? "refresh"
            : action === "reload"
              ? "conflict"
              : "general",
        );
        if (action === "reload") setReplaceConfirmation(false);
      }
    } finally {
      if (isLive()) {
        active.current = null;
        setPending(null);
      }
    }
  }

  const error = failure && (
    <Alert ref={alert} tabIndex={-1}>
      <AlertTitle>
        {failure === "conflict"
          ? t("Maximum length changed")
          : failure === "refresh"
            ? t("{{v0}}; current details could not be loaded", {
                v0: successCopy,
              })
            : removing
              ? t("Maximum length was not removed. Try again.")
              : t("Maximum length was not saved")}
      </AlertTitle>
      <AlertDescription className="space-y-(--space-sm)">
        {failure === "conflict" ? (
          <p>
            {t(
              "This constraint changed in another session. Reload the current value before saving again.",
            )}
          </p>
        ) : failure === "refresh" ? (
          <p>
            {t(
              "Reload the current value to see the saved result. The change will not be submitted again.",
            )}
          </p>
        ) : (
          !removing && <p>{t("Review the value and try again.")}</p>
        )}
        {(failure === "conflict" || failure === "refresh") && (
          <Button
            type="button"
            variant="outline"
            className={actionClass}
            disabled={pending !== null}
            onClick={() => setReplaceConfirmation(true)}
          >
            {t("Reload current value")}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
  const actions = (
    <>
      <Button
        type="button"
        variant="outline"
        className={actionClass}
        disabled={pending !== null}
        onClick={() => requestClose(false)}
      >
        {cancelLabel}
      </Button>
      <Button
        type={removing ? "button" : "submit"}
        className={actionClass}
        variant={removing ? "destructive" : "default"}
        disabled={
          pending !== null || failure === "conflict" || failure === "refresh"
        }
        aria-busy={pending === (removing ? "remove" : "save")}
        onClick={removing ? () => void execute("remove") : undefined}
      >
        {submitLabel}
      </Button>
    </>
  );
  const preventPendingEscape = (event: KeyboardEvent) => {
    if (active.current) event.preventDefault();
  };
  return (
    <>
      {removing ? (
        <AlertDialog open={open} onOpenChange={requestClose}>
          <AlertDialogContent
            className="max-h-[90dvh] overflow-y-auto"
            onEscapeKeyDown={preventPendingEscape}
            onCloseAutoFocus={restoreFocus}
          >
            <AlertDialogHeader>
              <AlertDialogTitle className="text-heading">
                {title}
              </AlertDialogTitle>
              <AlertDialogDescription>{description}</AlertDialogDescription>
            </AlertDialogHeader>
            {error}
            <AlertDialogFooter>{actions}</AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : (
        <Dialog open={open} onOpenChange={requestClose}>
          <DialogContent
            className="max-h-[90dvh] overflow-y-auto"
            showCloseButton={false}
            onEscapeKeyDown={preventPendingEscape}
            onPointerDownOutside={(event) => {
              if (active.current) event.preventDefault();
            }}
            onInteractOutside={(event) => {
              if (active.current) event.preventDefault();
            }}
            onCloseAutoFocus={restoreFocus}
            onOpenAutoFocus={(event) => {
              event.preventDefault();
              field.current?.focus();
            }}
          >
            <DialogHeader>
              <DialogTitle className="text-heading">{title}</DialogTitle>
              <DialogDescription>{description}</DialogDescription>
            </DialogHeader>
            <form
              noValidate
              className="grid gap-(--space-md)"
              onSubmit={(event) => {
                event.preventDefault();
                void execute("save");
              }}
            >
              {error}
              <div className="space-y-(--space-sm)">
                <Label htmlFor={fieldId}>{t("Maximum characters")}</Label>
                <Input
                  className="min-h-[44px] min-w-[44px]"
                  ref={field}
                  id={fieldId}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={1048576}
                  step={1}
                  value={input}
                  disabled={pending !== null}
                  aria-invalid={fieldError}
                  aria-describedby={fieldError ? `${fieldId}-error` : undefined}
                  onChange={(event) => {
                    setInput(event.target.value);
                    setFieldError(false);
                  }}
                />
                {fieldError && (
                  <p id={`${fieldId}-error`}>
                    {t("Enter a whole number from 0 to 1,048,576.")}
                  </p>
                )}
              </div>
              <p>
                {isBase
                  ? t(
                      "Languages without their own override inherit this value and will be recalculated.",
                    )
                  : authority.base_maximum === null
                    ? t("No base-language default is currently available.")
                    : t("This value overrides the {{v0}} default.", {
                        v0: authority.base_language,
                      })}
              </p>
              <DialogFooter>{actions}</DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
      <AlertDialog
        open={replaceConfirmation}
        onOpenChange={(next) => {
          if (!active.current) setReplaceConfirmation(next);
        }}
      >
        <AlertDialogContent
          className="max-h-[90dvh] overflow-y-auto"
          onEscapeKeyDown={preventPendingEscape}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (mounted.current && open) field.current?.focus();
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("Replace your entered value?")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "Your entered maximum will be replaced with the current server value. This does not save a change.",
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button
              className={actionClass}
              variant="outline"
              disabled={pending !== null}
              onClick={() => setReplaceConfirmation(false)}
            >
              {t("Keep entered value")}
            </Button>
            <Button
              className={actionClass}
              disabled={pending !== null}
              aria-busy={pending === "reload"}
              onClick={() => void execute("reload")}
            >
              {t("Replace entered value")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function MaximumLengthDialog(props: MaximumLengthDialogProps) {
  useUiLanguage();
  if (
    !props.roles.some(
      (role) => role === "admin" || role === "product_manager_reviewer",
    ) ||
    props.detail.base_language === null ||
    props.detail.is_deleted
  )
    return null;
  return (
    <AuthorizedDialog
      key={JSON.stringify([
        props.accessToken,
        props.detail.id,
        props.detail.language,
        props.detail.constraint_version,
        props.mode,
      ])}
      {...props}
    />
  );
}
