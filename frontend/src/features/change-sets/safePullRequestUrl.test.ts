import { expect, it } from "vitest";
import { safePullRequestUrl } from "./safePullRequestUrl";

const identity = { workspace: "acme", repository_slug: "mobile", pr_id: 41 };
const valid = "https://bitbucket.org/acme/mobile/pull-requests/41";

it("accepts only the exact authorized Bitbucket pull request", () => {
  expect(safePullRequestUrl({ ...identity, pr_url: valid })).toBe(valid);
});

it.each([
  "http://bitbucket.org/acme/mobile/pull-requests/41",
  "https://bitbucket.org.evil.test/acme/mobile/pull-requests/41",
  "https://evil.test/acme/mobile/pull-requests/41",
  "https://name@bitbucket.org/acme/mobile/pull-requests/41",
  "https://bitbucket.org:444/acme/mobile/pull-requests/41",
  "https://bitbucket.org/acme/mobile/pull-requests/42",
  "https://bitbucket.org/other/mobile/pull-requests/41",
  "https://bitbucket.org/acme/other/pull-requests/41",
  `${valid}?token=secret`,
  `${valid}#fragment`,
  `${valid}/`,
  "https://bitbucket.org/acme/mobile/pull-requests/041",
  "https://bitbucket.org/acme/%6dobile/pull-requests/41",
  "https://bitbucket.org/acme/mobile/../mobile/pull-requests/41",
  "https://bitbucket.org/acme/mobile/pull-requests/%34%31",
  "https://bitbucket.org/acme/mobile/pull-requests/41\n",
  "javascript:alert(1)",
])("rejects unsafe or ambiguous URL %s", (pr_url) => {
  expect(safePullRequestUrl({ ...identity, pr_url })).toBeNull();
});

it("rejects missing identity and encoded path separators", () => {
  expect(
    safePullRequestUrl({ ...identity, pr_id: null, pr_url: valid }),
  ).toBeNull();
  expect(
    safePullRequestUrl({
      ...identity,
      workspace: "a/b",
      pr_url: "https://bitbucket.org/a%2Fb/mobile/pull-requests/41",
    }),
  ).toBeNull();
});
