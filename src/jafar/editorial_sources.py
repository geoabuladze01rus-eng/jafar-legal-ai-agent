from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EditorialSource:
    name: str
    url: str
    priority: int
    official: bool = False


DEFAULT_SOURCES: tuple[EditorialSource, ...] = (
    EditorialSource("Верховный Суд РФ", "https://vsrf.ru/", 100, True),
    EditorialSource("Конституционный Суд РФ", "https://ksrf.ru/", 100, True),
    EditorialSource("Генеральная прокуратура РФ", "https://epp.genproc.gov.ru/", 100, True),
    EditorialSource("Следственный комитет РФ", "https://sledcom.ru/", 100, True),
    EditorialSource("ФСИН России", "https://fsin.gov.ru/", 90, True),
)


def sorted_sources() -> list[EditorialSource]:
    return sorted(DEFAULT_SOURCES, key=lambda item: item.priority, reverse=True)
