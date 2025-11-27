import re
from typing import Pattern


DEFAULT_IGNORED_PATHS = {
    "/.git/config",
    "/.git/HEAD",
    "/robots.txt",
    "/favicon.ico",
    "/ads.txt",
    "/.env",
    "/.env.local",
    "/.env.production",
    "/sitemap.xml",
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
}

DEFAULT_IGNORED_PREFIXES = [
    "/.git/",
    "/.well-known/",
    "/wp-admin/",
    "/wp-content/",
    "/wp-includes/",
    "/admin/",
    "/.aws/",
    "/.ssh/",
]

DEFAULT_IGNORED_EXTENSIONS = {
    ".php",
    ".asp",
    ".aspx",
    ".jsp",
    ".cgi",
}


class URLProcessor:
    def __init__(
        self,
        normalize_paths: bool = True,
        filter_ignored_paths: bool = True,
        custom_ignored_paths: list[str] | None = None,
        custom_ignored_prefixes: list[str] | None = None,
        custom_ignored_extensions: list[str] | None = None,
        normalization_patterns: list[tuple[Pattern, str]] | None = None,
        template_style: str = "curly",
    ):
        self.normalize_paths = normalize_paths
        self.filter_ignored_paths = filter_ignored_paths
        self.template_style = template_style

        self.ignored_paths = set(DEFAULT_IGNORED_PATHS)
        if custom_ignored_paths:
            self.ignored_paths.update(custom_ignored_paths)

        self.ignored_prefixes = list(DEFAULT_IGNORED_PREFIXES)
        if custom_ignored_prefixes:
            self.ignored_prefixes.extend(custom_ignored_prefixes)

        self.ignored_extensions = set(DEFAULT_IGNORED_EXTENSIONS)
        if custom_ignored_extensions:
            self.ignored_extensions.update(custom_ignored_extensions)

        if normalization_patterns:
            self.normalization_patterns = normalization_patterns
        else:
            self.normalization_patterns = self._build_default_patterns()

    def _build_default_patterns(self) -> list[tuple[Pattern, str]]:
        template = "{id}" if self.template_style == "curly" else ":id"

        patterns = [
            (re.compile(r"/\d+(?=/|$)"), f"/{template}"),
            (re.compile(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=/|$)", re.IGNORECASE), f"/{template}"),
            (re.compile(r"/[0-9a-f]{24}(?=/|$)", re.IGNORECASE), f"/{template}"),
            (re.compile(r"/[a-z0-9_-]{20,}(?=/|$)", re.IGNORECASE), f"/{template}"),
        ]

        return patterns

    def should_ignore_path(self, path: str) -> bool:
        if not self.filter_ignored_paths:
            return False

        if path in self.ignored_paths:
            return True

        for prefix in self.ignored_prefixes:
            if path.startswith(prefix):
                return True

        return any(path.endswith(extension) for extension in self.ignored_extensions)

    def normalize_path(self, path: str) -> str:
        if not self.normalize_paths:
            return path

        normalized = path
        for pattern, replacement in self.normalization_patterns:
            normalized = pattern.sub(replacement, normalized)

        return normalized

    def process_url(self, path: str) -> str | None:
        if self.should_ignore_path(path):
            return None

        return self.normalize_path(path)
