from __future__ import annotations

import copy
from typing import Any

from ..analysis.differ import escape_pointer
from ..models import CompatibilityPatch, Finding
from ..analysis.loader import LoadedSpec


def _set_pointer(document: dict[str, Any], pointer: str, value: Any, *, extend_list: bool = False) -> bool:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    if not parts:
        return False
    current: Any = document
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return False
        else:
            return False
    last = parts[-1]
    if isinstance(current, dict):
        current[last] = copy.deepcopy(value)
        return True
    if isinstance(current, list):
        if extend_list:
            current.append(copy.deepcopy(value))
            return True
        try:
            current[int(last)] = copy.deepcopy(value)
            return True
        except (ValueError, IndexError):
            return False
    return False


def _remove_required(document: dict[str, Any], pointer: str, name: str) -> bool:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    current: Any = document
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return False
        else:
            return False
    if not isinstance(current, dict):
        return False
    required = current.get("required")
    if isinstance(required, list) and name in required:
        current["required"] = [item for item in required if item != name]
        return True
    return False


def build_compatibility_patch(
    old: LoadedSpec, new: LoadedSpec, findings: list[Finding]
) -> tuple[dict[str, Any], CompatibilityPatch]:
    patched = copy.deepcopy(new.raw)
    changes: list[str] = []
    unpatchable: list[str] = []

    old_components = old.raw.get("components") if isinstance(old.raw.get("components"), dict) else {}
    new_components = patched.setdefault("components", {})
    for group in ("schemas", "responses", "parameters", "securitySchemes"):
        old_group = old_components.get(group) if isinstance(old_components.get(group), dict) else {}
        target = new_components.setdefault(group, {})
        if not isinstance(target, dict):
            continue
        for name, value in old_group.items():
            if name not in target:
                target[name] = copy.deepcopy(value)

    for finding in findings:
        if not finding.breaking:
            continue
        rule = finding.rule
        if rule == "endpoint.removed" and finding.path and finding.method:
            path_item = patched.setdefault("paths", {}).setdefault(finding.path, {})
            old_path_item = (old.raw.get("paths") or {}).get(finding.path) or {}
            old_operation = old_path_item.get(finding.method.lower())
            if isinstance(old_operation, dict):
                restored = copy.deepcopy(old_operation)
                if "security" not in restored:
                    old_view = old.operations.get(f"{finding.method} {finding.path}")
                    if old_view is not None and old_view.security:
                        restored["security"] = copy.deepcopy(old_view.security)
                path_item[finding.method.lower()] = restored
                path_item.setdefault("parameters", copy.deepcopy(old_path_item.get("parameters", [])))
                changes.append(f"Restored deprecated alias {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not restore {finding.method} {finding.path}")
        elif rule in {"parameter.required_added", "parameter.required_changed"} and finding.schema_pointer:
            if _set_pointer(patched, f"{finding.schema_pointer}/required", False):
                changes.append(f"Relaxed required parameter '{finding.parameter}' on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not relax parameter '{finding.parameter}' on {finding.method} {finding.path}")
        elif rule == "parameter.removed" and finding.method and finding.path and finding.old_fragment:
            operation = (
                patched.get("paths", {}).get(finding.path, {}).get(finding.method.lower())
            )
            if isinstance(operation, dict):
                params = operation.setdefault("parameters", [])
                if isinstance(params, list):
                    params.append(copy.deepcopy(finding.old_fragment))
                    changes.append(f"Restored parameter '{finding.parameter}' on {finding.method} {finding.path}")
                else:
                    unpatchable.append(f"Could not restore parameter '{finding.parameter}'")
            else:
                unpatchable.append(f"Could not restore parameter '{finding.parameter}'")
        elif rule in {"request.body.required_added", "request.body.required_changed"} and finding.schema_pointer:
            if _set_pointer(patched, f"{finding.schema_pointer}/required", False):
                changes.append(f"Made request body optional on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not make request body optional on {finding.method} {finding.path}")
        elif rule == "response.code.removed" and finding.method and finding.path and finding.parameter:
            old_path_item = (old.raw.get("paths") or {}).get(finding.path) or {}
            old_operation = old_path_item.get(finding.method.lower()) or {}
            old_response = (old_operation.get("responses") or {}).get(finding.parameter)
            operation = (
                patched.get("paths", {}).get(finding.path, {}).get(finding.method.lower())
            )
            if isinstance(operation, dict) and old_response is not None:
                operation.setdefault("responses", {})[finding.parameter] = copy.deepcopy(old_response)
                changes.append(f"Restored response {finding.parameter} on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not restore response {finding.parameter}")
        elif rule == "response.property_removed" and finding.schema_pointer and finding.parameter and finding.old_fragment is not None:
            if _set_pointer(
                patched,
                f"{finding.schema_pointer}/{escape_pointer(finding.parameter)}",
                finding.old_fragment,
            ):
                changes.append(f"Restored response field '{finding.parameter}' on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not restore response field '{finding.parameter}'")
        elif rule == "request.property_removed" and finding.schema_pointer and finding.parameter and finding.old_fragment is not None:
            if _set_pointer(
                patched,
                f"{finding.schema_pointer}/{escape_pointer(finding.parameter)}",
                finding.old_fragment,
            ):
                changes.append(f"Restored request field '{finding.parameter}' on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not restore request field '{finding.parameter}'")
        elif rule in {"request.property_required_added", "request.property_required_changed"} and finding.schema_pointer and finding.parameter:
            required_owner = finding.schema_pointer.rsplit("/properties", 1)[0]
            if _remove_required(patched, required_owner, finding.parameter):
                changes.append(f"Relaxed required request field '{finding.parameter}' on {finding.method} {finding.path}")
            else:
                unpatchable.append(
                    f"Required request field '{finding.parameter}' needs a consumer code change"
                )
        elif rule == "response.property_required_added" and finding.schema_pointer and finding.parameter:
            required_owner = finding.schema_pointer.rsplit("/properties", 1)[0]
            if _remove_required(patched, required_owner, finding.parameter):
                changes.append(f"Relaxed required response field '{finding.parameter}' on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"Could not relax response field '{finding.parameter}'")
        elif rule in {"request.type_changed", "response.type_changed"}:
            unpatchable.append(
                f"{finding.title} at {finding.location} requires a consumer or mapping-layer change"
            )
        elif rule == "security.requirements_changed":
            unpatchable.append("Authentication change requires coordinated credential migration")
        elif rule == "servers.changed":
            unpatchable.append("Base URL change requires consumer configuration updates")
        elif rule.endswith("required_added"):
            required_owner = (finding.schema_pointer or "").rsplit("/properties", 1)[0]
            if finding.schema_pointer and finding.parameter and _remove_required(
                patched, required_owner, finding.parameter
            ):
                changes.append(f"Relaxed required field '{finding.parameter}' on {finding.method} {finding.path}")
            else:
                unpatchable.append(f"{finding.title} requires a contract owner decision")
        elif finding.breaking:
            unpatchable.append(f"{finding.title} at {finding.location} is not auto-patchable")

    description = (
        "A simulated, best-effort compatibility shim was applied to a copy of the new contract. "
        "It restores routes/fields and relaxes additive requirements. Semantic type changes and auth "
        "changes are intentionally not auto-fixed. The original contract was not modified."
        if changes
        else "No safe compatibility shim could be generated for the remaining breaking changes."
    )
    return patched, CompatibilityPatch(
        applied=True,
        description=description,
        changes=changes,
        remaining_unpatchable=sorted(set(unpatchable)),
    )
