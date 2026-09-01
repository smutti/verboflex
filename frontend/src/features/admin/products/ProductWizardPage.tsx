import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
} from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import {
  createAdminProduct,
  getAdminProduct,
  listAdminRevisionMappings,
  type AdminMappingListResponse,
  updateAdminProductCandidate,
  type AdminMappingResponse,
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
import { Skeleton } from "../../../components/ui/skeleton";
import { Textarea } from "../../../components/ui/textarea";
import { ProductMappingsPage } from "../mappings/ProductMappingsPage";
import { ProductRepositoriesPage } from "../repositories/ProductRepositoriesPage";
import { useDirtyFormNavigationGuard } from "../../../components/navigation/DirtyFormNavigationGuard";

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

interface EditableProductLoad {
  mappedRepositoryIds: string[];
  product: AdminProductResponse;
}

const MAX_REVISION_MAPPING_PAGES = 50;

export interface MobileWizardNavigation {
  backDisabled: boolean;
  nextDisabled: boolean;
  nextLabel: string;
}

// Exported for focused behavior tests; production consumes the same pure navigation contract.
// eslint-disable-next-line react-refresh/only-export-components
export function mobileWizardNavigation(
  currentStep: number,
  productAvailable: boolean,
): MobileWizardNavigation {
  return {
    backDisabled: currentStep === 1,
    nextDisabled:
      currentStep === PRODUCT_STEPS.length ||
      (currentStep > 1 && !productAvailable),
    nextLabel:
      currentStep === PRODUCT_STEPS.length
        ? "Next"
        : `Next: ${PRODUCT_STEPS[currentStep]}`,
  };
}

function mappedRepositoryIds(mappings: readonly AdminMappingResponse[]) {
  return Array.from(
    new Set(
      mappings.flatMap((mapping) =>
        mapping.translations_repository_id === null
          ? [mapping.primary_repository_id]
          : [mapping.primary_repository_id, mapping.translations_repository_id],
      ),
    ),
  );
}

// Exported for route-level generated-client contract tests.
// eslint-disable-next-line react-refresh/only-export-components
export async function loadEditableProduct(
  accessToken: string,
  productId: string,
  signal = new AbortController().signal,
): Promise<EditableProductLoad> {
  const productResult = await getAdminProduct({
    auth: accessToken,
    path: { product_id: productId },
  });
  if (productResult.data === undefined) {
    throw new Error("product unavailable");
  }

  const product = productResult.data;
  const editableRevision =
    product.candidate_revision ?? product.active_revision;
  if (editableRevision === null) {
    return { mappedRepositoryIds: [], product };
  }

  const mappings: AdminMappingResponse[] = [];
  const mappingIds = new Set<string>();
  const consumedCursors = new Set<string>();
  let cursor: string | null = null;
  let pageCount = 0;
  do {
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (pageCount >= MAX_REVISION_MAPPING_PAGES) {
      throw new Error("product mappings exceeded page limit");
    }
    const mappingsResult: { data?: AdminMappingListResponse } =
      await listAdminRevisionMappings({
        auth: accessToken,
        path: {
          product_id: productId,
          revision_id: editableRevision.id,
        },
        query: { cursor, limit: 50 },
      });
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (mappingsResult.data === undefined) {
      throw new Error("product mappings unavailable");
    }
    for (const mapping of mappingsResult.data.items) {
      if (!mappingIds.has(mapping.id)) {
        mappingIds.add(mapping.id);
        mappings.push(mapping);
      }
    }
    cursor = mappingsResult.data.next_cursor;
    pageCount += 1;
    if (cursor !== null) {
      if (consumedCursors.has(cursor)) {
        throw new Error("product mappings repeated cursor");
      }
      consumedCursors.add(cursor);
    }
  } while (cursor !== null);

  if (signal.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
  return {
    mappedRepositoryIds: mappedRepositoryIds(mappings),
    product,
  };
}

function responseStatus(result: { response?: Response }) {
  // Stryker disable next-line OptionalChaining: a missing generated response and a thrown status access both map to the same bounded generic failure.
  return result.response?.status;
}

function savedDescription(product: AdminProductResponse | undefined) {
  return (
    product?.candidate_revision?.description ??
    product?.active_revision?.description ??
    ""
  );
}

function savedName(product: AdminProductResponse | undefined) {
  return (
    product?.candidate_revision?.name ??
    product?.active_revision?.name ??
    product?.name ??
    ""
  );
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
  const routeProductId = useParams<"productId">().productId;
  const nameId = useId();
  const descriptionId = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const detailsFormRef = useRef<HTMLFormElement>(null);
  const routeLoadControllerRef = useRef<AbortController | null>(null);
  const routeLoadGenerationRef = useRef(0);
  const stepErrorRef = useRef<HTMLDivElement>(null);
  const submitPendingRef = useRef(false);
  const [product, setProduct] = useState(initialProduct);
  const [savedNameValue, setSavedNameValue] = useState(
    savedName(initialProduct),
  );
  const [savedDescriptionValue, setSavedDescriptionValue] = useState(
    savedDescription(initialProduct),
  );
  const [name, setName] = useState(savedNameValue);
  const [description, setDescription] = useState(savedDescriptionValue);
  const [currentStep, setCurrentStep] = useState(1);
  const [routeLoadState, setRouteLoadState] = useState<
    "error" | "loading" | "ready"
  >(
    routeProductId === undefined || initialProduct !== undefined
      ? "ready"
      : "loading",
  );
  const [selectedRepositoryIds, setSelectedRepositoryIds] = useState<
    Set<string>
  >(() => new Set());
  const [pending, setPending] = useState(false);
  const [nameError, setNameError] = useState<"required" | "duplicate" | null>(
    null,
  );
  const [submissionError, setSubmissionError] = useState(false);
  const [pendingNavigation, setPendingNavigation] =
    useState<PendingNavigation | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);

  const dirty =
    name !== savedNameValue || description !== savedDescriptionValue;
  useDirtyFormNavigationGuard(
    `product-details:${routeProductId ?? initialProduct?.id ?? "new"}`,
    dirty,
  );

  const loadRouteProduct = useCallback(async () => {
    if (routeProductId === undefined || initialProduct !== undefined) {
      return;
    }
    const generation = ++routeLoadGenerationRef.current;
    routeLoadControllerRef.current?.abort();
    const controller = new AbortController();
    routeLoadControllerRef.current = controller;
    setRouteLoadState("loading");
    try {
      const loaded = await loadEditableProduct(
        accessToken,
        routeProductId,
        controller.signal,
      );
      if (
        controller.signal.aborted ||
        generation !== routeLoadGenerationRef.current
      ) {
        return;
      }
      const loadedName = savedName(loaded.product);
      const loadedDescription = savedDescription(loaded.product);
      setProduct(loaded.product);
      setSavedNameValue(loadedName);
      setSavedDescriptionValue(loadedDescription);
      setName(loadedName);
      setDescription(loadedDescription);
      setSelectedRepositoryIds(new Set(loaded.mappedRepositoryIds));
      setRouteLoadState("ready");
    } catch {
      if (
        !controller.signal.aborted &&
        generation === routeLoadGenerationRef.current
      ) {
        setRouteLoadState("error");
      }
    }
  }, [accessToken, initialProduct, routeProductId]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadRouteProduct();
      }
    });
    return () => {
      active = false;
      routeLoadGenerationRef.current += 1;
      routeLoadControllerRef.current?.abort();
    };
  }, [loadRouteProduct]);

  useEffect(() => {
    if (stepError !== null) {
      stepErrorRef.current?.focus();
    }
  }, [stepError]);

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
    setName(savedNameValue);
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
    if (
      product !== undefined &&
      product.candidate_revision === null &&
      product.active_revision === null
    ) {
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
      const expectedRevision =
        product?.candidate_revision ?? product?.active_revision;
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
                expected_candidate_version: expectedRevision!.version,
              },
            });

      if (result.data !== undefined) {
        const responseProduct = result.data;
        if (
          product !== undefined &&
          responseProduct.candidate_revision === null
        ) {
          setSubmissionError(true);
          return;
        }
        const responseDescription = savedDescription(responseProduct);
        const responseName = savedName(responseProduct);
        setProduct(responseProduct);
        setSavedNameValue(responseName);
        setSavedDescriptionValue(responseDescription);
        setName(responseName);
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

  function selectRepository(repositoryId: string) {
    setSelectedRepositoryIds((current) => new Set(current).add(repositoryId));
    setStepError(null);
  }

  function goBack() {
    setStepError(null);
    setCurrentStep((step) => step - 1);
  }

  function goForward() {
    setStepError(null);
    if (currentStep === 1) {
      detailsFormRef.current?.requestSubmit();
      return;
    }
    if (currentStep === 2 && selectedRepositoryIds.size === 0) {
      setStepError("Select or register a repository before continuing.");
      return;
    }
    setCurrentStep((step) => step + 1);
  }

  if (routeLoadState === "loading") {
    return (
      <section
        className="grid max-w-3xl gap-4"
        role="status"
        aria-live="polite"
      >
        <Skeleton className="h-9 w-64 max-w-full" />
        <Skeleton className="h-48 w-full" />
        <span>Loading product draft</span>
      </section>
    );
  }

  if (routeLoadState === "error") {
    return (
      <Alert variant="destructive" className="max-w-3xl">
        <AlertTitle>Product draft unavailable</AlertTitle>
        <AlertDescription>
          <p>
            We could not load this page. Retry without leaving the
            administration area.
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadRouteProduct()}
          >
            Retry loading page
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const mobileNavigation = mobileWizardNavigation(
    currentStep,
    product !== undefined,
  );

  return (
    <section
      className="mx-auto grid w-full min-w-0 max-w-3xl gap-8 overflow-x-clip"
      aria-labelledby="product-wizard-title"
    >
      <div className="grid gap-2">
        <h1
          id="product-wizard-title"
          className="break-words text-display font-semibold [overflow-wrap:anywhere]"
        >
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
        aria-live="polite"
        className="grid gap-1 rounded-lg border bg-secondary p-4 md:hidden"
      >
        <span className="text-label font-semibold">
          Step {currentStep} of 5
        </span>
        <span>{PRODUCT_STEPS[currentStep - 1]}</span>
      </p>

      {currentStep === 1 ? (
        <form
          ref={detailsFormRef}
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
        <ProductRepositoriesPage
          accessToken={accessToken}
          embedded
          selectedRepositoryIds={Array.from(selectedRepositoryIds)}
          onRepositorySelected={(repository) => selectRepository(repository.id)}
        />
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

      {stepError !== null ? (
        <Alert
          ref={stepErrorRef}
          tabIndex={-1}
          variant="destructive"
          aria-label="Wizard step incomplete"
        >
          <AlertTitle>Complete this step</AlertTitle>
          <AlertDescription>{stepError}</AlertDescription>
        </Alert>
      ) : null}

      <nav
        aria-label="Wizard navigation"
        className="grid min-w-0 grid-cols-2 gap-3 md:hidden"
      >
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px] min-w-0"
          disabled={mobileNavigation.backDisabled}
          onClick={goBack}
        >
          Back
        </Button>
        <Button
          type="button"
          className="min-h-[44px] min-w-0 whitespace-normal"
          aria-label={mobileNavigation.nextLabel}
          disabled={mobileNavigation.nextDisabled || pending}
          aria-busy={pending}
          onClick={goForward}
        >
          Next
        </Button>
      </nav>

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
