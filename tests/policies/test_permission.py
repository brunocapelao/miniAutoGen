import pytest

from miniautogen.policies.permission import (
    PermissionDeniedError,
    PermissionPolicy,
    check_permission,
)


class TestPermissionPolicyPermissiveDefault:
    def test_empty_allowed_actions_permits_everything(self):
        policy = PermissionPolicy(allowed_actions=())
        check_permission(policy, "read")
        check_permission(policy, "write")
        check_permission(policy, "delete")


class TestPermissionPolicyRestricted:
    def test_allowed_action_passes(self):
        policy = PermissionPolicy(allowed_actions=("read", "write"))
        check_permission(policy, "read")
        check_permission(policy, "write")

    def test_denied_action_raises(self):
        policy = PermissionPolicy(allowed_actions=("read",))
        with pytest.raises(PermissionDeniedError, match="Action 'write' not permitted"):
            check_permission(policy, "write")

    def test_denied_action_shows_allowed(self):
        policy = PermissionPolicy(allowed_actions=("read", "list"))
        with pytest.raises(PermissionDeniedError, match="Allowed:"):
            check_permission(policy, "delete")
