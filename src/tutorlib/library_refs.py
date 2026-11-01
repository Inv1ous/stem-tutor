"""Translate asset references in runtime copies and rendered Markdown.

Published packs and events remain immutable. Old vaults without a catalog retain
their existing paths. Once a catalog exists, a missing or corrupt asset is an
explicit error; the resolver never falls back to an old directory.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from .asset_library import AssetLibrary


ASSET_FIELDS = {"image", "images", "diagram", "diagrams", "pdf", "file", "path", "qp", "ms", "er", "gt", "ci", "source"}
PROTECTED_FIELDS = {"id", "ref", "answer", "answers", "scheme", "rubric", "options", "params", "template"}
ASSET_PREFIXES = ("asset:", "Library/", "Assets/", "assets/", "Papers/", "sources/", "Sources/",
                  "build/out/assets/", "build/out/Assets/",
                  "stem-tutor/build/out/assets/", "stem-tutor/build/out/Assets/")
ASSET_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".pdf", ".wav", ".mp3", ".m4a"}
# Code spans are literal examples, not rendered links. Preserve them verbatim.
MARKDOWN_TARGET = re.compile(
    r"(?P<code>```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)"
    r"|(?P<wiki>!?\[\[(?P<wiki_target>[^\]\n]+)\]\])"
    r"|(?P<link>!?\[[^\]\n]*\]\((?P<link_target><[^>\n]+>|[^)\s]+)(?:\s+\"[^\"\n]*\")?\))"
)


def normalize_asset_reference(value: str) -> str:
    """Remove only the historical repository adapter prefix before catalog lookup.

    The resulting alias still needs explicit registration and digest checking;
    this never searches the build tree or guesses a resource by filename.
    """
    return value.removeprefix("stem-tutor/") if value.startswith(
        ("stem-tutor/build/out/assets/", "stem-tutor/build/out/Assets/")) else value


def is_asset_reference(value: str) -> bool:
    """Distinguish unresolved local asset paths from citations and origin prose.

    Exact declared aliases take precedence over this classification. Spaces
    inside an explicit Library/Assets path do not make a missing file optional.
    """
    citation = (";" in value or "\n" in value
                or re.search(r"\.(?:pdf|svg|png|jpe?g|webp)[,\s]+(?:PDF\s+)?(?:p|pp)\.", value, re.I))
    return "://" not in value and not citation and (value.startswith(ASSET_PREFIXES)
        or (not any(char.isspace() for char in value)
            and Path(value).suffix.lower() in ASSET_SUFFIXES))


@lru_cache(maxsize=8)
def _catalog(root: str, signature: tuple) -> AssetLibrary:
    return AssetLibrary(Path(root))


class LibraryRefs:
    """One catalog reader for runtime asset fields and Markdown link targets."""

    def __init__(self, vault_root: Path | str):
        self.root = Path(vault_root).resolve()
        catalog = self.root / "Library/catalog.json"
        self.library = None
        if catalog.exists() or catalog.is_symlink():
            if catalog.is_symlink() or catalog.parent.is_symlink():
                raise ValueError("asset catalog must not use symlinks")
            info = catalog.stat()
            signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            self.library = _catalog(str(self.root), signature)

    def reference(self, value: str) -> str:
        """Resolve an exact catalog reference; leave other non-asset text alone."""
        if self.library is None or "://" in value:
            return value
        try:
            # Historical packs used the repository prefix for declared build
            # aliases. Strip only that exact adapter prefix and still require
            # catalog verification; never read the build tree at runtime.
            reference = normalize_asset_reference(value)
            path = self.library.resolve(reference)
        except ValueError as exc:
            # Source fields also contain citations such as "Registered Library
            # asset; origin ...svg" and "Library/...pdf p.12; syllabus ...".
            # Exact aliases were tried above; prose must remain byte-for-byte.
            if not is_asset_reference(value) and (str(exc).startswith("unknown asset reference:")
                                   or str(exc) == "invalid vault-relative asset path"):
                return value
            raise
        return path.relative_to(self.root).as_posix()

    def content(self, value, *, asset_field: bool = False):
        """Copy structured content, changing only explicit asset fields.

        Identity, source citations, answers, marking schemes, and formula/template
        values never change, even if a string happens to equal a catalog alias.
        """
        # A load is one verified snapshot. Shared PDFs can occur in hundreds of
        # questions; verify each reference once here, never cache across loads.
        references = {}

        def rewrite(child, asset_field=False):
            if isinstance(child, dict):
                mapped = {key: self._copy(item) if key in PROTECTED_FIELDS else
                          rewrite(item, asset_field=key in ASSET_FIELDS)
                          for key, item in child.items()}
                # Bind descriptions before aliases change the declared paths.
                # Positional bindings also preserve distinct descriptions when
                # two declared references resolve to the same canonical image.
                if (isinstance(child.get('diagram_descriptions'), dict)
                        and mapped.get('diagrams') != child.get('diagrams')):
                    from .card_diagrams import diagram_descriptions, valid_diagram_descriptions
                    if valid_diagram_descriptions(child):
                        mapped['diagram_descriptions'] = diagram_descriptions(child)
                return mapped
            if isinstance(child, list):
                return [rewrite(item, asset_field=asset_field) for item in child]
            if asset_field and isinstance(child, str):
                if child not in references:
                    references[child] = self.reference(child)
                return references[child]
            return child

        return rewrite(value, asset_field=asset_field)

    @staticmethod
    def _copy(value):
        if isinstance(value, dict):
            return {key: LibraryRefs._copy(child) for key, child in value.items()}
        if isinstance(value, list):
            return [LibraryRefs._copy(child) for child in value]
        return value

    def markdown(self, text: str) -> str:
        """Rewrite link destinations only, preserving prose, labels, and sizes."""
        if self.library is None:
            return text

        def replace(match):
            if match.group("code"):
                return match.group(0)
            if (target := match.group("wiki_target")) is not None:
                path = re.split(r"\\?\||#", target, maxsplit=1)[0]
                if not path:
                    return match.group(0)
                canonical = self._wiki_reference(path)
                updated = canonical + target[len(path):]
                return match.group(0).replace(target, updated, 1)
            target = match.group("link_target")
            enclosed = target.startswith("<")
            path = target[1:-1] if enclosed else target
            base, marker, fragment = path.partition("#")
            canonical = self.reference(base) + marker + fragment
            replacement = f"<{canonical}>" if enclosed else canonical
            start = match.start("link_target") - match.start()
            end = match.end("link_target") - match.start()
            return match.group(0)[:start] + replacement + match.group(0)[end:]

        return MARKDOWN_TARGET.sub(replace, text)

    def _wiki_reference(self, path: str) -> str:
        """Obsidian permits note links without .md; resolve only declared resources."""
        unknown = None
        try:
            canonical = self.reference(path)
        except ValueError as exc:
            if not str(exc).startswith("unknown asset reference:"):
                raise
            unknown = exc
            canonical = path
        if canonical == path and Path(path).suffix.lower() not in ASSET_SUFFIXES | {".md"}:
            try:
                note = self.library.resolve(path + ".md")
            except ValueError as exc:
                if not (str(exc).startswith("unknown asset reference:")
                        or str(exc) == "invalid vault-relative asset path"):
                    raise
            else:
                return note.relative_to(self.root).as_posix().removesuffix(".md")
        if unknown is not None:
            raise unknown
        return canonical
