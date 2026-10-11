import type { ChangeSetResponse, ChangeSetSource } from "../../api/client";
import { safePullRequestUrl } from "./safePullRequestUrl";

export function PullRequestLink({ record }: { record: ChangeSetResponse }) {
  if (record.pr_id === null) return null;
  const href = safePullRequestUrl(record);
  return href ? (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex min-h-[44px] items-center underline"
    >
      Open pull request #{record.pr_id} (opens in a new tab)
    </a>
  ) : (
    <p>
      Pull request #{record.pr_id} is recorded. A verified link is unavailable.
    </p>
  );
}
export function SourceProvenance({ sources }: { sources: ChangeSetSource[] }) {
  return (
    <ul className="grid min-w-0 gap-(--space-md)">
      {sources.map((source) => (
        <li
          key={`${source.mapping_id}:${source.repository_side}:${source.repository_id}`}
          className="min-w-0 wrap-anywhere"
        >
          <p className="font-semibold">
            Imported source ·{" "}
            {source.repository_side === "keys"
              ? "Keys read basis"
              : source.repository_side === "translations"
                ? "Translations write repository"
                : "Direct repository"}
          </p>
          <p>
            {source.workspace}/{source.repository_slug} · {source.branch}
          </p>
          <p>
            Commit <code>{source.commit_hash}</code>
          </p>
          <p>
            Mapping {source.mapping_id} · Import {source.import_execution_id}
          </p>
        </li>
      ))}
    </ul>
  );
}
