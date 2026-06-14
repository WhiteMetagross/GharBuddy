/**
 * Pure validation helpers for Login / Sign Up form. Mirrors the backend
 * registration rules in Backend/Services/AuthService.py so the user gets
 * synchronous feedback before round-tripping to the API.
 */

export const USERNAME_RE = /^[a-zA-Z0-9_.-]{3,32}$/;

export const ROLE_OPTIONS = [
  { id: "parent", label: "Parent",  hint: "Full control of devices" },
  { id: "family", label: "Family",  hint: "Day-to-day household use" },
  { id: "child",  label: "Child",   hint: "Limited, age-appropriate" },
];

export function validateAuthForm(form, mode) {
  const errors = {};
  const username = (form?.username || "").trim();
  const password = form?.password || "";

  if (!username || !USERNAME_RE.test(username)) {
    errors.username = "3–32 chars, letters/digits/_-. only";
  }
  if (!password || password.length < 6) {
    errors.password = "At least 6 characters";
  }
  if (mode === "signup") {
    if (password !== (form?.confirm || "")) {
      errors.confirm = "Passwords don't match";
    }
    if (!ROLE_OPTIONS.some((r) => r.id === form?.role)) {
      errors.role = "Pick a role";
    }
  }
  return errors;
}
