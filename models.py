from typing import List, Tuple

from pydantic import BaseModel
from environment import Step


class StateModel(BaseModel):
    hand: List[int]  # Карты в руке (нейросети)
    desk: Tuple[List[int], List[int | None]]  # Карты на столе
    known_cards: List[int]  # Карты, которые забрал противник (игрок)
    count_opponent_cards: int  # Сколько карт в руке у оппонента
    bat: List[int]  # Бито
    trump: int  # Козырная карта
    step: Step  # Тип хода
    opponent_take_mode: bool  # Берет

