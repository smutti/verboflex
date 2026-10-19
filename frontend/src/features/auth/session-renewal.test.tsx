import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, type PropsWithChildren } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { client } from "../../api/client/client.gen";
import { SessionProvider, useSession } from "./session";

const principal = {
  id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
  email: "person@example.com",
  display_name: "Person",
  roles: ["translator"],
  must_change_password: false,
};
const authority = (token: string) => ({
  access_token: token,
  token_type: "bearer",
  expires_in: 900,
  must_change_password: false,
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const denied = () => json({ detail: "Invalid access token" }, 401);
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function Wrapper({ children }: PropsWithChildren) {
  return <SessionProvider restoreOnMount={false}>{children}</SessionProvider>;
}
function StrictWrapper({ children }: PropsWithChildren) {
  return (
    <StrictMode>
      <SessionProvider>{children}</SessionProvider>
    </StrictMode>
  );
}

const initialConfig = client.getConfig();
let requests: Request[];
let refresh: () => Response | Promise<Response>;
let identity: (request: Request) => Response | Promise<Response>;
let protectedRequest: (request: Request) => Response | Promise<Response>;
let loginToken: string;
function sent(path: string) {
  return requests.filter((request) => new URL(request.url).pathname === path);
}
function read(signal?: AbortSignal) {
  return client.get({
    url: "/protected",
    headers: { Authorization: "Bearer initial-token" },
    signal,
  });
}
function write() {
  return client.post({
    url: "/protected",
    headers: { Authorization: "Bearer initial-token" },
    body: { text: "Synthetic draft" },
  });
}
async function login() {
  const hook = renderHook(() => useSession(), { wrapper: Wrapper });
  await act(() =>
    hook.result.current.login({
      email: principal.email,
      password: "synthetic password",
    }),
  );
  expect(hook.result.current.state.status).toBe("authenticated");
  return hook;
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  loginToken = "initial-token";
  requests = [];
  refresh = () => json(authority("renewed-token"));
  identity = () => json(principal);
  protectedRequest = (request) =>
    request.headers.get("Authorization") === "Bearer renewed-token"
      ? json({ text: "Saved" })
      : denied();
  client.setConfig({
    baseUrl: "http://localhost",
    fetch: async (input) => {
      const request = input as Request;
      requests.push(request);
      switch (new URL(request.url).pathname) {
        case "/api/v1/auth/token":
          return json(authority(loginToken));
        case "/api/v1/auth/refresh":
          return refresh();
        case "/api/v1/auth/logout":
          return new Response(null, { status: 204 });
        case "/api/v1/users/me":
          return identity(request);
        case "/protected":
          return protectedRequest(request);
        default:
          throw new Error("Unexpected synthetic request");
      }
    },
  });
});
afterEach(() => {
  cleanup();
  client.setConfig(initialConfig);
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("automatic session renewal through the generated client", () => {
  it("renews an expired bearer before sending a write and keeps its session scope stable", async () => {
    const { result } = await login();
    vi.setSystemTime(Date.now() + 901_000);
    let response!: Awaited<ReturnType<typeof write>>;
    await act(async () => {
      response = await write();
    });
    expect(response.data).toEqual({ text: "Saved" });
    expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
    expect(sent("/protected")).toHaveLength(1);
    expect(sent("/protected")[0].headers.get("Authorization")).toBe(
      "Bearer renewed-token",
    );
    expect(await sent("/protected")[0].json()).toEqual({
      text: "Synthetic draft",
    });
    expect(result.current.state).toMatchObject({
      status: "authenticated",
      accessToken: "initial-token",
    });
  });

  it("renews on 401 and retries a read exactly once with the new bearer", async () => {
    const { result } = await login();
    let response!: Awaited<ReturnType<typeof read>>;
    await act(async () => {
      response = await read();
    });
    expect(response.data).toEqual({ text: "Saved" });
    expect(
      sent("/protected").map((r) => r.headers.get("Authorization")),
    ).toEqual(["Bearer initial-token", "Bearer renewed-token"]);
    expect(result.current.state.status).toBe("authenticated");
    await act(async () => {
      await read();
    });
    expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
  });

  it("never replays a rejected write after renewing its session", async () => {
    const { result } = await login();
    let response!: Awaited<ReturnType<typeof write>>;
    await act(async () => {
      response = await write();
    });
    expect(response.response?.status).toBe(503);
    expect(sent("/protected")).toHaveLength(1);
    expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
    expect(result.current.state.status).toBe("authenticated");
    await act(async () => {
      response = await write();
    });
    expect(response.data).toEqual({ text: "Saved" });
    expect(sent("/protected")).toHaveLength(2);
  });

  it.each([false, true])(
    "shares one renewal between concurrent requests (expired: %s)",
    async (expired) => {
      await login();
      if (expired) vi.setSystemTime(Date.now() + 901_000);
      const gate = deferred<Response>();
      refresh = () => gate.promise;
      let pending!: ReturnType<typeof read>[];
      await act(async () => {
        pending = [read(), read(), read()];
        await waitFor(() =>
          expect(sent("/api/v1/auth/refresh")).toHaveLength(1),
        );
        gate.resolve(json(authority("renewed-token")));
        const responses = await Promise.all(pending);
        expect(responses.every((r) => r.response?.status === 200)).toBe(true);
      });
      expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
    },
  );

  it("reuses a completed rotation for a delayed old-token 401", async () => {
    await login();
    const late = deferred<Response>();
    let first = true;
    protectedRequest = (request) => {
      if (request.headers.get("Authorization") === "Bearer renewed-token")
        return json({ ok: true });
      if (first) {
        first = false;
        return late.promise;
      }
      return denied();
    };
    await act(async () => {
      const delayed = read();
      await waitFor(() => expect(sent("/protected")).toHaveLength(1));
      await read();
      late.resolve(denied());
      expect((await delayed).response?.status).toBe(200);
    });
    expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
  });

  it("signs out when the refresh cookie is expired or revoked", async () => {
    const { result } = await login();
    refresh = denied;
    await act(async () => {
      await read();
    });
    expect(result.current.state).toEqual({ status: "signed_out" });
    expect(sent("/protected")).toHaveLength(1);
  });

  it("ignores a retry rejection after a newer rotation has already succeeded", async () => {
    const { result } = await login();
    const lateRetry = deferred<Response>();
    protectedRequest = (request) =>
      request.headers.get("Authorization") === "Bearer renewed-token"
        ? lateRetry.promise
        : denied();
    await act(async () => {
      const pending = read();
      await waitFor(() => expect(sent("/protected")).toHaveLength(2));
      refresh = () => json(authority("latest-token"));
      await result.current.restoreSession();
      lateRetry.resolve(denied());
      expect((await pending).response?.status).toBe(503);
    });
    expect(result.current.state.status).toBe("authenticated");
  });

  it.each([401, 503])(
    "handles identity validation failure %s without submitting the waiting write",
    async (status) => {
      const { result } = await login();
      vi.setSystemTime(Date.now() + 901_000);
      identity = () => json({ detail: "Identity unavailable" }, status);
      await act(async () => {
        await write();
      });
      expect(result.current.state.status).toBe(
        status === 401 ? "signed_out" : "authenticated",
      );
      expect(sent("/protected")).toHaveLength(0);
      if (status === 503) {
        identity = () => json(principal);
        await act(async () => {
          expect((await write()).response?.status).toBe(200);
        });
      }
    },
  );

  it("stops after a fresh bearer is also rejected", async () => {
    const { result } = await login();
    protectedRequest = denied;
    await act(async () => {
      await read();
    });
    expect(result.current.state).toEqual({ status: "signed_out" });
    expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
    expect(sent("/protected")).toHaveLength(2);
  });

  it.each([0, 403, 429, 503])(
    "keeps the session recoverable after refresh failure %s",
    async (status) => {
      const { result } = await login();
      refresh = () => {
        if (!status) throw new TypeError("Offline");
        return json({ detail: "Unavailable" }, status);
      };
      await act(async () => {
        expect((await read()).response?.status).toBe(503);
      });
      expect(result.current.state.status).toBe("authenticated");
      refresh = () => json(authority("renewed-token"));
      await act(async () => {
        expect((await read()).response?.status).toBe(200);
      });
      expect(result.current.state.status).toBe("authenticated");
    },
  );

  it("keeps a draft mounted while renewing and while the server is unavailable", async () => {
    function Editor() {
      const { state, login } = useSession();
      return state.status === "authenticated" ? (
        <textarea key={state.accessToken} aria-label="Draft" />
      ) : (
        <button
          onClick={() =>
            void login({
              email: principal.email,
              password: "synthetic password",
            })
          }
        >
          Sign in
        </button>
      );
    }
    render(
      <Wrapper>
        <Editor />
      </Wrapper>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    const editor = await screen.findByRole("textbox", { name: "Draft" });
    await userEvent.type(editor, "Unsaved synthetic text");
    refresh = () => json({ detail: "Unavailable" }, 503);
    await act(async () => {
      await read();
    });
    expect(screen.getByRole("textbox", { name: "Draft" })).toBe(editor);
    refresh = () => json(authority("renewed-token"));
    await act(async () => {
      await read();
    });
    expect(screen.getByRole("textbox", { name: "Draft" })).toBe(editor);
    expect(editor).toHaveValue("Unsaved synthetic text");
  });

  it("never submits a pending write as a different account from another tab", async () => {
    const { result } = await login();
    vi.setSystemTime(Date.now() + 901_000);
    identity = () =>
      json({ ...principal, id: "45f123f7-ebad-4dad-8b5d-dcc3214b3b07" });
    await act(async () => {
      await write();
    });
    expect(result.current.state).toEqual({ status: "signed_out" });
    expect(sent("/protected")).toHaveLength(0);
  });

  it("honors revoked identity and required password changes during renewal", async () => {
    const { result } = await login();
    identity = () => json({ detail: "Password change required" }, 403);
    await act(async () => {
      await read();
    });
    expect(result.current.state).toEqual({
      status: "password_change_required",
      accessToken: "renewed-token",
    });
    expect(sent("/protected")).toHaveLength(1);
  });

  it.each(["logout", "login", "unmount"])(
    "cannot revive or replay the old session after %s",
    async (action) => {
      const { result, unmount } = await login();
      const gate = deferred<Response>();
      refresh = () => gate.promise;
      await act(async () => {
        const pending = read();
        await waitFor(() =>
          expect(sent("/api/v1/auth/refresh")).toHaveLength(1),
        );
        if (action === "logout") await result.current.logout();
        if (action === "unmount") unmount();
        if (action === "login") {
          loginToken = "other-login-token";
          await result.current.login({
            email: principal.email,
            password: "synthetic password",
          });
        }
        gate.resolve(json(authority("renewed-token")));
        await pending;
      });
      if (action === "logout")
        expect(result.current.state.status).toBe("signed_out");
      if (action === "login")
        expect(result.current.state).toMatchObject({
          status: "authenticated",
          accessToken: "other-login-token",
        });
      expect(sent("/protected")).toHaveLength(1);
    },
  );

  it("does not retry an aborted read or cancel another request sharing renewal", async () => {
    await login();
    const gate = deferred<Response>();
    refresh = () => gate.promise;
    const controller = new AbortController();
    await act(async () => {
      const cancelled = read(controller.signal);
      const active = read();
      await waitFor(() => expect(sent("/api/v1/auth/refresh")).toHaveLength(1));
      controller.abort();
      gate.resolve(json(authority("renewed-token")));
      await cancelled;
      expect((await active).response?.status).toBe(200);
    });
    expect(sent("/protected")).toHaveLength(3);
  });

  it("shares the refresh cookie request across StrictMode mount restoration", async () => {
    const gate = deferred<Response>();
    refresh = () => gate.promise;
    const { result } = renderHook(() => useSession(), {
      wrapper: StrictWrapper,
    });
    await waitFor(() => expect(sent("/api/v1/auth/refresh")).toHaveLength(1));
    await act(async () => {
      gate.resolve(json(authority("renewed-token")));
    });
    await waitFor(() =>
      expect(result.current.state.status).toBe("authenticated"),
    );
    expect(sent("/api/v1/auth/refresh")).toHaveLength(1);
    expect(sent("/api/v1/users/me")).toHaveLength(1);
  });

  it("keeps initial restoration recoverable on network failure", async () => {
    refresh = () => {
      throw new TypeError("Offline");
    };
    const { result } = renderHook(() => useSession(), {
      wrapper: StrictWrapper,
    });
    await waitFor(() =>
      expect(result.current.state.status).toBe("session_unavailable"),
    );
    refresh = () => json(authority("renewed-token"));
    await act(() => result.current.restoreSession());
    expect(result.current.state.status).toBe("authenticated");
  });
});
