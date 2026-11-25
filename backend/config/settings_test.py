"""Settings used by ``manage.py test``.

Password hashing is the dominant cost when creating test users, so tests use
the fast MD5 hasher. Production keeps the default PBKDF2 hasher.
"""
from config.settings import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
