from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from environment import Card


def count_cards(cards: Iterable["Card"]) -> int:
    i = 0
    for card in cards:
        if card:
            i += 1
    return i


def find_top_indices(numbers, top=4):
    # Создаем список кортежей (индекс, значение)
    indexed = list(enumerate(numbers))
    # Сортируем по убыванию значения, затем по возрастанию индекса (для стабильности)
    indexed.sort(key=lambda x: (-x[1], x[0]))
    # Берем первые четыре элемента и извлекаем индексы
    top_four = indexed[:top]
    return [idx for idx, val in top_four]
