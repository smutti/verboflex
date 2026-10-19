import {
  readCurrentUser,
  refreshAccessToken,
  type AccessTokenResponse,
  type CurrentUserResponse,
} from "../../api/client";
import { client } from "../../api/client/client.gen";
import { createClient } from "../../api/client/client";

let pendingRefresh: ReturnType<typeof refreshAccessToken> | undefined;

// Rotation consumes the cookie. Share concurrent calls (including StrictMode
// restoration) and serialize tabs so they cannot reuse the same refresh cookie.
export function refreshSessionCookie() {
  if (!pendingRefresh) {
    const refresh = () => refreshAccessToken();
    const request = navigator.locks
      ? navigator.locks.request("verboflex-session-refresh", refresh)
      : refresh();
    pendingRefresh = request.finally(() => {
      pendingRefresh = undefined;
    });
  }
  return pendingRefresh;
}

export function requiresPasswordChange(error: unknown): boolean {
  return (
    !!error &&
    typeof error === "object" &&
    "detail" in error &&
    error.detail === "Password change required"
  );
}

interface RenewalOptions {
  authority: AccessTokenResponse;
  principal: CurrentUserResponse;
  isCurrent: () => boolean;
  onInvalid: () => void;
  onRestricted: (accessToken: string) => void;
  onPrincipal: (principal: CurrentUserResponse) => void;
}

export function installSessionRenewal(options: RenewalOptions) {
  // Components use the original in-memory token as their stable session scope.
  // Only this transport rotates the bearer, preserving open editors and drafts.
  const scopeToken = options.authority.access_token;
  let accessToken = scopeToken;
  let expiresAt = Date.now() + options.authority.expires_in * 1000;
  let disposed = false;
  let renewal: Promise<void> | undefined;
  const requests = new WeakSet<Request>();
  const isCurrent = () => !disposed && options.isCurrent();
  const requireCurrent = () => {
    if (!isCurrent()) throw new Error("Session changed");
  };
  const unavailable = () =>
    new Response(
      JSON.stringify({
        detail: "Session renewal interrupted the request. Please try again.",
      }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );

  async function renew() {
    requireCurrent();
    if (!renewal) {
      renewal = (async () => {
        const result = await refreshSessionCookie();
        requireCurrent();
        if (!result.data) {
          if (result.response?.status === 401) options.onInvalid();
          throw new Error("Session renewal unavailable");
        }
        if (result.data.must_change_password) {
          options.onRestricted(result.data.access_token);
          throw new Error("Password change required");
        }

        // Identity validation must bypass these interceptors to avoid recursion.
        const identity = await readCurrentUser({
          auth: result.data.access_token,
          client: createClient(client.getConfig()),
        });
        requireCurrent();
        if (!identity.data) {
          if (identity.response?.status === 401) options.onInvalid();
          if (
            identity.response?.status === 403 &&
            requiresPasswordChange(identity.error)
          ) {
            options.onRestricted(result.data.access_token);
          }
          throw new Error("Session identity unavailable");
        }
        if (identity.data.id !== options.principal.id) {
          // Another tab may have signed into a different account. Never send
          // this user's pending request with the other account's authority.
          options.onInvalid();
          throw new Error("Session account changed");
        }
        if (identity.data.must_change_password) {
          options.onRestricted(result.data.access_token);
          throw new Error("Password change required");
        }
        accessToken = result.data.access_token;
        expiresAt = Date.now() + result.data.expires_in * 1000;
        options.onPrincipal(identity.data);
      })().finally(() => {
        renewal = undefined;
      });
    }
    return renewal;
  }

  async function inspect(response: Response, bearer: string | null) {
    if (!isCurrent() || bearer !== `Bearer ${accessToken}`) return;
    if (response.status === 401) options.onInvalid();
    if (response.status === 403) {
      try {
        if (
          requiresPasswordChange(await response.clone().json()) &&
          isCurrent() &&
          bearer === `Bearer ${accessToken}`
        ) {
          options.onRestricted(accessToken);
        }
      } catch {
        // Ordinary permission failures do not revoke the session.
      }
    }
  }

  const requestInterceptor = client.interceptors.request.use(
    async (request) => {
      if (request.headers.get("Authorization") !== `Bearer ${scopeToken}`) {
        return request;
      }
      requireCurrent();
      // Check on every request, including after a suspended/background tab wakes.
      // Refresh before writes so an expired bearer never submits them first.
      if (renewal || Date.now() >= expiresAt - 30_000) await renew();
      requireCurrent();
      request.signal.throwIfAborted();
      request.headers.set("Authorization", `Bearer ${accessToken}`);
      requests.add(request);
      return request;
    },
  );

  const responseInterceptor = client.interceptors.response.use(
    async (response, request, requestOptions) => {
      if (!requests.has(request) || !isCurrent()) return response;
      if (response.status !== 401) {
        await inspect(response, request.headers.get("Authorization"));
        return response;
      }
      try {
        // A late 401 for the previous bearer shares the already completed
        // rotation instead of consuming another cookie.
        if (request.headers.get("Authorization") === `Bearer ${accessToken}`) {
          await renew();
        }
        requireCurrent();
        request.signal.throwIfAborted();
        // Never replay a write. The caller retains its draft and can retry.
        if (request.method !== "GET" && request.method !== "HEAD")
          return unavailable();
        const headers = new Headers(request.headers);
        headers.set("Authorization", `Bearer ${accessToken}`);
        const fetchRequest = requestOptions.fetch ?? globalThis.fetch;
        const retried = await fetchRequest(new Request(request, { headers }));
        await inspect(retried, headers.get("Authorization"));
        if (retried.status === 401 && isCurrent()) return unavailable();
        return retried;
      } catch {
        // Do not report a recoverable renewal failure as an authority rejection
        // to feature code that clears its editor on 401.
        return isCurrent() ? unavailable() : response;
      }
    },
  );

  return {
    renew,
    dispose() {
      disposed = true;
      client.interceptors.request.eject(requestInterceptor);
      client.interceptors.response.eject(responseInterceptor);
    },
  };
}
