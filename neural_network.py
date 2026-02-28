from typing import Union

import torch
import torch.nn as nn
from torch.nn import functional as F

from environment import State, Action, ActionType, Card, Step, all_cards_24


def parse_state(states: State | list[State]) -> tuple[list[list[float]], list[int]]:
    if isinstance(states, State):
        states = [states]
    pre_states = []
    ones = [1] * len(states)
    for i, state in enumerate(states):
        if state.step in (Step.PLAYER_ATTACK, Step.PLAYER_DEFEND):
            state = state.mirror()
            ones[i] = -1
        pre_state: list[float] = [0.0] * 170

        # Карты свои
        for card in state.player_cards:
            pre_state[card.id + 24 * 0] = 1.0

        # Карты соперника (известные)
        for card in state.player_known_cards:
            pre_state[card.id + 24] = 1.0

        # Колода и карты соперника (вероятности)
        unknown_cards = all_cards_24 - state.player_cards - state.player_known_cards - state.bat - set(state.desk[0]) - set(state.desk[1])
        if state.trump in state.deck:
            unknown_cards.discard(state.trump)
        if unknown_cards:
            probability_hand = (len(state.opponent_cards) - len(state.player_known_cards)) / len(unknown_cards)
            for card in list(unknown_cards):
                pre_state[card.id + 24 * 1] = probability_hand
                pre_state[card.id + 24 * 6] = 1 - probability_hand

        # Козырь
        pre_state[state.trump.id + 24 * 2] = 1.0
        if state.trump in state.deck:
            pre_state[state.trump.id + 24 * 6] = 1.0

        # Бито
        for card in state.bat:
            pre_state[card.id + 24 * 3] = 1.0

        # Стол
        for i, card in enumerate(state.desk[0]):
            pre_state[card.id + 24 * 4] = 1.0
            if state.desk[1][i]:
                pre_state[state.desk[1][i].id + 24 * 4] = 1.0
            else:
                pre_state[card.id + 24 * 5] = 1.0

        if state.step == Step.PLAYER_ATTACK:
            pre_state[-2] = 1.0  # Атака
        else:
            pre_state[-2] = 0.0  # Защита
        pre_state[-1] = float(int(state.opponent_take_mode))  # Берет ли соперник (take_mode)
        pre_states.append(pre_state)
    return pre_states, ones


def convert_id_to_action(i: int) -> Action | None:
    if 23 >= i >= 0:
        return Action(ActionType.ATTACK, Card(i, 9))
    elif 24 <= i <= 47:
        return Action(ActionType.DEFEND, Card(i - 24, 9))
    elif 48 <= i <= 71:
        return Action(ActionType.TRANSFER, Card(i - 48, 9))
    elif i == 72:
        return Action(ActionType.BAT)
    elif i == 73:
        return Action(ActionType.TAKE)
    elif i == 74:
        return Action(ActionType.PASS)
    elif i == 75:
        return Action(ActionType.STOP_ATTACK)


class AttentionModule(nn.Module):
    def __init__(self, embed_size=16):
        super(AttentionModule, self).__init__()
        self.embed_size = embed_size

        # Проекционные слои для Q, K, V
        self.values = nn.Linear(embed_size, embed_size, bias=False)
        self.keys = nn.Linear(embed_size, embed_size, bias=False)
        self.queries = nn.Linear(embed_size, embed_size, bias=False)

    def forward(self, x, y):
        # x: (batch_size, seq_len, embed_size)
        batch_size, seq_len, _ = x.size()

        # Получаем Q, K, V
        Q = self.queries(y)  # (batch_size, seq_len, embed_size)
        K = self.keys(x)  # (batch_size, seq_len, embed_size)
        V = self.values(x)  # (batch_size, seq_len, embed_size)

        # Вычисляем скоры внимания
        scores = torch.bmm(Q, K.transpose(1, 2)) / (self.embed_size ** 0.5)
        # scores: (batch_size, seq_len, seq_len)

        # Применяем softmax к скорам
        attention_weights = F.softmax(scores, dim=-1)

        # Умножаем веса на значения
        out = torch.bmm(attention_weights, V)
        # out: (batch_size, seq_len, embed_size)

        return out


class Network(nn.Module):
    def __init__(self):
        super(Network, self).__init__()


        self.embedding = nn.Embedding(num_embeddings=24, embedding_dim=16)

        self.player_hand_trump = AttentionModule()
        self.player_hand_table = AttentionModule()
        self.player_hand_table_unbeat = AttentionModule()
        self.player_hand_bat = AttentionModule()
        self.player_hand_opponent_hand = AttentionModule()
        self.opponent_hand_trump = AttentionModule()
        self.opponent_hand_table_unbeat = AttentionModule()

        self.deck_player_hand = AttentionModule()
        self.deck_opponent_hand = AttentionModule()
        self.player_hand_self = AttentionModule()
        self.opponent_hand_self = AttentionModule()
        self.opponent_hand_bat = AttentionModule()

        self.estimate_layers = nn.Sequential(
            nn.Linear(3490, 2048), nn.ReLU(),
            nn.Linear(2048, 1024), nn.ReLU(),
            nn.Linear(1024, 512), nn.ReLU(),
            nn.Linear(512, 128), nn.ReLU(),
            nn.Linear(128, 32), nn.ReLU(),
            nn.Linear(32, 1), nn.Tanh()
        )




    def forward(self, x: State | list[State]):
        tensor, ones = self.prepare_state(x)  # [batch_size, 386]

        player_hand = self.weight_embeddings(tensor[:, :24])  # [batch_size, 24, embedd_dim]
        opponent_hand = self.weight_embeddings(tensor[:, 24:48])  # [batch_size, 24, embedd_dim]
        trump = torch.matmul(tensor[:, 48:72], self.embedding.weight).unsqueeze(1)  # [batch_size, 1, embedd_dim]
        bat = self.weight_embeddings(tensor[:, 72:96])  # [batch_size, 24, embedd_dim]
        table_all = self.weight_embeddings(tensor[:, 96:120])  # [batch_size, 24, embedd_dim]
        table_unbeat = self.weight_embeddings(tensor[:, 120:144])  # [batch_size, 24, embedd_dim]
        deck = self.weight_embeddings(tensor[:, 144:168])
        params = tensor[:, 168:]

        player_hand_trump = self.player_hand_trump(player_hand, trump).flatten(1)  # [batch_size, 16]
        player_hand_table = self.player_hand_table(player_hand, table_all).flatten(1)  # [batch_size, 384]
        player_hand_table_unbeat = self.player_hand_table_unbeat(player_hand, table_unbeat).flatten(1)  # [batch_size, 384]
        player_hand_bat = self.player_hand_bat(player_hand, bat).flatten(1)  # [batch_size, 384]
        deck_player_hand = self.deck_player_hand(deck, player_hand).flatten(1)  # [batch_size, 384]
        deck_opponent_hand = self.deck_opponent_hand(deck, opponent_hand).flatten(1)  # [batch_size, 384]
        player_hand_self = self.player_hand_self(player_hand, player_hand).flatten(1)  # [batch_size, 384]
        opponent_hand_self = self.opponent_hand_self(opponent_hand, opponent_hand).flatten(1)  # [batch_size, 384]
        opponent_hand_bat = self.opponent_hand_bat(opponent_hand, bat).flatten(1)

        opponent_hand_trump = self.opponent_hand_trump(opponent_hand, trump).flatten(1)  # [batch_size, 16]
        opponent_hand_table_unbeat = self.opponent_hand_table_unbeat(opponent_hand, table_unbeat).flatten(1)  # [batch_size, 384]

        attention_features = torch.cat(
            [player_hand_trump, player_hand_table, player_hand_table_unbeat, player_hand_bat,
             opponent_hand_trump, opponent_hand_table_unbeat, deck_player_hand, deck_opponent_hand, player_hand_self,
             opponent_hand_self, opponent_hand_bat, params],
            dim=1
        )

        estimate = self.estimate_layers(attention_features)
        estimate = estimate * ones.unsqueeze(-1)

        return estimate

    @staticmethod
    def prepare_state(state: Union["State", list["State"]]) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Преобразует стейт в тензор для нейронки
        """
        pre_state, ones = parse_state(state)
        tensor = torch.tensor(pre_state, dtype=torch.float, requires_grad=True)
        ones = torch.tensor(ones, dtype=torch.float, requires_grad=False)
        return tensor, ones

    def get_prediction(self, state: State) -> Action:
        probs = [(i, x) for i, x in enumerate(list(self.forward(state)))]
        probs.sort(key=lambda x: x[1], reverse=True)
        return convert_id_to_action(probs[0][0])

    def prepare_table(self, table: torch.Tensor) -> torch.Tensor:
        batch_size = table.size(0)
        table = table.reshape(batch_size, 11, 24)
        # Вместо argmax используйте взвешенную сумму
        table_embedded = torch.matmul(table, self.embedding.weight)

        zeros = torch.zeros(batch_size, 1, 16, device=table.device)
        table_embedded = torch.cat([table_embedded, zeros], dim=1)
        return table_embedded

    def weight_embeddings(self, weights: torch.Tensor) -> torch.Tensor:
        weighted_embeddings = self.embedding.weight * weights.unsqueeze(2)
        return weighted_embeddings

