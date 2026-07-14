"""Tiny, dependency-free pagination used across every long-list view
(rankings, recruiting, all teams, …). Server-side slicing keeps pages light
and the URL shareable (?page=N preserves all other filters)."""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PER_PAGE = 50


@dataclass
class Page:
    items: list
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev(self) -> int:
        return self.page - 1

    @property
    def next(self) -> int:
        return self.page + 1

    @property
    def start(self) -> int:
        """1-based index of the first item shown (0 when empty)."""
        return 0 if self.total == 0 else (self.page - 1) * self.per_page + 1

    @property
    def end(self) -> int:
        return min(self.page * self.per_page, self.total)

    def window(self, span: int = 2) -> list[int | None]:
        """Page numbers to render, with None marking an ellipsis gap.
        Always shows first/last and `span` neighbours around the current page."""
        pages = self.pages
        if pages <= 1:
            return [1]
        keep = {1, pages, self.page}
        for d in range(1, span + 1):
            keep.add(self.page - d)
            keep.add(self.page + d)
        nums = sorted(n for n in keep if 1 <= n <= pages)
        out: list[int | None] = []
        prev = 0
        for n in nums:
            if n - prev > 1:
                out.append(None)        # ellipsis
            out.append(n)
            prev = n
        return out


def per_page_arg(raw, default: int = DEFAULT_PER_PAGE, *, max_per: int = 100_000) -> int:
    """Parse a ?per= page-size parameter: a positive int is that size (capped at
    `max_per`), 0 or 'all' means show everything, junk/missing falls back to the
    route's default. Pair with the pager macro's `sizes=` links."""
    if raw is None or str(raw).strip() == "":
        return default
    if str(raw).strip().lower() == "all":
        return max_per
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max_per if n <= 0 else min(n, max_per)


def paginate(items, page, per_page: int = DEFAULT_PER_PAGE) -> Page:
    """Slice `items` to `page` (1-based). Coerces junk input and clamps the page
    into range so a stale ?page= never 500s or shows a blank list."""
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    seq = list(items)
    total = len(seq)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    s = (page - 1) * per_page
    return Page(seq[s:s + per_page], page, per_page, total)
