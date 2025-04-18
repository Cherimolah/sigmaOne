import copy

import torch
import torch.nn as nn


class Network(nn.Module):
    def __init__(self):
        super(Network, self).__init__()
        self.linear = nn.Sequential(
            nn.Linear(387, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 76), nn.Sigmoid()
        )
        self.id = id

    def forward(self, x):
        return self.linear(x)


def crossover_and_mutate(parent1, parent2, mutation_rate=0.1, mutation_scale=0.05):
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


def mutate_weights(model, mutation_rate=0.1, mutation_scale=0.05):
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
