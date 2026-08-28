import {
  useId,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
} from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  createAdminProduct,
  updateAdminProductCandidate,
  type AdminProductResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../../components/ui/alert-dialog";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Textarea } from "../../../components/ui/textarea";
import { ProductMappingsPage } from "../mappings/ProductMappingsPage";
import { ProductRepositoriesPage } from "../repositories/ProductRepositoriesPage";

export interface ProductWizardPageProps {
  accessToken: string;
  initialProduct?: AdminProductResponse;
}

const PRODUCT_STEPS = [
  "Product details",
  "Repositories",
  "Mappings",
  "Preview",
  "Review and publish",
] as const;

interface PendingNavigation {
  returnFocus: HTMLButtonElement;
  step: number;
}

function responseStatus(result: { response?: Response }) {
  // Stryker disable next-line OptionalChaining: a missing generated response and a thrown status access both map to the same bounded generic failure.
  return result.response?.status;
}

function savedDescription(product: AdminProductResponse | undefined) {
  return product?.candidate_revision?.description ?? "";
}

function FutureStep({ productId, step }: { productId: string; step: number }) {
  switch (step) {
    case 4:
      return (
        <section className="grid gap-4 rounded-lg border bg-secondary p-6">
          <h2 className="text-heading font-semibold">Validation has not run</h2>
          <p className="text-muted-foreground">
            Run validation to detect files, languages, and partial translation
            samples.
          </p>
          <Button asChild variant="outline" className="justify-self-start">
            <Link
              to={`/admin/products/${encodeURIComponent(productId)}/preview`}
            >
              Open product preview
            </Link>
          </Button>
        </section>
      );
    default:
      return (
        <section className="grid gap-4 rounded-lg border bg-secondary p-6">
          <h2 className="text-heading font-semibold">Review and publish</h2>
          <p className="text-muted-foreground">
            Complete repository, mapping, and preview confirmation before
            publishing.
          </p>
          <Link
            className="justify-self-start font-semibold text-primary underline-offset-4 hover:underline"
            to={`/admin/products/${encodeURIComponent(productId)}/preview`}
          >
            Review preview blockers
          </Link>
          <Button type="button" disabled className="justify-self-start">
            Publish product
          </Button>
        </section>
      );
  }
}

export function ProductWizardPage({
  accessToken,
  initialProduct,
}: ProductWizardPageProps) {
  const nameId = useId();
  const descriptionId = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const submitPendingRef = useRef(false);
  const [product, setProduct] = useState(initialProduct);
  const [savedName, setSavedName] = useState(initialProduct?.name ?? "");
  const [savedDescriptionValue, setSavedDescriptionValue] = useState(
    savedDescription(initialProduct),
  );
  const [name, setName] = useState(savedName);
  const [description, setDescription] = useState(savedDescriptionValue);
  const [currentStep, setCurrentStep] = useState(1);
  const [pending, setPending] = useState(false);
  const [nameError, setNameError] = useState<"required" | "duplicate" | null>(
    null,
  );
  const [submissionError, setSubmissionError] = useState(false);
  const [pendingNavigation, setPendingNavigation] =
    useState<PendingNavigation | null>(null);

  const dirty = name !== savedName || description !== savedDescriptionValue;

  function requestStep(step: number, event: MouseEvent<HTMLButtonElement>) {
    if (step === currentStep) {
      return;
    }
    if (dirty) {
      setPendingNavigation({ returnFocus: event.currentTarget, step });
      return;
    }
    setCurrentStep(step);
  }

  function keepEditing(navigation: PendingNavigation) {
    setPendingNavigation(null);
    queueMicrotask(() => navigation.returnFocus.focus());
  }

  function discardAndNavigate(navigation: PendingNavigation) {
    setName(savedName);
    setDescription(savedDescriptionValue);
    setNameError(null);
    setSubmissionError(false);
    setCurrentStep(navigation.step);
    setPendingNavigation(null);
  }

  async function submitDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitPendingRef.current) {
      return;
    }
    if (name.trim().length === 0) {
      // Stryker disable next-line StringLiteral: every non-duplicate sentinel renders the same exact required-name contract.
      setNameError("required");
      nameRef.current!.focus();
      return;
    }
    // Stryker disable next-line ConditionalExpression,BlockStatement: removal reaches the same caught generic failure without invoking a generated operation.
    if (product !== undefined && product.candidate_revision === null) {
      setSubmissionError(true);
      return;
    }

    submitPendingRef.current = true;
    setPending(true);
    setNameError(null);
    setSubmissionError(false);
    const normalizedDescription =
      description.trim().length === 0 ? null : description;

    try {
      const result =
        product === undefined
          ? await createAdminProduct({
              auth: accessToken,
              body: { name, description: normalizedDescription },
            })
          : await updateAdminProductCandidate({
              auth: accessToken,
              path: { product_id: product.id },
              body: {
                name,
                description: normalizedDescription,
                expected_candidate_version: product.candidate_revision!.version,
              },
            });

      if (result.data !== undefined) {
        const responseProduct = result.data;
        const responseDescription = savedDescription(responseProduct);
        setProduct(responseProduct);
        setSavedName(responseProduct.name);
        setSavedDescriptionValue(responseDescription);
        setName(responseProduct.name);
        setDescription(responseDescription);
        toast.success("Draft saved");
        setCurrentStep(2);
        return;
      }

      if (responseStatus(result) === 409) {
        setNameError("duplicate");
        nameRef.current!.focus();
        return;
      }
      setSubmissionError(true);
    } catch {
      setSubmissionError(true);
    } finally {
      submitPendingRef.current = false;
      setPending(false);
    }
  }

  function updateCandidateVersion(version: number) {
    setProduct((current) =>
      current === undefined || current.candidate_revision === null
        ? current
        : {
            ...current,
            candidate_revision: {
              ...current.candidate_revision,
              version,
            },
          },
    );
  }

  return (
    <section
      className="mx-auto grid w-full min-w-0 max-w-3xl gap-8 overflow-x-clip"
      aria-labelledby="product-wizard-title"
    >
      <div className="grid gap-2">
        <h1 id="product-wizard-title" className="text-display font-semibold">
          {product === undefined ? "Create product" : product.name}
        </h1>
        <p className="text-muted-foreground">
          Configure a candidate draft without changing published configuration.
        </p>
      </div>

      <nav aria-label="Product setup steps" className="hidden min-w-0 md:block">
        <ol className="grid grid-cols-5 gap-2">
          {PRODUCT_STEPS.map((label, index) => {
            const step = index + 1;
            return (
              <li key={label} className="min-w-0">
                <button
                  type="button"
                  className="min-h-11 w-full rounded-md border px-2 py-3 text-left text-label font-semibold whitespace-nowrap aria-[current=step]:border-primary aria-[current=step]:text-primary"
                  aria-current={currentStep === step ? "step" : undefined}
                  data-completed={step < currentStep ? "true" : undefined}
                  disabled={product === undefined && step > 1}
                  onClick={(event) => requestStep(step, event)}
                >
                  {label}
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <p
        aria-label="Product setup progress"
        className="grid gap-1 rounded-lg border bg-secondary p-4 md:hidden"
      >
        <span className="text-label font-semibold">
          Step {currentStep} of 5
        </span>
        <span>{PRODUCT_STEPS[currentStep - 1]}</span>
      </p>

      {currentStep === 1 ? (
        <form
          className="grid gap-6 rounded-lg border bg-secondary p-6"
          onSubmit={(event) => void submitDetails(event)}
        >
          <div className="grid gap-2">
            <Label htmlFor={nameId}>Name</Label>
            <Input
              ref={nameRef}
              id={nameId}
              value={name}
              aria-invalid={nameError !== null}
              aria-describedby={
                nameError !== null ? `${nameId}-error` : undefined
              }
              onChange={(event) => {
                setName(event.target.value);
                setNameError(null);
                setSubmissionError(false);
              }}
            />
            {nameError !== null ? (
              <p id={`${nameId}-error`} className="text-sm text-destructive">
                {nameError === "duplicate"
                  ? "A product already uses this name."
                  : "Enter a product name."}
              </p>
            ) : null}
          </div>

          <div className="grid gap-2">
            <Label htmlFor={descriptionId}>Description</Label>
            <Textarea
              id={descriptionId}
              value={description}
              onChange={(event) => {
                setDescription(event.target.value);
                setSubmissionError(false);
              }}
            />
            <p className="text-sm text-muted-foreground">Optional</p>
          </div>

          {submissionError ? (
            <Alert variant="destructive">
              <AlertTitle>Draft not saved</AlertTitle>
              <AlertDescription>
                We could not save this draft. Your entries are still here.
                Review the error and try again.
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap justify-end gap-3">
            <Button type="submit" disabled={pending} aria-busy={pending}>
              Save and continue
            </Button>
          </div>
        </form>
      ) : currentStep === 2 && product !== undefined ? (
        <ProductRepositoriesPage accessToken={accessToken} embedded />
      ) : currentStep === 3 &&
        product !== undefined &&
        product.candidate_revision !== null ? (
        <ProductMappingsPage
          accessToken={accessToken}
          candidateVersion={product.candidate_revision.version}
          embedded
          onCandidateVersionChange={updateCandidateVersion}
          productId={product.id}
        />
      ) : product !== undefined ? (
        <FutureStep productId={product.id} step={currentStep} />
      ) : null}

      {pendingNavigation !== null ? (
        <AlertDialog
          open
          onOpenChange={(open) => !open && keepEditing(pendingNavigation)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Leave without saving?</AlertDialogTitle>
              <AlertDialogDescription>
                Your unsaved entries on this page will be lost.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep editing</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                onClick={() => discardAndNavigate(pendingNavigation)}
              >
                Discard changes
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </section>
  );
}
