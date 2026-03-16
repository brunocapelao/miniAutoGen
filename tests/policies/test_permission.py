import pytest

from miniautogen.policies.permission import (
    PermissionDeniedError,
    PermissionPolicy,
    check_permission,
)


class TestPermissionPolicyDenyByDefault:
    def test_empty_allowed_actions_denies_by_default(self):
        policy = PermissionPolicy(allowed_actions=())
        with pytest.raises(PermissionDeniedError):
            check_permission(policy, "read")

    def test_allow_all_flag_permits_everything(self):
        policy = PermissionPolicy(allow_all=True)
        check_permission(policy, "read")
        check_permission(policy, "write")
        check_permission(policy, "delete")

    def test_allow_all_overrides_allowed_actions(self):
        policy = PermissionPolicy(allowed_actions=("read",), allow_all=True)
        check_permission(policy, "write")  # Allowed because allow_all=True


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
