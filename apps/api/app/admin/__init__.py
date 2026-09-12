"""Isolated super-admin subsystem.

Completely separate from regular user authentication: the super admin logs in
with env credentials (SUPER_ADMIN_USERNAME / SUPER_ADMIN_PASSWORD), receives a
JWT carrying a distinct ``admin`` scope, and every ``/api/admin/*`` route is
guarded by ``require_super_admin``.
"""
