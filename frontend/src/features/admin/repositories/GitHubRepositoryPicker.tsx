import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import { useEffect, useId, useRef, useState } from "react";
import { FolderGit2, Star } from "lucide-react";

import {
  connectAdminGithubRepository,
  getAdminRepository,
  type AdminRepositoryResponse,
  type GitHubRepositoryResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";

export function GitHubRepositoryPicker({
  accessToken,
  onRepositorySelected,
  selectedRepositoryIds = [],
}: {
  accessToken: string;
  onRepositorySelected?: (repository: AdminRepositoryResponse) => void;
  selectedRepositoryIds?: readonly string[];
}) {
  useUiLanguage();
  const id = useId();
  const [identity, setIdentity] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<
    Array<AdminRepositoryResponse & Partial<GitHubRepositoryResponse>>
  >([]);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const selectedKey = JSON.stringify(selectedRepositoryIds);
  useEffect(() => {
    const request = new AbortController();
    const ids: string[] = JSON.parse(selectedKey);
    void Promise.all(
      ids.map((id) =>
        getAdminRepository({
          auth: accessToken,
          path: { repository_id: id },
          signal: request.signal,
        }),
      ),
    )
      .then((results) => {
        if (request.signal.aborted) return;
        setSelected((current) =>
          results.flatMap((result) =>
            result.data?.provider === "github"
              ? [
                  current.find((item) => item.id === result.data!.id) ??
                    result.data,
                ]
              : [],
          ),
        );
      })
      .catch(() => {
        /* Retain the wizard selection if labels cannot load. */
      });
    return () => request.abort();
  }, [accessToken, selectedKey]);

  async function connect() {
    if (controller.current) return;
    const value = identity
      .trim()
      .replace(/^https:\/\/github\.com\//i, "")
      .replace(/\/$/, "");
    const match = /^([a-z\d][a-z\d_-]{0,99})\/([a-z\d][a-z\d_.-]{0,99})$/i.exec(
      value,
    );
    if (!match) {
      setError(
        "Enter owner/repository or https://github.com/owner/repository.",
      );
      return;
    }
    const request = new AbortController();
    controller.current = request;
    setPending(true);
    setError(null);
    try {
      const result = await connectAdminGithubRepository({
        auth: accessToken,
        signal: request.signal,
        body: { owner: match[1], repository: match[2] },
      });
      if (request.signal.aborted) return;
      if (!result.data) {
        setError(
          result.response?.status === 429
            ? "GitHub has reached its public request limit. Wait and try again."
            : "Repository unavailable. Check that it exists, is public, and that the owner and name are correct.",
        );
        return;
      }
      const repository = result.data;
      setSelected((current) => [
        ...current.filter((item) => item.id !== repository.id),
        repository,
      ]);
      onRepositorySelected?.(repository);
      setIdentity("");
    } catch {
      if (!request.signal.aborted)
        setError("Could not reach GitHub. Try again shortly.");
    } finally {
      if (!request.signal.aborted) setPending(false);
      controller.current = null;
    }
  }

  return (
    <section
      className="grid gap-5"
      aria-label={t("GitHub repository connection")}
    >
      <div className="flex items-center gap-2">
        <FolderGit2 aria-hidden="true" className="size-5" />
        <h2 className="text-heading font-semibold">
          {t("Connect a GitHub repository")}
        </h2>
      </div>
      <p className="text-sm text-muted-foreground">
        {t(
          "Public repositories, no token required. Changes and pull requests to GitHub are not supported.",
        )}
      </p>
      <div className="grid gap-2">
        <Label htmlFor={id}>{t("GitHub repository")}</Label>
        <Input
          id={id}
          placeholder={t("owner/repository or GitHub URL")}
          value={identity}
          maxLength={230}
          disabled={pending}
          onChange={(event) => setIdentity(event.target.value)}
        />
      </div>
      <Button
        type="button"
        className="justify-self-start"
        disabled={pending || !identity.trim()}
        onClick={() => void connect()}
      >
        {pending ? t("Connecting…") : t("Connect GitHub repository")}
      </Button>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>{t("Connection failed")}</AlertTitle>
          <AlertDescription>{t(error)}</AlertDescription>
        </Alert>
      )}
      {selected.length > 0 && (
        <section
          className="grid gap-3"
          aria-label={t("Connected GitHub repositories")}
        >
          <h3 className="font-semibold">{t("Connected repositories")}</h3>
          {selected.map((repo) => (
            <div key={repo.id} className="grid gap-2 rounded-lg border p-4">
              <strong>
                {repo.workspace}/{repo.repository_slug}
              </strong>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{t("GitHub · Import only")}</Badge>
                {repo.default_branch && (
                  <Badge variant="secondary">{repo.default_branch}</Badge>
                )}
                {repo.language && (
                  <Badge variant="secondary">{repo.language}</Badge>
                )}
                {repo.stars !== undefined && (
                  <span className="inline-flex items-center gap-1 text-sm">
                    <Star className="size-4" aria-hidden="true" />
                    {repo.stars.toLocaleString(getUiLanguage())} {t(" stars")}
                  </span>
                )}
              </div>
            </div>
          ))}
        </section>
      )}
    </section>
  );
}
