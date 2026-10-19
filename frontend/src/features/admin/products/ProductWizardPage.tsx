import { t, useUiLanguage } from "@/i18n";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type MouseEvent,
} from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";

import {
  createAdminProduct,
  getAdminProduct,
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
import { Skeleton } from "../../../components/ui/skeleton";
import { Textarea } from "../../../components/ui/textarea";
import { ProductPreviewPage } from "../previews/ProductPreviewPage";
import {
  ProductMappingsPage,
  type ProductMappingsPageHandle,
} from "../mappings/ProductMappingsPage";
import { ProductRepositoriesPage } from "../repositories/ProductRepositoriesPage";
import { loadMappedRepositoryIds } from "../repositories/product-repository-usage";
import { useDirtyFormNavigationGuard } from "../../../components/navigation/DirtyFormNavigationGuard";

export interface ProductWizardPageProps {
  accessToken: string;
  initialProduct?: AdminProductResponse;
}

const PRODUCT_STEPS = [
  "Product details",
  "Repositories",
  "Translation sources",
  "Preview and import",
] as const;

interface PendingNavigation {
  returnFocus: HTMLButtonElement;
  step: number;
}

interface EditableProductLoad {
  mappedRepositoryIds: string[];
  product: AdminProductResponse;
}

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
        ? t("Next")
        : t("Next: {{step}}", { step: t(PRODUCT_STEPS[currentStep]) }),
  };
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

  const repositoryIds = await loadMappedRepositoryIds({
    accessToken,
    productId,
    revisionId: editableRevision.id,
    signal,
  });
  return {
    mappedRepositoryIds: repositoryIds,
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

export function ProductWizardPage({
  accessToken,
  initialProduct,
}: ProductWizardPageProps) {
  useUiLanguage();
  const routeProductId = useParams<"productId">().productId;
  const nameId = useId();
  const descriptionId = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const detailsFormRef = useRef<HTMLFormElement>(null);
  const mappingEditorRef = useRef<ProductMappingsPageHandle>(null);
  const mappingContinuePendingRef = useRef(false);
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
  const [mappingDirty, setMappingDirty] = useState(false);
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
    if (pending || mappingContinuePendingRef.current || step === currentStep) {
      return;
    }
    if (dirty || mappingDirty) {
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
    setMappingDirty(false);
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
        toast.success(t("Draft saved"));
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

  function goBack(event: MouseEvent<HTMLButtonElement>) {
    setStepError(null);
    requestStep(currentStep - 1, event);
  }

  async function saveSourceAndContinue() {
    if (mappingContinuePendingRef.current || !mappingEditorRef.current) return;
    mappingContinuePendingRef.current = true;
    setPending(true);
    try {
      if (await mappingEditorRef.current.saveAndContinue()) {
        setMappingDirty(false);
        setCurrentStep(4);
      }
    } finally {
      mappingContinuePendingRef.current = false;
      setPending(false);
    }
  }

  async function goForward(event: MouseEvent<HTMLButtonElement>) {
    if (pending || mappingContinuePendingRef.current) return;
    setStepError(null);
    if (currentStep === 1) {
      detailsFormRef.current?.requestSubmit();
      return;
    }
    if (currentStep === 2 && selectedRepositoryIds.size === 0) {
      setStepError("Select a repository before continuing.");
      return;
    }
    if (currentStep === 3 && mappingEditorRef.current) {
      await saveSourceAndContinue();
      return;
    }
    requestStep(currentStep + 1, event);
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
        <span>{t("Loading product draft")}</span>
      </section>
    );
  }

  if (routeLoadState === "error") {
    return (
      <Alert variant="destructive" className="max-w-3xl">
        <AlertTitle>{t("Product draft unavailable")}</AlertTitle>
        <AlertDescription>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadRouteProduct()}
          >
            {t("Retry loading page")}
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
      className={`mx-auto grid w-full min-w-0 gap-8 overflow-x-clip ${currentStep >= 3 ? "max-w-6xl" : "max-w-3xl"}`}
      aria-labelledby="product-wizard-title"
    >
      <div className="grid gap-2">
        <h1
          id="product-wizard-title"
          className="break-words text-display font-semibold [overflow-wrap:anywhere]"
        >
          {product === undefined ? t("Create product") : product.name}
        </h1>
      </div>

      <nav
        aria-label={t("Product setup steps")}
        className="hidden min-w-0 md:block"
      >
        <ol className="grid grid-cols-4 gap-2">
          {PRODUCT_STEPS.map((label, index) => {
            const step = index + 1;
            return (
              <li key={label} className="min-w-0">
                <button
                  type="button"
                  className="min-h-11 w-full rounded-md border px-2 py-3 text-left text-label font-semibold whitespace-normal break-words aria-[current=step]:border-primary aria-[current=step]:text-primary"
                  aria-current={currentStep === step ? "step" : undefined}
                  data-completed={step < currentStep ? "true" : undefined}
                  disabled={pending || (product === undefined && step > 1)}
                  onClick={(event) => requestStep(step, event)}
                >
                  {t(label)}
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <p
        aria-label={t("Product setup progress")}
        aria-live="polite"
        className="grid gap-1 rounded-lg border bg-secondary p-4 md:hidden"
      >
        <span className="text-label font-semibold">
          {t("Step ")}
          {currentStep} {t(" of ")}
          {PRODUCT_STEPS.length}
        </span>
        <span>{t(PRODUCT_STEPS[currentStep - 1])}</span>
      </p>

      {currentStep === 1 ? (
        <form
          ref={detailsFormRef}
          className="grid gap-6 rounded-lg border bg-secondary p-6"
          onSubmit={(event) => void submitDetails(event)}
        >
          <div className="grid gap-2">
            <Label htmlFor={nameId}>{t("Name")}</Label>
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
                  ? t("A product already uses this name.")
                  : t("Enter a product name.")}
              </p>
            ) : null}
          </div>

          <div className="grid gap-2">
            <Label htmlFor={descriptionId}>{t("Description")}</Label>
            <Textarea
              id={descriptionId}
              value={description}
              onChange={(event) => {
                setDescription(event.target.value);
                setSubmissionError(false);
              }}
            />
            <p className="text-sm text-muted-foreground">{t("Optional")}</p>
          </div>

          {submissionError ? (
            <Alert variant="destructive">
              <AlertTitle>{t("Draft not saved")}</AlertTitle>
              <AlertDescription>
                {t(
                  "We could not save this draft. Your entries are still here. Review the error and try again.",
                )}
              </AlertDescription>
            </Alert>
          ) : null}
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
          ref={mappingEditorRef}
          accessToken={accessToken}
          candidateVersion={product.candidate_revision.version}
          selectedRepositoryIds={
            selectedRepositoryIds.size > 0
              ? Array.from(selectedRepositoryIds)
              : undefined
          }
          embedded
          onCandidateVersionChange={updateCandidateVersion}
          onDirtyChange={setMappingDirty}
          onContinueRequested={saveSourceAndContinue}
          productId={product.id}
        />
      ) : currentStep === 4 && product !== undefined ? (
        <ProductPreviewPage
          key={product.id}
          accessToken={accessToken}
          productId={product.id}
          embedded
          onProductPublished={setProduct}
        />
      ) : product !== undefined ? (
        <Alert>
          <AlertTitle>{t("Create a draft to edit sources")}</AlertTitle>
          <AlertDescription>
            {t(
              "Save the product details to start a draft, then choose its translation sources.",
            )}
          </AlertDescription>
        </Alert>
      ) : null}

      {stepError !== null ? (
        <Alert
          ref={stepErrorRef}
          tabIndex={-1}
          variant="destructive"
          aria-label={t("Wizard step incomplete")}
        >
          <AlertTitle>{t("Complete this step")}</AlertTitle>
          <AlertDescription>{stepError}</AlertDescription>
        </Alert>
      ) : null}

      <nav
        aria-label={t("Wizard navigation")}
        className="flex min-w-0 flex-wrap justify-between gap-3 border-t pt-4"
      >
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px] min-w-0"
          disabled={mobileNavigation.backDisabled || pending}
          onClick={goBack}
        >
          {t("Back")}
        </Button>
        {currentStep < PRODUCT_STEPS.length ? (
          <Button
            type="button"
            className="min-h-[44px] min-w-0 whitespace-normal"
            aria-label={mobileNavigation.nextLabel}
            disabled={mobileNavigation.nextDisabled || pending}
            aria-busy={pending}
            onClick={(event) => void goForward(event)}
          >
            {mobileNavigation.nextLabel}
          </Button>
        ) : null}
      </nav>

      {pendingNavigation !== null ? (
        <AlertDialog
          open
          onOpenChange={(open) => !open && keepEditing(pendingNavigation)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("Leave without saving?")}</AlertDialogTitle>
              <AlertDialogDescription>
                {t("Your unsaved entries on this page will be lost.")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("Keep editing")}</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                onClick={() => discardAndNavigate(pendingNavigation)}
              >
                {t("Discard changes")}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </section>
  );
}
