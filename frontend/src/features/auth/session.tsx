import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  changePassword as generatedChangePassword,
  logout as generatedLogout,
  issueToken,
  readCurrentUser,
  refreshAccessToken,
  type CurrentUserResponse,
} from "../../api/client";
import { client } from "../../api/client/client.gen";

export type SessionState =
  | { status: "checking_session" }
  | { status: "signed_out" }
  | { status: "password_change_required"; accessToken: string }
  | {
      status: "authenticated";
      accessToken: string;
      principal: CurrentUserResponse;
    };

export type SessionEvent =
  | { type: "check_session" }
  | { type: "sign_out" }
  | { type: "restrict"; accessToken: string }
  | {
      type: "authenticate";
      accessToken: string;
      principal: CurrentUserResponse;
    };

export function transitionSession(
  _state: SessionState,
  event: SessionEvent,
): SessionState {
  switch (event.type) {
    case "check_session":
      return { status: "checking_session" };
    case "sign_out":
      return { status: "signed_out" };
    case "restrict":
      return event.accessToken.length > 0
        ? {
            status: "password_change_required",
            accessToken: event.accessToken,
          }
        : { status: "signed_out" };
    case "authenticate":
      return event.accessToken.length > 0 &&
        !event.principal.must_change_password
        ? {
            status: "authenticated",
            accessToken: event.accessToken,
            principal: event.principal,
          }
        : { status: "signed_out" };
  }
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface PasswordChange {
  currentPassword: string;
  newPassword: string;
}

export interface SessionValue {
  state: SessionState;
  login: (credentials: LoginCredentials) => Promise<void>;
  changePassword: (passwords: PasswordChange) => Promise<void>;
  restoreSession: () => Promise<void>;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function initialSessionState(restoreOnMount: boolean): SessionState {
  return restoreOnMount
    ? { status: "checking_session" }
    : { status: "signed_out" };
}

export interface SessionProviderProps extends PropsWithChildren {
  restoreOnMount?: boolean;
}

export function SessionProvider({
  children,
  restoreOnMount = true,
}: SessionProviderProps) {
  const [state, setState] = useState<SessionState>(() =>
    initialSessionState(restoreOnMount),
  );
  const activeOperation = useRef(Symbol());

  useEffect(() => {
    if (
      state.status !== "authenticated" &&
      state.status !== "password_change_required"
    ) {
      return;
    }
    const accessToken = state.accessToken;
    const operation = activeOperation.current;
    let mounted = true;
    const interceptor = client.interceptors.response.use(
      async (response, request) => {
        if (request.headers.get("Authorization") !== `Bearer ${accessToken}`) {
          return response;
        }
        let event: SessionEvent | null =
          response.status === 401 ? { type: "sign_out" } : null;
        if (response.status === 403 && state.status === "authenticated") {
          try {
            const body: unknown = await response.clone().json();
            if (
              body &&
              typeof body === "object" &&
              "detail" in body &&
              body.detail === "Password change required"
            ) {
              event = { type: "restrict", accessToken };
            }
          } catch {
            // An ordinary denied action or unreadable error is not a session revocation.
          }
        }
        // A delayed response from a previous login must not revoke newer authority.
        if (event && mounted && activeOperation.current === operation) {
          activeOperation.current = Symbol();
          setState((current) => transitionSession(current, event));
        }
        return response;
      },
    );
    return () => {
      mounted = false;
      client.interceptors.response.eject(interceptor);
    };
  }, [state]);

  async function login(credentials: LoginCredentials) {
    const operation = Symbol();
    activeOperation.current = operation;
    const tokenResult = await issueToken({
      body: {
        username: credentials.email,
        password: credentials.password,
      },
    });
    if (activeOperation.current !== operation) {
      return;
    }
    const authority = tokenResult.data;
    if (authority === undefined) {
      setState((current) => transitionSession(current, { type: "sign_out" }));
      throw new Error("Session action failed");
    }
    if (authority.must_change_password) {
      setState((current) =>
        transitionSession(current, {
          type: "restrict",
          accessToken: authority.access_token,
        }),
      );
      return;
    }

    const identityResult = await readCurrentUser({
      auth: authority.access_token,
    });
    if (activeOperation.current !== operation) {
      return;
    }
    if (identityResult.data === undefined) {
      setState((current) => transitionSession(current, { type: "sign_out" }));
      return;
    }
    setState((current) =>
      transitionSession(current, {
        type: "authenticate",
        accessToken: authority.access_token,
        principal: identityResult.data,
      }),
    );
  }

  async function changePassword(passwords: PasswordChange) {
    if (
      state.status !== "password_change_required" &&
      state.status !== "authenticated"
    ) {
      return;
    }
    const accessToken = state.accessToken;
    const operation = Symbol();
    activeOperation.current = operation;
    const result = await generatedChangePassword({
      auth: accessToken,
      body: {
        current_password: passwords.currentPassword,
        new_password: passwords.newPassword,
      },
    });
    if (activeOperation.current !== operation) {
      return;
    }
    if (result.error !== undefined) {
      throw new Error("Session action failed");
    }
    setState((current) => transitionSession(current, { type: "sign_out" }));
  }

  async function restoreSession() {
    const operation = Symbol();
    activeOperation.current = operation;
    setState((current) =>
      transitionSession(current, { type: "check_session" }),
    );
    let refreshResult: Awaited<ReturnType<typeof refreshAccessToken>>;
    try {
      refreshResult = await refreshAccessToken();
    } catch {
      if (activeOperation.current === operation) {
        setState((current) => transitionSession(current, { type: "sign_out" }));
      }
      return;
    }
    if (activeOperation.current !== operation) {
      return;
    }
    const authority = refreshResult.data;
    if (authority === undefined || authority.must_change_password) {
      setState((current) => transitionSession(current, { type: "sign_out" }));
      return;
    }
    const identityResult = await readCurrentUser({
      auth: authority.access_token,
    });
    if (activeOperation.current !== operation) {
      return;
    }
    if (identityResult.data === undefined) {
      setState((current) => transitionSession(current, { type: "sign_out" }));
      return;
    }
    setState((current) =>
      transitionSession(current, {
        type: "authenticate",
        accessToken: authority.access_token,
        principal: identityResult.data,
      }),
    );
  }

  const restoreSessionRef = useRef(restoreSession);

  useEffect(() => {
    if (restoreOnMount) {
      void restoreSessionRef.current();
    }
  }, [restoreOnMount]);

  async function logout() {
    activeOperation.current = Symbol();
    setState((current) => transitionSession(current, { type: "sign_out" }));
    await generatedLogout();
  }

  const value: SessionValue = {
    state,
    login,
    changePassword,
    restoreSession,
    logout,
  };

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const session = useContext(SessionContext);
  if (session === null) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return session;
}
