import { t, useUiLanguage } from "@/i18n";
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/button";

export function AdminAccessDenied() {
  useUiLanguage();
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <section
      className="grid max-w-3xl gap-4 rounded-lg border bg-secondary p-6"
      aria-labelledby="admin-access-denied-title"
    >
      <h1
        ref={headingRef}
        id="admin-access-denied-title"
        tabIndex={-1}
        className="text-display font-semibold outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {t("Administrator access required")}
      </h1>
      <p className="text-muted-foreground">
        {t("Your account does not have permission to open administration.")}
      </p>
      <div>
        <Button asChild>
          <Link to="/">{t("Return to workspace")}</Link>
        </Button>
      </div>
    </section>
  );
}
