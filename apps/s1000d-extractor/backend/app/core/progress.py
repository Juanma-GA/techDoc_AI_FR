"""Progress checkpoints with bounded percentage notifications."""

from collections.abc import Callable, Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")


def progress_items(
    items: Sequence[T],
    callback: Callable[[int, int], None] | None,
) -> Iterator[T]:
    for completed, item in enumerate(items, start=1):
        yield item
        if callback is not None:
            callback(completed, len(items))


def scaled_progress(
    callback: Callable[[str, int], None],
    step: str,
    start: int,
    end: int,
) -> Callable[[int, int], None]:
    last = start

    def report(completed: int, total: int) -> None:
        nonlocal last
        pct = start + (end - start) * completed // max(total, 1)
        if pct > last:
            last = pct
            callback(step, pct)

    return report
