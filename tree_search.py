from collections import defaultdict
import copy

from anytree import Node

from environment import Step, State, Action

class GameNode(Node):
    """Узел дерева игры для алгоритма минимакс."""

    def __init__(self, state, action=None, parent=None, node_depth=0, maximizing_player=True):
        # Генерируем уникальное имя для anytree
        name = f"node_{id(self)}"
        super().__init__(name, parent=parent)

        self.state = state
        self.action = action
        self.node_depth = node_depth
        self.maximizing_player = maximizing_player
        self.value = None
        self.alpha = float('-inf')
        self.beta = float('inf')


class GameTreeSearcher:
    """Класс для поиска оптимального хода с использованием дерева игры."""

    DISCOUNT_FACTOR = 0.995

    def __init__(self, model, discount_factor=None):
        self.model = model
        self.discount_factor = discount_factor or self.DISCOUNT_FACTOR

    def evaluate_actions(self, state: State) -> list[tuple[Action, float]]:
        """Выбирает лучшее действие для текущего состояния."""
        max_depth = self._determine_search_depth(state)
        root, leaves = self._build_game_tree(state, max_depth)

        self._evaluate_leaves(leaves)
        self._compute_minimax_values(root)

        return self._extract_best_actions(root)

    @staticmethod
    def _determine_search_depth(state):
        """Определяет глубину поиска на основе состояния игры."""
        if len(state.deck) < 6:
            if len(state.player_cards) >= 8 or len(state.opponent_cards) >= 8:
                return 6 if len(state.player_cards) >= 11 or len(state.opponent_cards) >= 11 else 8
            return 10
        return 8

    def _build_game_tree(self, root_state, max_depth):
        """Строит дерево игры до указанной глубины."""
        root = GameNode(
            state=root_state,
            node_depth=0,
            maximizing_player=root_state.step in (Step.PLAYER_ATTACK, Step.PLAYER_DEFEND)
        )

        leaves = []
        nodes_to_expand = [root]

        while nodes_to_expand:
            current_node = nodes_to_expand.pop()

            if self._should_stop_expansion(current_node, max_depth):
                leaves.append(current_node)
                continue

            self._expand_node(current_node, nodes_to_expand)

        return root, leaves

    @staticmethod
    def _should_stop_expansion(node, max_depth):
        """Определяет, нужно ли прекращать расширение узла."""
        return node.node_depth == max_depth or node.state.finished

    @staticmethod
    def _expand_node(parent_node, nodes_to_expand):
        """Создает дочерние узлы для заданного родительского узла."""
        for action in parent_node.state.get_available_actions():
            new_state = copy.deepcopy(parent_node.state)
            new_state.next_step(action)

            is_maximizing = new_state.step in (Step.PLAYER_ATTACK, Step.PLAYER_DEFEND)
            child = GameNode(
                state=new_state,
                action=action,
                parent=parent_node,
                node_depth=parent_node.node_depth + 1,
                maximizing_player=is_maximizing
            )

            nodes_to_expand.append(child)

    def _evaluate_leaves(self, leaves):
        """Вычисляет оценочные значения для листьев дерева."""
        if not leaves:
            return

        leaf_states = [leaf.state for leaf in leaves]
        model_predictions = self.model(leaf_states)

        for leaf, prediction in zip(leaves, model_predictions):
            leaf.value = self._calculate_leaf_value(leaf, prediction)

    @staticmethod
    def _calculate_leaf_value(leaf, model_prediction):
        """Вычисляет значение для листового узла."""
        if leaf.state.finished:
            return 1 if leaf.state.winner == 0 else -1
        return model_prediction

    def _compute_minimax_values(self, root):
        """Вычисляет минимаксные значения для всех узлов дерева."""
        nodes_by_depth = defaultdict(list)

        # Группируем узлы по глубине
        for node in root.descendants:
            nodes_by_depth[node.node_depth].append(node)
        nodes_by_depth[0].append(root)

        # Обратный проход от самых глубоких узлов к корню
        max_depth = max(nodes_by_depth.keys())

        for depth in range(max_depth, -1, -1):
            if depth not in nodes_by_depth:
                continue

            for node in nodes_by_depth[depth]:
                if not node.children:
                    continue

                discounted_child_values = [
                    child.value * self.discount_factor
                    for child in node.children
                ]

                node.value = self._aggregate_child_values(
                    node, discounted_child_values
                )

    @staticmethod
    def _aggregate_child_values(node, child_values):
        """Агрегирует значения дочерних узлов в зависимости от типа игрока."""
        if not child_values:
            return float('-inf') if node.maximizing_player else float('inf')

        if node.maximizing_player:
            return max(child_values)
        return min(child_values)

    @staticmethod
    def _extract_best_actions(root):
        """Извлекает действия и их значения из дочерних узлов корня."""
        return [(child.action, child.value) for child in root.children]