from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILL_NAME = "api-migration"
_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "skills" / SKILL_NAME / "SKILL.md",
    Path(__file__).resolve().parent / "resources" / SKILL_NAME / "SKILL.md",
)


class SkillLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    license: str
    compatibility: str
    allowed_tools: str
    version: str
    body: str
    path: str
    digest: str

    def public_metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "compatibility": self.compatibility,
            "allowed_tools": self.allowed_tools,
            "version": self.version,
            "digest": self.digest,
            "used_by": ["Migration Strategist"],
            "source": self.path,
        }


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, str], dict[str, str], str]:
    if not text.startswith("---"):
        raise SkillLoadError("SKILL.md is missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise SkillLoadError("SKILL.md frontmatter is not closed")
    _, raw_frontmatter, body = parts
    fields: dict[str, str] = {}
    metadata: dict[str, str] = {}
    in_metadata = False
    for raw_line in raw_frontmatter.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")):
            if in_metadata and ":" in raw_line:
                key, value = raw_line.strip().split(":", 1)
                metadata[key.strip()] = _unquote(value)
            continue
        in_metadata = False
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if key == "metadata":
            in_metadata = True
            continue
        fields[key] = _unquote(value)
    return fields, metadata, body.strip()


def _load_from(path: Path) -> Skill:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillLoadError(f"Unable to read {path}: {exc}") from exc
    fields, metadata, body = _parse_frontmatter(text)
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name or not description:
        raise SkillLoadError("SKILL.md requires name and description")
    if not _NAME_PATTERN.fullmatch(name) or name != path.parent.name:
        raise SkillLoadError("SKILL.md name must be lowercase kebab-case and match its directory")
    if len(name) > 64:
        raise SkillLoadError("SKILL.md name exceeds 64 characters")
    if len(description) > 1024:
        raise SkillLoadError("SKILL.md description exceeds 1024 characters")
    compatibility = fields.get("compatibility", "")
    if len(compatibility) > 500:
        raise SkillLoadError("SKILL.md compatibility exceeds 500 characters")
    allowed_tools = fields.get("allowed-tools", "")
    if "\n" in allowed_tools or allowed_tools.lstrip().startswith("-"):
        raise SkillLoadError("SKILL.md allowed-tools must be a space-separated string")
    if not body:
        raise SkillLoadError("SKILL.md body is empty")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Skill(
        name=name,
        description=description,
        license=fields.get("license", "unspecified"),
        compatibility=compatibility,
        allowed_tools=allowed_tools,
        version=metadata.get("version", "unversioned"),
        body=body,
        path=f"skills/{SKILL_NAME}/SKILL.md",
        digest=f"sha256:{digest}",
    )


@lru_cache(maxsize=1)
def load_skill() -> Skill:
    for candidate in _CANDIDATES:
        if candidate.is_file():
            return _load_from(candidate)
    raise SkillLoadError("api-migration SKILL.md was not found")


def skill_guidance() -> str:
    return load_skill().body
