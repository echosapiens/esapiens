"""
Skill Loader — Dynamically loads bioSkills SKILL.md files on demand.

Simplified port from Sprint-1. Provides caching and context building
for injecting skill patterns into the LLM prompt.
"""

import os
import threading
from pathlib import Path
from typing import Optional


class SkillLoader:
    """Loads bioSkills SKILL.md files dynamically based on query intent."""

    def __init__(self, base_path: Path):
        self._base_path = base_path
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()

    def load_skill(self, skill_path: str, use_cache: bool = True) -> Optional[str]:
        """Load a single SKILL.md file."""
        cache_key = skill_path

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        skill_file = self._base_path / skill_path / "SKILL.md"
        if not skill_file.exists():
            print(f"[SkillLoader] Skill not found: {skill_path}")
            return None

        try:
            content = skill_file.read_text(encoding="utf-8")
            with self._lock:
                self._cache[cache_key] = content
            return content
        except Exception as e:
            print(f"[SkillLoader] Error loading skill {skill_path}: {e}")
            return None

    def load_skills(self, skill_paths: list[str], use_cache: bool = True) -> dict[str, str]:
        """Load multiple skills at once. Returns dict of path→content."""
        results = {}
        for sp in skill_paths:
            content = self.load_skill(sp, use_cache)
            if content:
                results[sp] = content
        return results

    def clear_cache(self):
        with self._lock:
            self._cache.clear()


class SkillContextBuilder:
    """Builds context strings from loaded skills for LLM prompt injection."""

    def __init__(self, loader: SkillLoader):
        self._loader = loader

    def build_context(
        self,
        skill_paths: list[str],
        include_header: bool = True,
        max_length: int = 8000,
    ) -> str:
        """Build a formatted context string from matched skills."""
        skills_content = self._loader.load_skills(skill_paths)
        if not skills_content:
            return ""

        sections: list[str] = []
        total = 0
        for path, content in skills_content.items():
            section = f"\n\n## Skill: {path}\n\n{content}" if include_header else content
            if total + len(section) > max_length:
                remaining = max_length - total - 50
                if remaining > 0:
                    section = section[:remaining] + "\n\n[... truncated ...]"
                else:
                    break
            sections.append(section)
            total += len(section)

        return "\n".join(sections)


# Global singleton
_loader: Optional[SkillLoader] = None


def get_skill_loader(base_path: Optional[Path] = None) -> SkillLoader:
    """Get or create the global SkillLoader instance."""
    global _loader
    if _loader is None:
        if base_path is None:
            base_path = Path(__file__).parent.parent / "bioSkills"
        _loader = SkillLoader(base_path)
    return _loader


def load_skills_for_intent(skill_paths: list[str]) -> dict[str, str]:
    """Convenience: load skills for a given set of paths."""
    return get_skill_loader().load_skills(skill_paths)