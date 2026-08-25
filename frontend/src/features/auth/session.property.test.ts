import fc from "fast-check";
import { describe, expect, it } from "vitest";

import type { CurrentUserResponse, RoleName } from "../../api/client";
import {
  initialSessionState,
  transitionSession,
  type SessionEvent,
  type SessionState,
} from "./session";

const roles: RoleName[] = [
  "admin",
  "product_manager_reviewer",
  "translator",
  "viewer",
];

const principalArbitrary: fc.Arbitrary<CurrentUserResponse> = fc.record({
  id: fc.uuid(),
  email: fc.emailAddress(),
  display_name: fc.string({ minLength: 1, maxLength: 40 }),
  roles: fc.uniqueArray(fc.constantFrom(...roles), { maxLength: roles.length }),
  must_change_password: fc.boolean(),
});

const eventArbitrary: fc.Arbitrary<SessionEvent> = fc.oneof(
  fc.constant({ type: "check_session" as const }),
  fc.constant({ type: "sign_out" as const }),
  fc.record({
    type: fc.constant("restrict" as const),
    accessToken: fc.string({ maxLength: 40 }),
  }),
  fc.record({
    type: fc.constant("authenticate" as const),
    accessToken: fc.string({ maxLength: 40 }),
    principal: principalArbitrary,
  }),
);

function assertAuthorityInvariant(state: SessionState) {
  if (state.status === "authenticated") {
    expect(state.accessToken.length).toBeGreaterThan(0);
    expect(state.principal.must_change_password).toBe(false);
    return;
  }

  expect(state).not.toHaveProperty("principal");
  if (state.status === "password_change_required") {
    expect(state.accessToken.length).toBeGreaterThan(0);
  } else {
    expect(state).not.toHaveProperty("accessToken");
  }
}

describe("session state properties", () => {
  it("selects the exact initial state for automatic and manual restoration", () => {
    expect(initialSessionState(true)).toEqual({ status: "checking_session" });
    expect(initialSessionState(false)).toEqual({ status: "signed_out" });
  });

  it("fails closed for restricted and authenticated events without valid authority", () => {
    expect(
      transitionSession(
        { status: "checking_session" },
        { type: "restrict", accessToken: "" },
      ),
    ).toEqual({ status: "signed_out" });

    expect(
      transitionSession(
        { status: "checking_session" },
        {
          type: "authenticate",
          accessToken: "",
          principal: {
            id: "73f123f7-ebad-4dad-8b5d-dcc3214b3b06",
            email: "person@example.com",
            display_name: "Person",
            roles: ["translator"],
            must_change_password: false,
          },
        },
      ),
    ).toEqual({ status: "signed_out" });
  });

  it("preserves ordinary-token and no-principal invariants across event sequences", () => {
    fc.assert(
      fc.property(
        fc.array(eventArbitrary, { minLength: 1, maxLength: 100 }),
        (events) => {
          let state: SessionState = { status: "signed_out" };

          for (const event of events) {
            state = transitionSession(state, event);
            assertAuthorityInvariant(state);

            if (
              event.type === "authenticate" &&
              event.accessToken.length > 0 &&
              !event.principal.must_change_password
            ) {
              expect(state.status).toBe("authenticated");
            }
            if (event.type === "restrict" && event.accessToken.length > 0) {
              expect(state.status).toBe("password_change_required");
            }
          }
        },
      ),
      { numRuns: 250 },
    );
  });
});
