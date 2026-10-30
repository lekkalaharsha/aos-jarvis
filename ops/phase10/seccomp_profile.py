"""Fail-closed P10-R1 seccomp profile transformation."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


CHROOT_RULE = {
    "names": ["chroot"],
    "action": "SCMP_ACT_ALLOW",
    "args": [],
    "comment": "",
    "includes": {},
    "excludes": {},
}

_TOP_LEVEL_FIELDS = {"defaultAction", "defaultErrnoRet", "defaultErrno", "archMap", "syscalls"}
_RULE_FIELDS = {"names", "action", "args", "comment", "includes", "excludes", "errnoRet", "errno"}
_ACTIONS = {"SCMP_ACT_ALLOW", "SCMP_ACT_ERRNO"}
_ARG_FIELDS = {"index", "value", "valueTwo", "op"}
_ARG_OPS = {"SCMP_CMP_EQ", "SCMP_CMP_NE"}
_ARCHES = {"amd64", "arm", "arm64", "ppc64le", "riscv64", "s390", "s390x", "x32", "x86"}
_CAPS = {
    "CAP_AUDIT_WRITE", "CAP_BPF", "CAP_DAC_READ_SEARCH", "CAP_PERFMON",
    "CAP_SYS_ADMIN", "CAP_SYS_CHROOT", "CAP_SYS_MODULE", "CAP_SYS_PACCT",
    "CAP_SYS_PTRACE", "CAP_SYS_RAWIO", "CAP_SYS_TIME", "CAP_SYS_TTY_CONFIG",
}


class SeccompProfileError(ValueError):
    """The base profile cannot be proven safe to transform."""


def _fail(message: str) -> None:
    raise SeccompProfileError(message)


def _valid_string_list(value: Any, *, allowed: set[str] | None = None) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item and (allowed is None or item in allowed) for item in value)
        and len(value) == len(set(value))
    )


def _validate_condition(value: Any, *, allowed_keys: set[str]) -> None:
    if not isinstance(value, dict) or set(value) - allowed_keys:
        _fail("base profile has malformed syscall conditions")
    for key, allowed in (("arches", _ARCHES), ("caps", _CAPS)):
        if key in value and not _valid_string_list(value[key], allowed=allowed):
            _fail("base profile has malformed syscall conditions")


def _validate_args(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        _fail("base profile has malformed syscall arguments")
    for arg in value:
        if (
            not isinstance(arg, dict)
            or set(arg) != _ARG_FIELDS
            or not isinstance(arg["index"], int)
            or isinstance(arg["index"], bool)
            or arg["index"] < 0
            or not isinstance(arg["value"], int)
            or isinstance(arg["value"], bool)
            or not isinstance(arg["valueTwo"], int)
            or isinstance(arg["valueTwo"], bool)
            or arg["op"] not in _ARG_OPS
        ):
            _fail("base profile has malformed syscall arguments")


def _validate_rule(rule: Any) -> None:
    if not isinstance(rule, dict) or set(rule) - _RULE_FIELDS:
        _fail("base profile contains a malformed syscall rule")
    if not _valid_string_list(rule.get("names")):
        _fail("base profile contains malformed syscall names")
    if rule.get("action") not in _ACTIONS:
        _fail("base profile contains an unknown or missing syscall action")
    _validate_args(rule.get("args"))
    if not isinstance(rule.get("comment"), str):
        _fail("base profile contains a malformed syscall comment")
    _validate_condition(rule.get("includes"), allowed_keys={"arches", "caps"})
    _validate_condition(rule.get("excludes"), allowed_keys={"caps"})
    has_errno = "errnoRet" in rule or "errno" in rule
    if has_errno and (
        rule.get("action") != "SCMP_ACT_ERRNO"
        or not isinstance(rule.get("errnoRet"), int)
        or isinstance(rule.get("errnoRet"), bool)
        or rule["errnoRet"] < 0
        or not isinstance(rule.get("errno"), str)
        or not rule["errno"]
    ):
        _fail("base profile contains malformed errno fields")


def _validate_profile(profile: Any) -> None:
    if not isinstance(profile, dict) or set(profile) != _TOP_LEVEL_FIELDS:
        _fail("base profile has an unexpected top-level structure")
    if profile["defaultAction"] != "SCMP_ACT_ERRNO":
        _fail("base profile has an unexpected defaultAction")
    if not isinstance(profile["defaultErrnoRet"], int) or isinstance(profile["defaultErrnoRet"], bool):
        _fail("base profile has malformed defaultErrnoRet")
    if not isinstance(profile["defaultErrno"], str) or not profile["defaultErrno"]:
        _fail("base profile has malformed defaultErrno")
    if not isinstance(profile["archMap"], list) or not profile["archMap"]:
        _fail("base profile has malformed archMap")
    for arch in profile["archMap"]:
        if (
            not isinstance(arch, dict)
            or set(arch) != {"architecture", "subArchitectures"}
            or not isinstance(arch["architecture"], str)
            or not arch["architecture"]
            or not _valid_string_list(arch["subArchitectures"])
        ):
            _fail("base profile has malformed archMap")
    if not isinstance(profile["syscalls"], list) or not profile["syscalls"]:
        _fail("base profile has no valid syscall-rule list")
    for rule in profile["syscalls"]:
        _validate_rule(rule)


def transform_chroot_rule(profile: dict[str, Any]) -> dict[str, Any]:
    """Replace every base-profile ``chroot`` entry with one exact allow rule.

    Only ``chroot`` is removed from matched rules. All other names and every
    other rule property are retained byte-for-byte in the structured object.
    """
    _validate_profile(profile)
    rules = profile["syscalls"]

    transformed: list[dict[str, Any]] = []
    found = 0
    for rule in rules:
        names = rule["names"]
        if "chroot" not in names:
            transformed.append(deepcopy(rule))
            continue
        found += 1
        if rule.get("action") == "SCMP_ACT_ALLOW" and not rule.get("includes") and not rule.get("excludes"):
            raise SeccompProfileError("base profile unexpectedly already allows chroot unconditionally")
        preserved = deepcopy(rule)
        preserved["names"] = [name for name in names if name != "chroot"]
        if preserved["names"]:
            transformed.append(preserved)

    if not found:
        raise SeccompProfileError("base profile contains no chroot rule")

    result = deepcopy(profile)
    result["syscalls"] = [*transformed, deepcopy(CHROOT_RULE)]
    validate_chroot_transformation(profile, result)
    return result


def validate_chroot_transformation(source: dict[str, Any], transformed: dict[str, Any]) -> None:
    """Prove the transformation changed only ``chroot`` handling."""
    _validate_profile(source)
    _validate_profile(transformed)
    if source.get("defaultAction") != transformed.get("defaultAction"):
        raise SeccompProfileError("seccomp defaultAction changed")
    source_rules = source.get("syscalls")
    result_rules = transformed.get("syscalls")
    if not isinstance(source_rules, list) or not isinstance(result_rules, list):
        raise SeccompProfileError("profile syscall-rule list is malformed")

    expected_other_rules: list[dict[str, Any]] = []
    for rule in source_rules:
        if "chroot" not in rule["names"]:
            expected_other_rules.append(rule)
            continue
        preserved = deepcopy(rule)
        preserved["names"] = [name for name in rule["names"] if name != "chroot"]
        if preserved["names"]:
            expected_other_rules.append(preserved)

    chroot_rules = [rule for rule in result_rules if "chroot" in rule["names"]]
    if chroot_rules != [CHROOT_RULE]:
        raise SeccompProfileError("generated profile does not contain exactly one unconditional chroot allow rule")
    other_rules = [rule for rule in result_rules if rule is not chroot_rules[0]]
    if other_rules != expected_other_rules:
        raise SeccompProfileError("generated profile changed an unrelated syscall rule")
