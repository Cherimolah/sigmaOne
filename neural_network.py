import copy
from typing import List, Union

import torch
import torch.nn as nn
from torch.nn import functional as F

from environment import State, Action, IllegalStep, convert_id_to_action, parse_state, ActionType, Environment


class Network(nn.Module):
    def __init__(self):
        super(Network, self).__init__()
        self.linear = nn.Sequential(
            nn.Linear(387, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 76)
        )

    def forward(self, x: State):
        tensor = prepare_state(x)
        logits = self.linear(tensor)
        mask = [0] * len(logits)
        mask = torch.tensor(mask, dtype=torch.bool)
        named_actions: List[Action] = []
        for i, logit in enumerate(logits):
            named_actions.append(convert_id_to_action(i))
        for i, action in enumerate(named_actions):
            state = copy.deepcopy(x)
            if state.step == 0:
                if action.type not in (ActionType.ATTACK, ActionType.STOP_ATTACK, ActionType.BAT, ActionType.PASS):
                    mask[i] = False
                    continue
            else:
                if action.type not in (ActionType.DEFEND, ActionType.TAKE, ActionType.TRANSFER):
                    mask[i] = False
                    continue
            try:
                state.next_step(action)
                mask[i] = True
            except IllegalStep:
                mask[i] = False
        masked_logits = logits.masked_fill(~mask, float('-inf'))
        probs = F.softmax(masked_logits, dim=-1)
        mask = torch.tensor([x > 0 for x in probs], dtype=torch.bool)
        masked_probs = probs.masked_fill(~mask, 1e-8)
        return masked_probs


class Critic(nn.Module):
    def __init__(self):
        super(Critic, self).__init__()
        self.linear = nn.Sequential(
            nn.Linear(387, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
            nn.Linear(8, 4), nn.ReLU(),
            nn.Linear(4, 2), nn.ReLU(),
            nn.Linear(2, 1), nn.Tanh()
        )

    def forward(self, x):
        return self.linear(x)


def crossover_and_mutate(parent1, parent2, mutation_rate=0.5, mutation_scale=0.3):
    """
    Создает новую модель путем кроссовера и мутации двух родительских моделей.

    Аргументы:
        parent1 (torch.nn.Module): Первая родительская модель
        parent2 (torch.nn.Module): Вторая родительская модель
        mutation_rate (float): Вероятность мутации для каждого параметра (по умолчанию 0.1)
        mutation_scale (float): Масштаб случайного шума для мутации (по умолчанию 0.01)

    Возвращает:
        torch.nn.Module: Новая модель-потомок
    """
    # Создаем новую модель-потомок
    child = copy.deepcopy(parent1)
    child_state = child.state_dict()
    parent1_state = parent1.state_dict()
    parent2_state = parent2.state_dict()

    # Проверяем совместимость моделей
    if parent1_state.keys() != parent2_state.keys():
        raise ValueError("Модели имеют разную архитектуру")

    # Производим кроссовер параметров
    for key in child_state:
        # Создаем маску для случайного выбора параметров
        mask = torch.rand_like(parent1_state[key]) < 0.5

        # Применяем кроссовер
        child_state[key] = torch.where(mask, parent1_state[key], parent2_state[key])

        # Добавляем мутацию
        mutation_mask = torch.rand_like(child_state[key]) < mutation_rate
        mutation_noise = torch.randn_like(child_state[key]) * mutation_scale
        child_state[key] = child_state[key] + mutation_mask * mutation_noise

    # Загружаем обновленные параметры в потомка
    child.load_state_dict(child_state)
    return child


def mutate_weights(model, mutation_rate=0.5, mutation_scale=0.5):
    """
    Мутирует веса модели, добавляя случайный шум.

    Параметры:
        model (nn.Module): модель PyTorch
        mutation_rate (float): вероятность мутации отдельного параметра (0-1)
        mutation_scale (float): масштаб шума (стандартное отклонение)
    """
    with torch.no_grad():
        for param in model.parameters():
            if param.requires_grad:  # Мутируем только обучаемые параметры
                # Генерируем маску для случайного выбора мутируемых параметров
                mask = torch.rand_like(param) < mutation_rate
                # Генерируем шум и применяем маску
                noise = torch.randn_like(param) * mutation_scale
                param[mask] += noise[mask]
    return model


def prepare_state(state: "State") -> torch.Tensor:
    """
    Преобразует стейт в тензор для нейронки
    """
    pre_state = parse_state(state)
    return torch.tensor(pre_state, dtype=torch.float, requires_grad=True)
