from copy import deepcopy
import random
from typing import Optional, List, Set, Tuple, Iterable
from enum import IntEnum, Enum


def count_cards(cards: Iterable["Card"]) -> int:
    count = len(list(filter(lambda x: x is not None, cards)))
    return count


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

    def __deepcopy__(self, memo):
        return self

    def __le__(self, other):
        if other is None:
            return False
        return self.id <= other.id

    def __ge__(self, other):
        if other is None:
            return False
        return self.id >= other.id

    def __lt__(self, other):
        if other is None:
            return False
        return self.id < other.id

    def __gt__(self, other):
        if other is None:
            return False
        return self.id > other.id


all_cards_24 = {Card(x, 9) for x in list(range(24))}
all_cards_36 = {Card(x, 6) for x in list(range(36))}
all_cards_52 = {Card(x, 2) for x in list(range(52))}

class Step(Enum):  # Здесь тип Enum, а не  IntEnum потому что так краисивее принтится 🤡
    PLAYER_ATTACK = 1
    PLAYER_DEFEND = 2
    OPPONENT_ATTACK = 3
    OPPONENT_DEFEND = 4


class IllegalStep(Exception):
    pass


class ActionType(IntEnum):
    ATTACK = 1
    TRANSFER = 2
    DEFEND = 3
    TAKE = 4
    BAT = 5
    PASS = 6
    STOP_ATTACK = 7

    def __str__(self):
        if self.value == 1:
            return 'ATTACK'
        elif self.value == 2:
            return 'TRANSFER'
        elif self.value == 3:
            return 'DEFEND'
        elif self.value == 4:
            return 'TAKE'
        elif self.value == 5:
            return 'BAT'
        elif self.value == 6:
            return 'PASS'
        elif self.value == 7:
            return 'STOP_ATTACK'
        return ''


finished_action_types = (ActionType.TAKE, ActionType.BAT, ActionType.PASS, ActionType.STOP_ATTACK)


class Action:
    def __init__(self, action: ActionType = None, card: Optional[Card] = None):
        self.type = action
        self.card = card

    def __repr__(self):
        return f"{self.type} {self.card}"

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if isinstance(other, Action):
            return self.type == other.type and self.card == other.card
        return False

    def __hash__(self):
        return f'{self.type!s}{self.card!s}'.__hash__()

    def to_dict(self):
        return {'type': self.type.value, 'card': self.card.id}


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
        self.finished = False
        self.winner: Optional[int] = None
        self.player_take_mode = False
        self.opponent_take_mode = False
        self.max_card_desk = 5  # До первого бита можно подкинуть 5 карт
        self.player_known_cards: Set[Card] = set()
        self.opponent_known_cards: Set[Card] = set()

    def load_cards(self):
        if self.deck_size == 24:
            self.deck = list(all_cards_24)
        elif self.deck_size == 36:
            self.deck = list(all_cards_36)
        else:
            self.deck = list(all_cards_52)
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
            rand = random.randint(1, 2)
            if rand == 1:
                self.step = Step.PLAYER_ATTACK
            else:
                self.step = Step.OPPONENT_ATTACK
        elif my_trumps and not opponent_trumps:
            self.step = Step.PLAYER_ATTACK
        elif not my_trumps and opponent_trumps:
            self.step = Step.OPPONENT_ATTACK
        else:
            result = min(opponent_trumps) < min(my_trumps)
            if result:
                self.step = Step.OPPONENT_ATTACK
            else:
                self.step = Step.PLAYER_ATTACK

    def attack(self, card: Card):
        if self.step in (Step.PLAYER_DEFEND, Step.OPPONENT_DEFEND):
            raise IllegalStep('Cannot attack in defend step')

        if self.step == Step.PLAYER_ATTACK:
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

        self.check_win()

        if self.finished:
            return

        if self.step == Step.PLAYER_ATTACK:
            self.opponent_known_cards.discard(card)
        else:
            self.player_known_cards.discard(card)


    def defend(self, card: Card, index: Optional[int] = None):
        if self.step in (Step.PLAYER_ATTACK, Step.OPPONENT_ATTACK):
            raise IllegalStep('Cannot defend in attack step')

        if self.opponent_take_mode or self.player_take_mode:
            raise IllegalStep('You cannot defend while taking mode')
        if self.step == Step.OPPONENT_DEFEND:
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

        if self.finished:
            return

        if self.step == Step.PLAYER_DEFEND:
            self.opponent_known_cards.discard(card)
        else:
            self.player_known_cards.discard(card)

        if len(self.desk[0]) == count_cards(self.desk[1]):
            if self.step == Step.PLAYER_DEFEND:
                self.step = Step.OPPONENT_ATTACK
            else:
                self.step = Step.PLAYER_ATTACK

        if len(self.desk[1]) >= self.max_card_desk and all(self.desk[1]):
            self.bat_table()

    def bat_table(self):
        if self.step in (Step.PLAYER_DEFEND, Step.OPPONENT_DEFEND):
            raise IllegalStep('Cannot bat table in defend step')
        if not (self.desk[0] and self.desk[1] and all(self.desk[1])):
            raise IllegalStep('Not enough cards on table')

        cards = {y for x in self.desk for y in x if y}
        self.bat = self.bat.union(cards)
        self.desk = ([], [])
        if self.step == Step.PLAYER_ATTACK:
            self.player_get_cards()
            self.opponent_get_cards()
            self.step = Step.OPPONENT_ATTACK
        else:
            self.opponent_get_cards()
            self.player_get_cards()
            self.step = Step.PLAYER_ATTACK
        self.check_win()
        self.max_card_desk = 6

    def take(self):
        if self.step in (Step.PLAYER_ATTACK, Step.OPPONENT_ATTACK):
            raise IllegalStep('Cannot take in attack step')
        if self.player_take_mode or self.opponent_take_mode:
            raise IllegalStep('Take mode is actually enabled')

        if not self.desk[0]:
            raise IllegalStep('Take mode cannot be enabled when none cards in attack')

        if None not in self.desk[1]:
            raise IllegalStep('You can take cards only when there are cards not beated')

        if self.step == Step.OPPONENT_DEFEND:
            self.opponent_take_mode = True
            self.step = Step.PLAYER_ATTACK
        else:
            self.player_take_mode = True
            self.step = Step.OPPONENT_ATTACK


    def pass_cards(self):
        if not self.opponent_take_mode and not self.player_take_mode:
            raise IllegalStep('Take mode is disabled')
        if self.step in (Step.PLAYER_DEFEND, Step.OPPONENT_DEFEND):
            raise IllegalStep('Cannot pass cards in defend step')
        cards = {y for x in self.desk for y in x if y}

        if self.player_take_mode:
            self.opponent_known_cards |= cards
        else:
            self.player_known_cards |= cards

        self.desk = ([], [])
        if self.step == Step.PLAYER_ATTACK:
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

        if self.step in (Step.PLAYER_ATTACK, Step.OPPONENT_ATTACK):
            raise IllegalStep('Cannot transfer in attack step')

        if not self.desk[0]:
            raise IllegalStep("You can't transfer when none cards sent in attack")

        if any(self.desk[1]):
            raise IllegalStep('You can\'t transfer when any card has beated')

        if card.number != self.desk[0][0].number:
            raise IllegalStep("Card must be same number to transfer")

        if self.step == Step.OPPONENT_DEFEND:
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

        self.check_win()
        if self.finished:
            return

        if self.step == Step.OPPONENT_DEFEND:
            self.step = Step.OPPONENT_ATTACK
        else:
            self.step = Step.PLAYER_ATTACK


    def check_win(self):
        if self.deck:
            return
        if not self.opponent_cards and self.player_cards:
            self.finished = True
            self.winner = 1
        if not self.player_cards and self.opponent_cards:
            self.finished = True
            self.winner = 0

    def mirror(self) -> "State":
        state = deepcopy(self)
        state.player_cards = deepcopy(self.opponent_cards)
        state.opponent_cards = deepcopy(self.player_cards)
        state.player_known_cards = deepcopy(self.opponent_known_cards)
        state.opponent_known_cards = deepcopy(self.player_known_cards)
        if state.step == Step.PLAYER_ATTACK:
            state.step = Step.OPPONENT_ATTACK
        elif state.step == Step.PLAYER_DEFEND:
            state.step = Step.OPPONENT_DEFEND
        elif state.step == Step.OPPONENT_ATTACK:
            state.step = Step.PLAYER_ATTACK
        else:
            state.step = Step.PLAYER_DEFEND
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

        if self.step in (Step.PLAYER_DEFEND, Step.OPPONENT_DEFEND):
            raise IllegalStep('Cannot stop attack in defend mode')

        if self.step == Step.PLAYER_ATTACK:
            self.step = Step.OPPONENT_DEFEND
        elif self.step == Step.OPPONENT_ATTACK:
            self.step = Step.PLAYER_DEFEND

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

    def get_available_actions(self) -> list[Action]:
        """Возвращает список доступных действий"""
        available_actions = []
        if self.finished:
            return available_actions

        if self.step in (Step.OPPONENT_DEFEND, Step.OPPONENT_ATTACK):
            hand = self.opponent_cards
            opponent_hand = self.player_cards
        else:
            hand = self.player_cards
            opponent_hand = self.opponent_cards

        if self.step in (Step.PLAYER_ATTACK, Step.OPPONENT_ATTACK):
            if self.desk[0]:
                if len(self.desk[0]) > count_cards(self.desk[1]):
                    if not self.player_take_mode and not self.opponent_take_mode:
                        available_actions.append(Action(ActionType.STOP_ATTACK))
                    else:
                        available_actions.append(Action(ActionType.PASS))
                unbeat_cards = [x for i, x in enumerate(self.desk[0]) if self.desk[1][i] is None]
                if len(self.desk[0]) < self.max_card_desk and len(opponent_hand) > len(unbeat_cards):
                    desk = self.desk[0] + [x for x in self.desk[1] if x is not None]
                    numbers = {x.number for x in desk}
                    cards_available = [x for x in list(hand) if x.number in numbers]
                    [available_actions.append(Action(ActionType.ATTACK, Card(x.id, self.offset))) for x in
                     cards_available]
            else:
                [available_actions.append(Action(ActionType.ATTACK, Card(x.id, self.offset))) for x in list(hand)]
            if len(self.desk[0]) != 0 and len(self.desk[0]) == count_cards(self.desk[1]):
                available_actions.append(Action(ActionType.BAT))
        else:
            if self.step == Step.PLAYER_DEFEND and not self.player_take_mode or self.step == Step.OPPONENT_DEFEND and not self.opponent_take_mode:
                available_actions.append(Action(ActionType.TAKE))

            numbers_hand = {x.number for x in list(hand)}
            if count_cards(self.desk[1]) == 0 and self.desk[0][0].number in numbers_hand and len(opponent_hand) > len(
                    self.desk[0]):
                cards_available = {x for x in list(hand) if x.number == self.desk[0][0].number}
                [available_actions.append(Action(ActionType.TRANSFER, Card(x.id, self.offset))) for x in
                 cards_available]

            unbeat_card = None
            for i, card in enumerate(self.desk[0]):
                if self.desk[1][i] is None:
                    unbeat_card = card
                    break
            for card in list(hand):
                if ((unbeat_card.suit == card.suit and card.number > unbeat_card.number) or
                        (card.suit == self.trump.suit and unbeat_card.suit != self.trump.suit) or
                        (
                                unbeat_card.suit == self.trump.suit and card.suit == self.trump.suit and card.number > unbeat_card.number)):
                    available_actions.append(Action(ActionType.DEFEND, Card(card.id, self.offset)))

        return available_actions

    def __str__(self):
        return (f'Player cards = {self.player_cards}, opponent cards = {self.opponent_cards}, trump = {self.trump}, desk = {self.desk}, '
                f'step = {self.step}, deck = {self.deck}, player take mode = {self.player_take_mode}, '
                f'opponent take mode = {self.opponent_take_mode}, player known cards = {self.player_known_cards}, '
                f'opponent known cards = {self.opponent_known_cards}')


