import copy
import random
from typing import Optional, List, Set, Tuple
from enum import Enum

from utils import count_cards


class Number(int):

    def __str__(self):
        if self < 11:
            return super().__str__()
        match self:
            case 11:
                return "J"
            case 12:
                return "Q"
            case 13:
                return "K"
            case 14:
                return "A"


class Suit(int):

    def __str__(self):
        match self:
            case 0:
                return "♣"
            case 1:
                return "♥"
            case 2:
                return "♠"
            case 3:
                return "♦"


class Card:

    def __init__(self, id_: int, offset: int):
        if not 0 <= id_ <= 51:
            raise Exception("Id card is not correct!")
        self.number = Number((id_ // 4) + offset)
        self.value = str(self.number)
        self.suit = Suit(id_ % 4)
        self.id = id_
        self.name = f"{self.number!s}{self.suit!s}"

    def __repr__(self):
        return self.name

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        if other is None:
            return False
        return self.id == other.id


class Step(int):

    def __repr__(self):
        if self == 0:
            return "Player attack"
        elif self == 1:
            return "Player defend"
        else:
            return super().__repr__()


class IllegalStep(Exception):
    pass


class ActionType(Enum):
    ATTACK = 'attack'
    DEFEND = 'defend'
    TAKE = 'take'
    BAT = 'bat'
    PASS = 'pass'
    TRANSFER = 'transfer'
    STOP_ATTACK = 'stop_attack'


class Action:
    def __init__(self, action: ActionType = None, card: Optional[Card] = None):
        self.type = action
        self.card = card

    def __repr__(self):
        return f"{self.type} {self.card}"

    def __str__(self):
        return self.__repr__()


class State:

    def __init__(self, deck_size: int = 36, transferable: bool = True):
        self.player_cards: Set[Card] = set()
        self.deck: List[Card] = []
        self.opponent_cards: Set[Card] = set()
        self.desk: Tuple[List[Card], List[Optional[Card]]] = ([], [])
        self.trump: Optional[Card] = None
        self.bat: Set[Card] = set()
        self.step: Optional[Step] = None
        self.deck_size = deck_size
        self.transferable = transferable
        if self.deck_size == 24:
            offset = 9
        elif self.deck_size == 36:
            offset = 6
        else:
            offset = 2
        self.offset = offset
        self.ended = False
        self.winner: Optional[int] = None
        self.player_take_mode = False
        self.opponent_take_mode = False
        self.max_card_desk = 5
        self.player_known_cards: Set[Card] = set()
        self.opponent_known_cards: Set[Card] = set()

    def load_cards(self):
        self.deck = [Card(x, self.offset) for x in list(range(self.deck_size))]
        random.shuffle(self.deck)
        self.trump = self.deck[-1]
        self.player_get_cards()
        self.opponent_get_cards()

    def player_get_cards(self):
        while len(self.player_cards) < 6:
            if not self.deck:
                return
            self.player_cards.add(self.deck[0])
            self.deck.pop(0)

    def opponent_get_cards(self):
        while len(self.opponent_cards) < 6:
            if not self.deck:
                return
            self.opponent_cards.add(self.deck[0])
            self.deck.pop(0)

    def load_first_step(self):
        my_trumps = [x.number for x in self.player_cards if x.suit == self.trump.suit]
        opponent_trumps = [x.number for x in self.opponent_cards if x.suit == self.trump.suit]
        if not my_trumps and not opponent_trumps:
            self.step = Step(random.randint(1, 2))
        elif my_trumps and not opponent_trumps:
            self.step = Step(0)
        elif not my_trumps and opponent_trumps:
            self.step = Step(1)
        else:
            self.step = Step(min(opponent_trumps) < min(my_trumps))

    def attack(self, card: Card):
        if self.step == 0:
            hand = self.player_cards
            opponent_hand = self.opponent_cards
        else:
            hand = self.opponent_cards
            opponent_hand = self.player_cards

        if card not in hand:
            raise IllegalStep('Attack card must be in hand')

        card_numbers = {x.number for x in self.desk[0] if x is not None} | {x.number for x in self.desk[1] if
                                                                            x is not None}
        if self.desk[0] and not (card.number in card_numbers):
            raise IllegalStep('Card number must be in numbers at the desk')

        if len(self.desk[0]) >= self.max_card_desk:
            raise IllegalStep('Max card in attack')

        if len(self.desk[0]) + 1 > len(opponent_hand) + count_cards(self.desk[1]):
            raise IllegalStep('Not enogh cards has to defend')

        self.desk[0].append(card)
        self.desk[1].append(None)
        hand.discard(card)

        if self.step == 0:
            self.opponent_known_cards.discard(card)
        else:
            self.player_known_cards.discard(card)

        self.check_win()

    def defend(self, card: Card, index: Optional[int] = None):
        if self.opponent_take_mode or self.player_take_mode:
            raise IllegalStep('You cannot defend while taking mode')
        if self.step == 0:
            hand = self.opponent_cards
        else:
            hand = self.player_cards

        if card not in hand:
            raise IllegalStep('Card not found in hand')

        if not index:
            try:
                index = next((i for i in range(len(self.desk[1])) if not self.desk[1][i]))
            except StopIteration:
                raise IllegalStep('No found card to defend')

        if (card.number > self.desk[0][index].number and card.suit == self.desk[0][index].suit) \
                or (self.desk[0][index].suit != self.trump.suit and card.suit == self.trump.suit):
            self.desk[1][index] = card
            hand.discard(card)
        else:
            raise IllegalStep("Card is too low")
        self.check_win()

        if self.step == 0:
            self.player_known_cards.discard(card)
        else:
            self.opponent_known_cards.discard(card)

        if len(self.desk[1]) >= self.max_card_desk and all(self.desk[1]):
            self.bat_table()

    def bat_table(self):
        if not (self.desk[0] and self.desk[1] and all(self.desk[1])):
            raise IllegalStep('Not enough cards on table')

        cards = {y for x in self.desk for y in x if y}
        self.bat = self.bat.union(cards)
        self.desk = ([], [])
        if self.step == 0:
            self.player_get_cards()
            self.opponent_get_cards()
            self.step = Step(1)
        else:
            self.opponent_get_cards()
            self.player_get_cards()
            self.step = Step(0)
        self.check_win()
        self.max_card_desk = 6

    def take(self):
        if self.player_take_mode or self.opponent_take_mode:
            raise IllegalStep('Take mode is actually enabled')

        if not self.desk[0]:
            raise IllegalStep('Take mode cannot be enabled when none cards in attack')

        if None not in self.desk[1]:
            raise IllegalStep('You can take cards only when there are cards not beated')

        if self.step == 0:
            self.opponent_take_mode = True
        else:
            self.player_take_mode = True

    def pass_cards(self):
        if not self.opponent_take_mode and not self.player_take_mode:
            raise IllegalStep('Take mode is disabled')
        cards = {y for x in self.desk for y in x if y}

        if self.player_take_mode:
            self.opponent_known_cards |= cards
        else:
            self.player_known_cards |= cards

        self.desk = ([], [])
        if self.step == 0:
            self.opponent_cards = self.opponent_cards.union(cards)
            self.player_get_cards()
        else:
            self.player_cards = self.player_cards.union(cards)
            self.opponent_get_cards()
        self.check_win()
        self.opponent_take_mode = False
        self.player_take_mode = False

    def transfer(self, card: Card):
        if not self.transferable:
            raise IllegalStep("Cannot transfer in non-transferable game")

        if self.player_take_mode or self.opponent_take_mode:
            raise IllegalStep('Cannot transfer when take mode is enabled')

        if not self.desk[0]:
            raise IllegalStep("You can't transfer when none cards sent in attack")

        if any(self.desk[1]):
            raise IllegalStep('You can\'t transfer when any card has beated')

        if card.number != self.desk[0][0].number:
            raise IllegalStep("Card must be same number to transfer")

        if self.step == 0:
            hand = self.opponent_cards
            opposite_hand = self.player_cards
            self.player_known_cards.discard(card)
        else:
            hand = self.player_cards
            opposite_hand = self.opponent_cards
            self.opponent_known_cards.discard(card)

        if card not in hand:
            raise IllegalStep('Card must be in hand')

        if len(self.desk[0]) + 1 > len(opposite_hand):
            raise IllegalStep('Opponent doesn\'t have enough cards to beat')

        hand.discard(card)
        self.desk[0].append(card)
        self.desk[1].append(None)
        if self.step == 0:
            self.step = Step(1)
        else:
            self.step = Step(0)
        self.check_win()

    def check_win(self):
        if self.deck:
            return
        if not self.opponent_cards and self.player_cards:
            self.ended = True
            self.winner = 1
        if not self.player_cards and self.opponent_cards:
            self.ended = True
            self.winner = 0

    def mirror(self) -> "State":
        state = copy.deepcopy(self)
        state.player_cards = self.opponent_cards
        state.opponent_cards = self.player_cards
        state.player_known_cards = self.opponent_known_cards
        state.opponent_known_cards = self.player_known_cards
        if state.step == 0:
            state.step = Step(1)
        else:
            state.step = Step(0)
        if self.player_take_mode:
            state.opponent_take_mode = True
            state.player_take_mode = False
        elif self.opponent_take_mode:
            state.player_take_mode = True
            state.opponent_take_mode = False
        return state

    def stop_attack(self):
        if self.opponent_take_mode or self.player_take_mode:
            raise IllegalStep('Cannot stop attack while take mode is enabled')
        if count_cards(self.desk[0]) == count_cards(self.desk[1]):
            raise IllegalStep('Cannot stop attack that have not started yet or beated')

    def next_step(self, action: Action):
        if not action:
            print(self.player_cards, self.opponent_cards, self.deck, self.desk, self.player_take_mode, self.opponent_take_mode, self.step)
        if action.type == ActionType.ATTACK:
            self.attack(action.card)
        elif action.type == ActionType.DEFEND:
            self.defend(action.card)
        elif action.type == ActionType.BAT:
            self.bat_table()
        elif action.type == ActionType.PASS:
            self.pass_cards()
        elif action.type == ActionType.TAKE:
            self.take()
        elif action.type == ActionType.TRANSFER:
            self.transfer(action.card)
        elif action.type == ActionType.STOP_ATTACK:
            self.stop_attack()

    def __str__(self):
        return (f'Player cards = {self.player_cards}, opponent cards = {self.opponent_cards}, trump = {self.trump}, desk = {self.desk}, '
                f'step = {self.step}, deck = {self.deck}, player take mode = {self.player_take_mode}, '
                f'opponent take mode = {self.opponent_take_mode}, player known cards = {self.player_known_cards}, '
                f'opponent known cards = {self.opponent_known_cards}')


class Environment:

    def __init__(self, deck_size: int = 24, transferable: bool = True):
        assert deck_size in (24, 36, 52)
        self.state = State(deck_size=deck_size, transferable=transferable)

    def reset(self):
        self.state = State(self.state.deck_size, self.state.transferable)
        self.state.load_cards()
        self.state.load_first_step()


def convert_id_to_action(i: int) -> Action:
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


def convert_action_to_id(action: Action) -> int:
    if action.type == ActionType.ATTACK:
        return action.card.id
    if action.type == ActionType.DEFEND:
        return 24 + action.card.id
    if action.type == ActionType.TRANSFER:
        return 48 + action.card.id
    if action.type == ActionType.BAT:
        return 72
    if action.type == ActionType.TAKE:
        return 73
    if action.type == ActionType.PASS:
        return 74
    if action.type == ActionType.STOP_ATTACK:
        return 75


def parse_state(state: State) -> List[float]:
    all_cards = {Card(x, 9) for x in list(range(24))}
    pre_state: List[float] = [0] * 387

    # Карты свои
    for card in state.player_cards:
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
    return pre_state
