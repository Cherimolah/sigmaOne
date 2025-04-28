import asyncio
import random
import time
from typing import List, Tuple, Optional
from copy import deepcopy
import pickle

import torch
from torch import optim
from sqlalchemy import insert, func

from environment import Environment, State, Action, ActionType, convert_id_to_action, IllegalStep, convert_action_to_id, parse_state
from neural_network import Network, crossover_and_mutate, mutate_weights, Critic, prepare_state
from utils import count_cards, find_top_indices, count_unbat_cards
from database import db

EPOCHS = 1000
MATCHES = 20
MODELS_COUNT = 32
ELITE_SIZE = 5


def get_prediction(model: Network, state: State) -> Action:
    probs = [(i, x) for i, x in enumerate(list(model(state)))]
    probs.sort(key=lambda x: x[1], reverse=True)
    return convert_id_to_action(probs[0][0])


def get_steps(model, state) -> List[Action]:
    state = deepcopy(state)
    action = Action()
    steps = []
    if state.step == 0:
        while action.type not in (ActionType.STOP_ATTACK, ActionType.BAT, ActionType.PASS):
            action = get_prediction(model, state)
            state.next_step(action)
            steps.append(action)
    else:
        while not (state.opponent_take_mode or state.player_take_mode or count_cards(state.desk[0]) == count_cards(
                state.desk[1]) or action.type == ActionType.TRANSFER):
            action = get_prediction(model, state)
            state.next_step(action)
            steps.append(action)
    return steps


def battle_networks(model1, model2) -> Tuple[List[Tuple[State, Optional[Action]]], List[Tuple[State, Optional[Action]]], int]:
    env = Environment(deck_size=24)
    env.reset()
    count = 0
    history_player = []
    history_opponent = []
    while not env.state.ended:
        opponent_state = env.state.mirror()

        if env.state.step == 0:  # Player attack mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.opponent_take_mode:
                # Player attack
                steps = get_steps(model1, env.state)
                mode = 0
            else:
                # Opponent defend
                steps = get_steps(model2, opponent_state)
                mode = 1
        else:  # Player defend mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.player_take_mode:
                # Opponent attack
                steps = get_steps(model2, opponent_state)
                mode = 1
            else:
                # Player defend
                steps = get_steps(model1, env.state)
                mode = 0

        for step in steps:
            if mode == 0:
                history_player.append((deepcopy(env.state), step))
            else:
                history_opponent.append((deepcopy(env.state.mirror()), step))
            env.state.next_step(step)
            count += 1

        if count >= 300:
            break
    history_player.append((deepcopy(env.state), None))
    history_opponent.append((deepcopy(env.state.mirror()), None))
    return history_player, history_opponent, env.state.winner


def tournament(models):
    # Создаем копию списка моделей, чтобы не изменять исходный
    models = list(models)
    scores = [0] * len(models)
    current_round = models.copy()
    stage_points = {32: 1, 16: 2, 8: 4, 4: 8, 2: 16}

    while len(current_round) >= 2:
        print(len(current_round))
        n = len(current_round)
        points = stage_points.get(n, 0)
        next_round = []

        # Проверяем, что количество участников четное
        if n % 2 != 0:
            raise ValueError("Нечетное количество участников в раунде")

        for i in range(0, n, 2):
            model1 = current_round[i]
            model2 = current_round[i + 1]

            _, _, result = battle_networks(model1, model2)
            print(result)

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


def test(model) -> int:
    wins = 0
    for _ in range(100):
        env = Environment(deck_size=24)
        env.reset()
        count = 0
        while not env.state.ended:

            if env.state.step == 0:  # Player attack mode
                if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.opponent_take_mode:
                    # Player attack
                    steps = get_steps(model, env.state)
                else:
                    # Opponent defend
                    steps = get_random_steps(env.state.mirror())
            else:  # Player defend mode
                if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.player_take_mode:
                    # Opponent attack
                    steps = get_random_steps(env.state.mirror())
                else:
                    # Player defend
                    steps = get_steps(model, env.state)

            for step in steps:
                env.state.next_step(step)
                count += 1

            if count >= 300:
                return 3
        if env.state.winner == 0:
            wins += 1

    print(f'{wins}% wins with random player')


def get_smart_bot_steps(state) -> List[Action]:
    non_trumps = [x for x in state.opponent_cards if x.suit != state.trump.suit]
    non_trumps.sort(key=lambda x: x.number)
    trumps = [x for x in state.opponent_cards if x.suit == state.trump.suit]
    trumps.sort(key=lambda x: x.number)
    if state.step == 0:  # Bot defend
        # Try transfer
        if count_cards(state.desk[1]) == 0 and count_unbat_cards(state.desk[1]) < len(state.player_cards):
            for card in non_trumps:
                if card.value == state.desk[0][0].value:
                    return [Action(ActionType.TRANSFER, card)]
            for card in trumps:
                if card.value == state.desk[0][0].value:
                    return [Action(ActionType.TRANSFER, card)]
        # Try beat
        actions = []
        unbat_cards = [card for i, card in enumerate(state.desk[0]) if not state.desk[1][i]]
        opponent_cards = deepcopy(state.opponent_cards)
        for unbat in unbat_cards:
            non_trumps = [x for x in opponent_cards if x.suit != state.trump.suit]
            non_trumps.sort(key=lambda x: x.number)
            trumps = [x for x in opponent_cards if x.suit == state.trump.suit]
            trumps.sort(key=lambda x: x.number)
            same_suits = [x for x in opponent_cards if x.suit == unbat.suit and x.number > unbat.number]
            same_suits.sort(key=lambda x: x.number)
            if same_suits:
                actions.append(Action(ActionType.DEFEND, same_suits[0]))
                if unbat.suit != state.trump.suit:
                    opponent_cards.remove(same_suits[0])
                else:
                    opponent_cards.remove(same_suits[0])
                continue
            if trumps:
                if unbat.suit != state.trump.suit:
                    actions.append(Action(ActionType.DEFEND, trumps[0]))
                    opponent_cards.remove(trumps[0])
                else:
                    for card in trumps:
                        if card.value > unbat.value:
                            actions.append(Action(ActionType.DEFEND, card))
                            opponent_cards.remove(card)
                            break
                    return [Action(ActionType.TAKE)]
                continue
            return [Action(ActionType.TAKE)]
        return actions
    else:  # Bot attack
        if len(state.desk[0]) == 0:
            if non_trumps:
                return [Action(ActionType.ATTACK, non_trumps[0]), Action(ActionType.STOP_ATTACK)]
            else:
                return [Action(ActionType.ATTACK, trumps[0]), Action(ActionType.STOP_ATTACK)]
        numbers = list({x.number for x in state.desk[0]} | {x.number for x in state.desk[1] if x})
        actions = []
        for card in non_trumps:
            if len(state.player_cards) <= count_unbat_cards(state.desk[1]) + len(actions) or state.max_card_desk <= len(state.desk[0]) + len(actions):
                break
            if card.number in numbers:
                actions.append(Action(ActionType.ATTACK, card))
        if state.player_take_mode:
            actions.append(Action(ActionType.PASS))
        else:
            if not actions:
                return [Action(ActionType.BAT)]
            actions.append(Action(ActionType.STOP_ATTACK))
        return actions


def get_random_steps(state: State) -> List[Action]:
    cards = list(state.player_cards)
    random.shuffle(cards)
    if state.step == 0:
        if len(state.desk[0]) == 0:
            card = random.choice(list(state.player_cards))
            return [Action(ActionType.ATTACK, card)]
        if len(state.desk[0]) >= state.max_card_desk or not state.opponent_cards or count_unbat_cards(state.desk[1]) >= len(state.opponent_cards):
            if state.opponent_take_mode:
                return [Action(ActionType.PASS)]
            if count_cards(state.desk[0]) > count_cards(state.desk[1]):
                return [Action(ActionType.STOP_ATTACK)]
            return [Action(ActionType.BAT)]
        if random.choice([0, 1]) == 0:
            if state.opponent_take_mode:
                return [Action(ActionType.PASS)]
            return [Action(ActionType.BAT)]
        values = {x.value for x in state.desk[0]} | {x.value for x in state.desk[1] if x}
        for card in cards:
            if card.value in values:
                if not state.opponent_take_mode:
                    return [Action(ActionType.ATTACK, card)]
                return [Action(ActionType.ATTACK, card), Action(ActionType.PASS)]
        if state.opponent_take_mode:
            return [Action(ActionType.PASS)]
        return [Action(ActionType.BAT)]
    else:
        if count_cards(state.desk[1]) == 0 and len(state.opponent_cards) - count_unbat_cards(state.desk[1]) > 0:
            for card in cards:
                if card.value == state.desk[0][0].value:
                    return [Action(ActionType.TRANSFER, card)]
        if random.choice([0, 1, 2]) == 0:
            return [Action(ActionType.TAKE)]
        state = deepcopy(state)
        for card in cards:
            try:
                state.next_step(Action(ActionType.DEFEND, card))
                return [Action(ActionType.DEFEND, card)]
            except IllegalStep:
                pass
        return [Action(ActionType.TAKE)]


def train():
    top_model = Network()
    # top_model.load_state_dict(torch.load('model_weights.pth'))
    models = [deepcopy(top_model) for _ in range(MODELS_COUNT)]
    for i in range(EPOCHS):
        scores = [0] * MODELS_COUNT
        for i1 in range(MATCHES):
            ids = list(range(MODELS_COUNT))
            random.shuffle(ids)
            models = [models[i] for i in ids]
            intermediate_scores = tournament(models)
            for n, score in enumerate(intermediate_scores):
                scores[ids[n]] += score
        print(scores)
        print(f'Epoch {i + 1}/{EPOCHS} done')
        top_models = [models[i] for i in find_top_indices(scores, ELITE_SIZE)]  # ELITE_SIZE = 4-8

        new_models = []

        torch.save(top_models[0].state_dict(), 'model_weights1.pth')

        test_on_smart_bot(top_models[0])

        # Добавляем элиту
        new_models.extend(top_models)

        # Генерация новых моделей
        for _ in range(MODELS_COUNT - len(new_models)):
            parents = random.choices(top_models, k=2)
            child = crossover_and_mutate(parents[0], parents[1])
            new_models.append(mutate_weights(child))

        models = new_models

        if i % 10 == 0:
            test(top_models[0])
            test_on_smart_bot(top_models[0])


def battle_smart_bot(model) -> Tuple[List[Tuple[State, Optional[Action]]], List[Tuple[State, Optional[Action]]], int]:
    env = Environment(deck_size=24)
    env.reset()
    steps_count = 0
    history_player = []
    history_opponent = []
    while not env.state.ended:

        if env.state.step == 0:  # Player attack mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.opponent_take_mode:
                # Player attack
                steps = get_steps(model, env.state)
                mode = 0
            else:
                # Opponent defend
                steps = get_smart_bot_steps(env.state)
                mode = 1
        else:  # Player defend mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.player_take_mode:
                # Opponent attack
                steps = get_smart_bot_steps(env.state)
                mode = 1
            else:
                # Player defend
                steps = get_steps(model, env.state)
                mode = 0

        for step in steps:
            if mode == 0:
                history_player.append((deepcopy(env.state), step))
            else:
                history_opponent.append((env.state.mirror(), step))
            env.state.next_step(step)
            steps_count += 1

        if steps_count >= 300:
            break
    history_player.append((env.state, None))
    history_opponent.append((env.state.mirror(), None))
    return history_player, history_opponent, env.state.winner


def battle_random_bot(model) -> Tuple[List[Tuple[State, Optional[Action]]], List[Tuple[State, Optional[Action]]], int]:
    env = Environment(deck_size=24)
    env.reset()
    steps_count = 0
    history_player = []
    history_opponent = []
    while not env.state.ended:

        if env.state.step == 0:  # Player attack mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.opponent_take_mode:
                # Player attack
                steps = get_steps(model, env.state)
                mode = 0
            else:
                # Opponent defend
                steps = get_random_steps(env.state.mirror())
                mode = 1
        else:  # Player defend mode
            if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.player_take_mode:
                # Opponent attack
                steps = get_random_steps(env.state.mirror())
                mode = 1
            else:
                # Player defend
                steps = get_steps(model, env.state)
                mode = 0

        for step in steps:
            if mode == 0:
                history_player.append((deepcopy(env.state), step))
            else:
                history_opponent.append((env.state.mirror(), step))
            env.state.next_step(step)
            steps_count += 1

        if steps_count >= 300:
            break
    history_player.append((env.state, None))
    history_opponent.append((env.state.mirror(), None))
    return history_player, history_opponent, env.state.winner


def test_on_smart_bot(model):
    wins = 0
    count = 100
    for i in range(count):
        _, _, winner = battle_smart_bot(model)
        if winner == 0:
            wins += 1
    print(f'{int(wins / count * 100)}% wins with smart player')
    return wins


async def test_random_smart():
    count = 0
    for i in range(10000):
        env = Environment(deck_size=24)
        env.reset()
        history_player: List[Tuple[State, Optional[Action]]] = []
        history_opponent: List[Tuple[State, Optional[Action]]] = []
        count_steps = 0
        model = Network()
        while not env.state.ended:

            if env.state.step == 0:  # Player attack mode
                if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.opponent_take_mode:
                    # Player attack
                    actions = get_steps(model, env.state)
                    step = 0
                else:
                    # Opponent defend
                    actions = get_smart_bot_steps(env.state)
                    step = 1
            else:  # Player defend mode
                if count_cards(env.state.desk[0]) <= count_cards(env.state.desk[1]) or env.state.player_take_mode:
                    # Opponent attack
                    actions = get_smart_bot_steps(env.state)
                    step = 1
                else:
                    # Player defend
                    actions = get_steps(model, env.state)
                    step = 0

            for action in actions:
                # Step в env.state показывает скорее режим, кто в атаке, к то в защите
                # Здесь же нужно знать кто конкретно ходил. При одном step == 0 одновременно атакует игрок и
                # защищается оппонент
                if step == 0:
                    history_player.append((deepcopy(env.state), action))
                else:
                    history_opponent.append((deepcopy(env.state), action))
                env.state.next_step(action)
                count_steps += 1
                if env.state.ended:
                    history_player.append((deepcopy(env.state), None))
                    history_opponent.append((deepcopy(env.state), None))
                    break

            if count_steps >= 300:
                break

        if not env.state.winner:  # Draw
            continue

        data_player = []
        for i1, d in enumerate(history_player[:-1]):
            state, action = d
            if len(history_player) - 1 > i1:
                data_player.append({'state': pickle.dumps(state),
                                    # 'next_state': pickle.dumps(history_player[i1+1][0]),
                             'action_id': convert_action_to_id(action),
                                    # 'reward': 0.9 ** (len(history_player) - i1 - 1),
                             # 'done': False
                })
            else:
                data_player.append(
                    {'state': pickle.dumps(state),
                     # 'next_state': pickle.dumps(history_player[i1+1][0]),
                     'action_id': convert_action_to_id(action),
                     # 'reward': 1, 'done': True
                     })

        # data_opponent = []
        # for i1, d in enumerate(history_opponent[:-1]):
        #     state, action = d
        #     if len(history_opponent) - 1 > i1:
        #         data_opponent.append(
        #             {'state': pickle.dumps(state.mirror()), 'next_state': pickle.dumps(history_opponent[i1 + 1][0].mirror()),
        #              'action_id': convert_action_to_id(action), 'reward': 0.9 ** (len(history_opponent) - i1 - 1),
        #              'done': False})
        #     else:
        #         data_opponent.append(
        #             {'state': pickle.dumps(state.mirror()), 'next_state': pickle.dumps(history_opponent[i1 + 1][0].mirror()),
        #              'action_id': convert_action_to_id(action), 'reward': 1, 'done': True})

        print(i, env.state.winner, env.state)
        if env.state.winner == 0:
            # for data in data_opponent:
            #     data['reward'] = -data['reward']
            await insert(db.Step2).values(data_player).gino.scalar()
            count += 1
            print(f'{count} loaded')
        # else:
        #     for data in data_player:
        #         data['reward'] = -data['reward']

        # await insert(db.Step).values(data_player).gino.scalar()
        # await insert(db.Step).values(data_opponent).gino.scalar()

        # print(f'{i + 1}/{count} loaded')


async def main():
    await db.connect()
    # await test_random_smart()
    train_policy_gradient()
    await train_gradient()


def fit_policy_gradient(actor, history, win_coeff):
    optimizer_actor = optim.SGD(actor.parameters(), lr=1e-5)
    for i1, data in enumerate(history[:-1]):
        state, action = data
        reward = (0.95 ** (len(history) - i1 - 2)) * win_coeff
        #
        # if i1 > 0:
        #     print(actor(history[i1-1][0]))
        #     print(actor(state), convert_action_to_id(action))

        # Actor update
        log_prob = torch.log(actor(state)[convert_action_to_id(action)])
        # print(log_prob)
        actor_loss = -log_prob * reward

        optimizer_actor.zero_grad()
        actor_loss.backward()
        optimizer_actor.step()
    return actor_loss


def train_policy_gradient():
    actor = Network()
    actor.load_state_dict(torch.load('model_weights1.pth'))
    count = 1000000
    i = 0
    while i < count:
        history_player, history_opponent, winner = battle_networks(actor, mutate_weights(actor))
        if winner == 0:
            win_coeff = 1
        elif winner == 1:
            win_coeff = -1
        else:
            win_coeff = 0

        loss = fit_policy_gradient(actor, history_player, win_coeff)
        if winner == 0:
            print(f'{i + 1} win, {loss.detach()}')
        elif winner == 1:
            print(f'{i + 1} loss, {loss.detach()}')
        else:
            print(f"{i + 1} draw, {loss.detach()}")

        torch.save(actor.state_dict(), 'weights_actor.pth')
        i += 1
        if i % 100 == 0:
            test(actor)
            a = test_on_smart_bot(actor)
            with open('wins.txt', 'a') as file:
                file.write(str(a) + '\n')


async def train_gradient():
    model = Network()
    # model.load_state_dict(torch.load(f'weights_actor.pth'))
    count = await db.select([func.count(db.Step.id)]).where(db.Step.reward > 0).gino.scalar()
    loss_func = torch.nn.NLLLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    for i in range(0, count, 100):
        response = await db.select([db.Step.state, db.Step.action_id]).where(db.Step.reward > 0).offset(i).limit(100).gino.all()
        loss_batch = 0
        for state, action_id in response:
            state = pickle.loads(state)

            # Forward
            outputs = model(state)
            loss = loss_func(torch.log(outputs), torch.tensor(action_id, dtype=torch.long))
            optimizer.zero_grad()  # Обнуляем градиенты
            loss.backward()  # Вычисляем градиенты
            optimizer.step()

            loss_batch += loss.detach()

        print(f'{i + 100}/{count} loss: {loss_batch / 100}')
        # print(outputs, action_id)
        # print(prepare_state(state))
        # print(outputs, actions)
        torch.save(model.state_dict(), 'model_weights1.pth')

        if (i + 100) % 30000 == 0:
            test(model)
            test_on_smart_bot(model)


if __name__ == '__main__':
    train()
    # test_on_smart_bot()
    # asyncio.run(main())
    # model = Network()
    # model.load_state_dict(torch.load('model_weights1.pth'))
    # test(model)
    # test_on_smart_bot(model)
