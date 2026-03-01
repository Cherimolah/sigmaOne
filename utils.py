import copy
import random

from environment import State, all_cards_24, Card, Action, Step
from tree_search import GameTreeSearcher
from models import StateModel
from neural_network import Network


def create_similar_state(state: State, mirror_mode=False) -> State:
    """
    Функция создает похожий стейт на основе существующего
    То есть рандомит все неизвестные достоверно элементы, остальные (известные) копирует как есть
    :param mirror_mode: если включен, то считает игрока за оппонента
    :param state:
    :return:
    """
    # Копируем стейт в новый
    state_copy = State(state.deck_size, state.transferable)
    state_copy.trump = state.trump
    state_copy.player_take_mode = state.player_take_mode
    state_copy.opponent_take_mode = state.opponent_take_mode
    state_copy.desk = (copy.copy(state.desk[0]), copy.copy(state.desk[1]))
    state_copy.bat = copy.copy(state.bat)

    pull_cards = all_cards_24

    state_copy.player_known_cards = copy.copy(state.player_known_cards)
    state_copy.opponent_known_cards = copy.copy(state.opponent_known_cards)
    state_copy.step = state.step
    state_copy.finished = state.finished
    state_copy.max_card_desk = state.max_card_desk
    state_copy.check_win()

    if not mirror_mode:
        state_copy.player_cards = copy.copy(state.player_cards)
        state_copy.opponent_cards = copy.copy(state.player_known_cards)
    else:
        state_copy.player_cards = copy.copy(state.opponent_known_cards)
        state_copy.opponent_cards = copy.copy(state.opponent_cards)

    # Считаем какие карты остались неизвестными
    pull_cards = pull_cards - state_copy.opponent_cards - state_copy.player_cards - state_copy.bat - set(
        state_copy.desk[0]) - set(state_copy.desk[1])

    # Если колода была, то убираем из рандома козырь (он переходит в колоду как достоверный)
    if len(state.deck) > 0:
        pull_cards = pull_cards - {state_copy.trump}
        # Далее раскидываем недостающие карты оппоненту и в колоду
        if not mirror_mode:
            for _ in range(len(state.opponent_cards) - len(state_copy.opponent_cards)):
                card = random.choice(list(pull_cards))
                state_copy.opponent_cards.add(card)
                pull_cards.discard(card)
        else:
            for _ in range(len(state.player_cards) - len(state_copy.player_cards)):
                card = random.choice(list(pull_cards))
                state.player_cards.add(card)
                pull_cards.discard(card)
        pull_cards = list(pull_cards)
        random.shuffle(pull_cards)
        state_copy.deck = pull_cards + [state_copy.trump]
    # Если колода уже разобрана, то все неизвестные карты уходят оппоненту (в т.ч. и козырь, если он нигде не вычитался)
    else:
        if not mirror_mode:
            state_copy.opponent_cards = state_copy.opponent_cards.union(pull_cards)
        else:
            state_copy.player_cards = state_copy.player_cards.union(pull_cards)
    return state_copy


def evaluate_action_tree(model: Network, state: State) -> list[tuple[Action, float]]:
    """Основная функция для выбора действия"""
    searcher = GameTreeSearcher(model)
    return searcher.evaluate_actions(state)


def create_state_from_model(model: StateModel) -> State:
    state = State(deck_size=24, transferable=True)
    state.player_cards = {Card(x, 9) for x in model.hand}
    state.opponent_cards = {Card(x, 9) for x in model.known_cards}
    state.trump = Card(model.trump, 9)
    state.bat = {Card(x, 9) for x in model.bat}
    state.opponent_take_mode = model.opponent_take_mode
    state.player_take_mode = False
    state.desk = ([Card(x, 9) for x in model.desk[0]],
                  [Card(x, 9) for x in model.desk[1] if x])
    state.finished = False
    if state.bat:
        state.max_card_desk = 6
    else:
        state.max_card_desk = 5

    pull_cards = (
            all_cards_24 - state.player_cards - state.opponent_cards - {x for x in state.desk[0]} -
            {x for x in state.desk[0] if x} - state.bat
    )

    # Если оставшийся пул карт меньше, чем у оппонента, то рандомим ему карты
    if model.count_opponent_cards < len(pull_cards):
        pull_cards.discard(state.trump)  # Козырь переходит в колоду
        for _ in range(model.count_opponent_cards - len(state.opponent_cards)):
            card = random.choice(list(pull_cards))
            state.opponent_cards.add(card)
            pull_cards.discard(card)
        deck = list(pull_cards)
        random.shuffle(deck)
        deck.append(state.trump)
        state.deck = deck
    else:
        state.opponent_cards |= pull_cards
    state.check_win()
    state.step = model.step

    return state
