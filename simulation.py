import random
from typing import List, Tuple
from copy import deepcopy

import torch

from environment import Environment, State, Card, Action, ActionType, IllegalStep
from neural_network import Network, crossover_and_mutate, mutate_weights
from utils import count_cards, find_top_indices

all_cards = {Card(x, 9) for x in list(range(24))}
EPOCHS = 300
MATCHES = 20
MODELS_COUNT = 32
ELITE_SIZE = 5


def prepare_state(state: State) -> torch.Tensor:
    """
    Преобразует стейт в тензор для нейронки
    """
    pre_state: List[float] = [0] * 387

    # Карты свои
    for card in state.opponent_known_cards:
        pre_state[card.id + 24 * 0] = 1

    # Карты соперника (известные)
    for card in state.player_known_cards:
        pre_state[card.id + 24] = 1

    # Колода и карты соерника (вероятности)
    unknown_cards = all_cards - state.player_cards - state.player_known_cards - {state.trump} - state.bat
    if unknown_cards:
        probability_hand = (len(state.opponent_cards) - len(state.player_known_cards)) / len(unknown_cards)
        for card in list(unknown_cards):
            pre_state[card.id + 24 * 1] = probability_hand
            pre_state[card.id + 24 * 2] = 1 - probability_hand

    # Козырь
    pre_state[state.trump.id + 24 * 3] = 1

    # Бито
    for card in state.bat:
        pre_state[card.id + 24 * 4] = 1

    # Стол
    for i, card in enumerate(state.desk[0]):
        pre_state[card.id + 24 * (5 + i)] = 1
    for i, card in enumerate(state.desk[1]):
        if card:
            pre_state[card.id + 24 * (11 + i)] = 1

    if state.step == 0:
        pre_state[-3] = 1  # Атака
    else:
        pre_state[-2] = 1  # Защита
    pre_state[-1] = int(state.opponent_take_mode)  # Берет ли соперник (take_mode)
    return torch.tensor(pre_state, dtype=torch.float)


def get_prediction(model, state, mode: int) -> Action:
    #  Mode: 0 - attack, 1 - defend
    prepared_state = prepare_state(state)
    prediction = model(prepared_state)
    named_predictions: List[Tuple[Action, float]] = []
    for i, prob in enumerate(prediction):
        if 23 >= i >= 0 and mode == 0:
            named_predictions.append((Action(ActionType.ATTACK, Card(i, 9)), prob))
        elif 24 <= i <= 47 and mode == 1:
            named_predictions.append((Action(ActionType.DEFEND, Card(i - 24, 9)), prob))
        elif 48 <= i <= 71 and mode == 1:
            named_predictions.append((Action(ActionType.TRANSFER, Card(i - 48, 9)), prob))
        elif i == 72 and mode == 0:
            named_predictions.append((Action(ActionType.BAT), prob))
        elif i == 73 and mode == 1:
            named_predictions.append((Action(ActionType.TAKE), prob))
        elif i == 74 and mode == 0:
            named_predictions.append((Action(ActionType.PASS), prob))
        elif i == 75 and mode == 0:
            named_predictions.append((Action(ActionType.STOP_ATTACK), prob))
    named_predictions.sort(key=lambda x: x[1], reverse=True)

    # Здесь просто применяем все предикты пока не получится без ошибки.
    # Возможно надо писать проверки вручную, но мне лень, типа а нахуя?
    state = deepcopy(state)
    for pred in named_predictions:
        try:
            state.next_step(pred[0])
        except IllegalStep:
            continue
        else:
            return pred[0]


def get_steps(model, state, mode: int) -> List[Action]:
    state = deepcopy(state)
    action = Action()
    steps = []
    if mode == 0:
        while action.type not in (ActionType.STOP_ATTACK, ActionType.BAT, ActionType.PASS):
            action = get_prediction(model, state, 0)
            state.next_step(action)
            steps.append(action)
    else:
        while not (state.opponent_take_mode or state.player_take_mode or count_cards(state.desk[0]) == count_cards(
                state.desk[1]) or action.type == ActionType.TRANSFER):
            action = get_prediction(model, state, 1)
            state.next_step(action)
            steps.append(action)
    return steps


def battle_networks(model1, model2) -> int:
    env = Environment(deck_size=24)
    env.reset()
    count = 0
    while not env.state.ended:
        opponent_state = env.state.mirror()

        if env.state.step == 0:  # Player attack mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.opponent_take_mode:
                # Player attack
                steps = get_steps(model1, env.state, 0)
            else:
                # Opponent defend
                steps = get_steps(model2, opponent_state, 1)
        else:  # Player defend mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.player_take_mode:
                # Opponent attack
                steps = get_steps(model2, opponent_state, 0)
            else:
                # Player defend
                steps = get_steps(model1, env.state, 1)

        for step in steps:
            env.state.next_step(step)
            count += 1

        if count >= 300:
            return 3
    return env.state.winner


def tournament(models):
    # Создаем копию списка моделей, чтобы не изменять исходный
    models = list(models)
    scores = [0] * len(models)
    current_round = models.copy()
    stage_points = {32: 1, 16: 2, 8: 4, 4: 8, 2: 16}

    while len(current_round) >= 2:
        n = len(current_round)
        points = stage_points.get(n, 0)
        next_round = []

        # Проверяем, что количество участников четное
        if n % 2 != 0:
            raise ValueError("Нечетное количество участников в раунде")

        for i in range(0, n, 2):
            model1 = current_round[i]
            model2 = current_round[i + 1]

            result = battle_networks(model1, model2)

            # Определяем победителя
            if result == 0:
                winner = model1
            elif result == 1:
                winner = model2
            else:
                winner = random.choice([model1, model2])

            # Находим исходный индекс модели в списке models
            winner_idx = models.index(winner)
            scores[winner_idx] += points
            next_round.append(winner)

        current_round = next_round

    return scores


def test(model, prev) -> int:
    # test_nn = Network()
    # wins = 0
    # for _ in range(100):
    #     winner = battle_networks(test_nn, model)
    #     if winner == 1:
    #         wins += 1
    # print(f'{wins}% wins with random player')
    wins = 0
    for _ in range(100):
        winner = battle_networks(prev, model)
        if winner == 1:
            wins += 1
    print(f'{wins}% wins with previous model')
    return wins


def train():
    models = [Network() for _ in range(MODELS_COUNT - 1)]
    top_model = Network()
    models.append(top_model)
    for i in range(EPOCHS):
        scores = [0] * MODELS_COUNT
        for i1 in range(MATCHES):
            intermediate_scores = tournament(models)
            for n, score in enumerate(intermediate_scores):
                scores[n] += score
        print(scores)
        print(f'Epoch {i + 1}/{EPOCHS} done')
        top_models = [models[i] for i in find_top_indices(scores, ELITE_SIZE)]  # ELITE_SIZE = 4-8

        new_models = []

        wins = test(top_models[0], top_model)
        if wins > 50:
            top_model = deepcopy(top_models[0])
            torch.save(top_model.state_dict(), 'model_weights1.pth')
            top_models.append(top_model)

        # Добавляем элиту
        new_models.extend(top_models)

        # Генерация новых моделей
        for _ in range(MODELS_COUNT - len(new_models)):
            parents = random.choices(top_models, k=2)
            child = crossover_and_mutate(parents[0], parents[1])
            new_models.append(mutate_weights(child))

        models = new_models


if __name__ == '__main__':
    train()
