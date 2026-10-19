import { t, useUiLanguage } from "@/i18n";
export function Dashboard() {
  useUiLanguage();
  return (
    <section className="grid gap-2 rounded-lg border bg-secondary p-6">
      <h2 className="text-heading font-semibold">
        {t("Workspace ready for configuration")}
      </h2>
      <p className="max-w-3xl text-muted-foreground">
        {t(
          "Phase 1 confirms the platform shell, session, and services. Product and translation workflows will appear after configuration is added.",
        )}
      </p>
    </section>
  );
}
