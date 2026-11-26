import { useEffect, useState, type FormEvent } from "react";
import {
  getProjectReviewer,
  setProjectReviewer,
  type PullRequestReviewer,
} from "../../../api/client";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { t, useUiLanguage } from "@/i18n";

function profileUuid(input: string) {
  let id = input.trim();
  if (id.startsWith("https://bitbucket.org/")) {
    try {
      id = decodeURIComponent(
        id.slice("https://bitbucket.org/".length).replace(/\/$/, ""),
      );
    } catch {
      return null;
    }
  }
  if (id.startsWith("{") && id.endsWith("}")) id = id.slice(1, -1);
  return /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id)
    ? id.toLowerCase()
    : null;
}

export function ProjectReviewerForm({
  accessToken,
  productId,
}: {
  accessToken: string;
  productId: string;
}) {
  useUiLanguage();
  const [reviewer, setReviewer] = useState<PullRequestReviewer | null>();
  const [name, setName] = useState("");
  const [profile, setProfile] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const { data } = await getProjectReviewer({
          auth: accessToken,
          path: { product_id: productId },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!data) throw new Error();
        setReviewer(data.reviewer);
        setName(data.reviewer?.name ?? "");
        setProfile(
          data.reviewer
            ? "https://bitbucket.org/{" + data.reviewer.uuid + "}/"
            : "",
        );
        setError("");
      } catch {
        if (!controller.signal.aborted)
          setError("Could not load the project reviewer.");
      }
    })();
    return () => controller.abort();
  }, [accessToken, productId, reload]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || reviewer === undefined) return;
    const uuid = profileUuid(profile);
    setSaved(false);
    if (!uuid) {
      setError(
        "Copy the Bitbucket profile link containing the account ID, or paste the Bitbucket UUID.",
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      const { data } = await setProjectReviewer({
        auth: accessToken,
        path: { product_id: productId },
        body: { name: name.trim(), uuid },
      });
      if (!data?.reviewer) throw new Error();
      setReviewer(data.reviewer);
      setSaved(true);
    } catch {
      setError("Could not save the reviewer. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => void save(event)}
      className="grid gap-3 rounded-lg border bg-card p-4"
      aria-labelledby="pr-reviewer-title"
    >
      <h2 id="pr-reviewer-title" className="text-heading font-semibold">
        {t("Pull request reviewer")}
      </h2>
      <p>
        {t(
          "Bitbucket will ask this person to review new pull requests for this project.",
        )}
      </p>
      {reviewer !== undefined && (
        <fieldset disabled={busy} className="grid gap-3">
          <Label htmlFor="reviewer-name">{t("Reviewer name")}</Label>
          <Input
            id="reviewer-name"
            value={name}
            required
            maxLength={120}
            onChange={(e) => {
              setName(e.target.value);
              setSaved(false);
              setError("");
            }}
          />
          <Label htmlFor="reviewer-profile">
            {t("Bitbucket profile link")}
          </Label>
          <Input
            id="reviewer-profile"
            value={profile}
            required
            maxLength={256}
            aria-describedby="profile-help"
            onChange={(e) => {
              setProfile(e.target.value);
              setSaved(false);
              setError("");
            }}
          />
          <p id="profile-help" className="text-sm text-muted-foreground">
            {t(
              "In a Bitbucket pull request, copy the link on the person’s avatar. Choose someone who can review changes in this repository.",
            )}
          </p>
          <Button
            type="submit"
            className="w-fit"
            disabled={busy || !name.trim() || !profile.trim()}
          >
            {busy ? t("Saving…") : t("Save reviewer")}
          </Button>
        </fieldset>
      )}
      {error && <p role="alert">{t(error)}</p>}
      {reviewer === undefined && error && (
        <Button
          type="button"
          className="w-fit"
          variant="outline"
          onClick={() => setReload((n) => n + 1)}
        >
          {t("Reload configuration")}
        </Button>
      )}
      {saved && <p role="status">{t("Reviewer saved.")}</p>}
    </form>
  );
}
