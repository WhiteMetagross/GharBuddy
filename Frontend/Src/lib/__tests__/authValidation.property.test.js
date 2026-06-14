import { describe, it, expect } from "vitest";
import fc from "fast-check";
import {
  validateAuthForm,
  USERNAME_RE,
  ROLE_OPTIONS,
} from "../authValidation.js";

// Mirror of the backend regex — anything outside [a-zA-Z0-9_.-]{3,32} is invalid.
const VALID_USERNAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.";

const validUsernameArb = fc
  .string({ minLength: 3, maxLength: 32 })
  .filter((s) => USERNAME_RE.test(s));

const validPasswordArb = fc.string({ minLength: 6, maxLength: 64 });
const roleArb = fc.constantFrom(...ROLE_OPTIONS.map((r) => r.id));

describe("validateAuthForm — sign in mode", () => {
  it("accepts well-formed credentials with no errors", () => {
    fc.assert(
      fc.property(validUsernameArb, validPasswordArb, (username, password) => {
        const errors = validateAuthForm({ username, password }, "signin");
        expect(errors.username).toBeUndefined();
        expect(errors.password).toBeUndefined();
      }),
      { numRuns: 50 },
    );
  });

  it("rejects passwords shorter than 6 characters", () => {
    fc.assert(
      fc.property(
        validUsernameArb,
        fc.string({ minLength: 0, maxLength: 5 }),
        (username, password) => {
          const errors = validateAuthForm({ username, password }, "signin");
          expect(errors.password).toBeDefined();
        },
      ),
      { numRuns: 30 },
    );
  });

  it("rejects usernames containing disallowed characters", () => {
    const disallowedAlphabet = " !@#$%^&*()+=[]{}|;:'\",<>/?\\";
    fc.assert(
      fc.property(
        fc.string({
          minLength: 1,
          maxLength: 8,
          unit: fc.constantFrom(...disallowedAlphabet.split("")),
        }),
        fc.string({ minLength: 0, maxLength: 4 }),
        validPasswordArb,
        (badPart, prefix, password) => {
          const username = `${prefix}${badPart}`;
          const errors = validateAuthForm({ username, password }, "signin");
          expect(errors.username).toBeDefined();
        },
      ),
      { numRuns: 30 },
    );
  });

  it("does not check confirm or role outside signup mode", () => {
    const errors = validateAuthForm(
      { username: "alice", password: "abcdef" },
      "signin",
    );
    expect(errors.confirm).toBeUndefined();
    expect(errors.role).toBeUndefined();
  });
});

describe("validateAuthForm — sign up mode", () => {
  it("requires confirm password to match", () => {
    fc.assert(
      fc.property(
        validUsernameArb,
        validPasswordArb,
        validPasswordArb,
        roleArb,
        (username, password, confirm, role) => {
          const errors = validateAuthForm(
            { username, password, confirm, role },
            "signup",
          );
          if (password !== confirm) {
            expect(errors.confirm).toBeDefined();
          } else {
            expect(errors.confirm).toBeUndefined();
          }
        },
      ),
      { numRuns: 40 },
    );
  });

  it("requires a known role", () => {
    fc.assert(
      fc.property(
        validUsernameArb,
        validPasswordArb,
        fc.string().filter((s) => !ROLE_OPTIONS.some((r) => r.id === s)),
        (username, password, badRole) => {
          const errors = validateAuthForm(
            { username, password, confirm: password, role: badRole },
            "signup",
          );
          expect(errors.role).toBeDefined();
        },
      ),
      { numRuns: 30 },
    );
  });

  it("returns no errors for a fully valid signup payload", () => {
    fc.assert(
      fc.property(
        validUsernameArb,
        validPasswordArb,
        roleArb,
        (username, password, role) => {
          const errors = validateAuthForm(
            { username, password, confirm: password, role },
            "signup",
          );
          expect(Object.keys(errors)).toHaveLength(0);
        },
      ),
      { numRuns: 50 },
    );
  });
});

describe("validateAuthForm — defensive parsing", () => {
  it("treats undefined form fields as missing without crashing", () => {
    const errors = validateAuthForm({}, "signup");
    expect(errors.username).toBeDefined();
    expect(errors.password).toBeDefined();
  });

  it("trims whitespace around usernames", () => {
    const errors = validateAuthForm(
      { username: "  alice  ", password: "abcdef" },
      "signin",
    );
    expect(errors.username).toBeUndefined();
  });
});
