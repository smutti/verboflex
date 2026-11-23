import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import {
  getAdminProduct,
  getAdminRepository,
  type AdminRepositoryResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { t, useUiLanguage } from "../../i18n";
import { PublishedMappingImports } from "../admin/imports/PublishedMappingImports";
import { loadMappedRepositoryIds } from "../admin/repositories/product-repository-usage";

function SourceUpdates({
  accessToken,
  productId,
}: {
  accessToken: string;
  productId: string;
}) {
  useUiLanguage();
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<
    | { status: "loading" }
    | { status: "error" }
    | { status: "ready"; repositories: AdminRepositoryResponse[] }
  >({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;
    async function loadSources() {
      const product = await getAdminProduct({
        auth: accessToken,
        path: { product_id: productId },
        signal,
      });
      if (!product.data || product.data.id !== productId)
        throw new Error("Product unavailable");
      const revision = product.data.active_revision;
      const ids = revision
        ? await loadMappedRepositoryIds({
            accessToken,
            productId,
            revisionId: revision.id,
            signal,
          })
        : [];
      const repositories: AdminRepositoryResponse[] = [];
      for (const repositoryId of ids) {
        if (signal.aborted) return;
        const result = await getAdminRepository({
          auth: accessToken,
          path: { repository_id: repositoryId },
          signal,
        });
        if (!result.data || result.data.id !== repositoryId)
          throw new Error("Repository unavailable");
        repositories.push(result.data);
      }
      if (!signal.aborted) setLoad({ status: "ready", repositories });
    }
    void loadSources().catch(() => {
      if (!signal.aborted) setLoad({ status: "error" });
    });
    return () => controller.abort();
  }, [accessToken, productId, attempt]);

  return (
    <section className="grid min-w-0 gap-4">
      <h2 className="text-heading font-semibold">{t("Update catalog")}</h2>
      <p className="text-muted-foreground">
        {t(
          "Bring new and changed strings into VerboFlex. To send approved translations to Bitbucket, choose Publish translations.",
        )}
      </p>
      <p className="text-sm text-muted-foreground">
        {t("You can leave this page while the catalog updates.")}
      </p>
      {load.status === "loading" && <p role="status">{t("Loading sources")}</p>}
      {load.status === "error" && (
        <Alert>
          <AlertTitle>{t("Sources unavailable")}</AlertTitle>
          <AlertDescription>
            <Button
              variant="outline"
              onClick={() => {
                setLoad({ status: "loading" });
                setAttempt((value) => value + 1);
              }}
            >
              {t("Retry loading sources")}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {load.status === "ready" && (
        <PublishedMappingImports
          accessToken={accessToken}
          productId={productId}
          repositories={load.repositories}
          headingLevel="h3"
          catalogView
          compact
        />
      )}
    </section>
  );
}

export function ProductSourceUpdatesPage({
  accessToken,
}: {
  accessToken: string;
}) {
  const productId = useParams<"productId">().productId ?? "";
  return (
    <SourceUpdates
      key={`${productId}:${accessToken}`}
      accessToken={accessToken}
      productId={productId}
    />
  );
}
