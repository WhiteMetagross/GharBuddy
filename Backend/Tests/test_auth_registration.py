"""
Tests for proper auth flow — Registration, login, PBKDF2 hashing, and
input validation. Uses pure stdlib + Hypothesis for property tests.

Feature: proper-auth-flow
"""
import string
import unittest
from hypothesis import given, settings, strategies as st

import Backend.Services.AuthService as auth


class _AuthTestBase(unittest.TestCase):
    def setUp(self):
        # Reset the in-memory user store between tests so cases stay isolated.
        auth.REGISTERED_USERS.clear()


class TestPbkdf2RoundTrip(_AuthTestBase):
    """PBKDF2 hash should always verify the original password and reject others."""

    @given(st.text(min_size=1, max_size=64))
    @settings(max_examples=40, deadline=None)
    def test_hash_verifies(self, password):
        digest, salt_hex = auth._pbkdf2_hash(password)
        self.assertTrue(auth._pbkdf2_verify(password, digest, salt_hex))

    @given(
        st.text(min_size=1, max_size=32),
        st.text(min_size=1, max_size=32),
    )
    @settings(max_examples=40, deadline=None)
    def test_different_passwords_do_not_collide(self, a, b):
        if a == b:
            return
        digest, salt = auth._pbkdf2_hash(a)
        # Slim odds that PBKDF2 collides on a different password
        self.assertFalse(auth._pbkdf2_verify(b, digest, salt))

    def test_hash_uses_random_salt(self):
        h1, s1 = auth._pbkdf2_hash("samepassword")
        h2, s2 = auth._pbkdf2_hash("samepassword")
        self.assertNotEqual(s1, s2, "Each call must use a fresh random salt")
        self.assertNotEqual(h1, h2, "Different salts must produce different hashes")


class TestRegisterUser(_AuthTestBase):
    """Registration validation rules and round-trip with login."""

    def test_registers_and_logs_in(self):
        result = auth.registerUser("alice", "secret123", role="parent")
        self.assertEqual(result["username"], "alice")
        self.assertEqual(result["role"], "parent")
        self.assertTrue(result["token"])

        login = auth.loginUser("alice", "secret123")
        self.assertIsNotNone(login)
        self.assertEqual(login["username"], "alice")
        self.assertEqual(login["role"], "parent")

    def test_login_rejects_wrong_password(self):
        auth.registerUser("bob", "secret123", role="family")
        self.assertIsNone(auth.loginUser("bob", "WRONG"))

    def test_duplicate_username_raises(self):
        auth.registerUser("dup", "secret123", role="family")
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("dup", "anotherpw", role="family")

    def test_demo_username_is_reserved(self):
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("admin", "newpassword", role="parent")

    def test_short_password_rejected(self):
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("user1", "abc", role="family")

    def test_short_username_rejected(self):
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("ab", "secret123", role="family")

    def test_invalid_role_rejected(self):
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("user2", "secret123", role="superadmin")

    def test_invalid_username_chars_rejected(self):
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("bad name", "secret123", role="family")
        with self.assertRaises(auth.RegistrationError):
            auth.registerUser("nope!", "secret123", role="family")

    @given(
        st.text(
            alphabet=string.ascii_letters + string.digits + "_-.",
            min_size=3,
            max_size=32,
        ),
        st.text(min_size=6, max_size=64),
        st.sampled_from(auth.ALLOWED_ROLES),
    )
    @settings(max_examples=25, deadline=None)
    def test_round_trip_property(self, username, password, role):
        auth.REGISTERED_USERS.clear()
        if username in auth.DEMO_USERS:
            return  # skip names already taken by the demo store
        result = auth.registerUser(username, password, role=role)
        self.assertEqual(result["username"], username)
        self.assertEqual(result["role"], role)
        login = auth.loginUser(username, password)
        self.assertIsNotNone(login)
        self.assertEqual(login["username"], username)
        self.assertEqual(login["role"], role)


class TestLoginPriority(_AuthTestBase):
    """A registered user should take precedence over a same-name demo entry."""

    def test_demo_user_still_works_when_no_registration(self):
        login = auth.loginUser("admin", "gharbuddy123")
        self.assertIsNotNone(login)
        self.assertEqual(login["username"], "admin")

    def test_password_hashing_does_not_store_plaintext(self):
        auth.registerUser("paranoid", "topsecret123", role="parent")
        record = auth.REGISTERED_USERS["paranoid"]
        self.assertNotIn("topsecret123", record["password_hash"])
        self.assertNotEqual(record["password_hash"], "topsecret123")
        self.assertTrue(len(record["password_hash"]) >= 32)


if __name__ == "__main__":
    unittest.main()
