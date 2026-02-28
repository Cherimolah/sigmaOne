// environment.js

class CardNumber {
    constructor(value) {
        this.value = value;
    }

    toString() {
        if (this.value < 11) {
            return this.value.toString();
        }
        switch (this.value) {
            case 11:
                return "J";
            case 12:
                return "Q";
            case 13:
                return "K";
            case 14:
                return "A";
            default:
                return this.value.toString();
        }
    }

    valueOf() {
        return this.value;
    }

    equals(other) {
        if (other instanceof CardNumber) {
            return this.value === other.value;
        }
        return this.value === other;
    }
}

class CardSuit {
    constructor(value) {
        this.value = value;
    }

    toString() {
        switch (this.value) {
            case 0:
                return "♣";
            case 1:
                return "♥";
            case 2:
                return "♠";
            case 3:
                return "♦";
            default:
                return this.value.toString();
        }
    }

    valueOf() {
        return this.value;
    }

    equals(other) {
        if (other instanceof CardSuit) {
            return this.value === other.value;
        }
        return this.value === other;
    }
}

class Card {
    constructor(id_, offset) {
        if (!(0 <= id_ && id_ <= 51)) {
            throw new Error("Id card is not correct!");
        }
        this.number = new CardNumber(Math.floor(id_ / 4) + offset);
        this.value = this.number.toString();
        this.suit = new CardSuit(id_ % 4);
        this.id = id_;
        this.name = `${this.number.toString()}${this.suit.toString()}`;
    }

    toString() {
        return this.name;
    }

    hashCode() {
        return this.id;
    }

    equals(other) {
        if (other === null || other === undefined) {
            return false;
        }
        return this.id === other.id;
    }

    clone() {
        return this; // Cards are immutable
    }

    compareTo(other) {
        if (other === null || other === undefined) {
            return 1;
        }
        return this.id - other.id;
    }
}

function countCards(cards) {
    return cards.filter(card => card !== null && card !== undefined).length;
}

const all_cards_24 = new Set(Array.from({ length: 24 }, (_, i) => new Card(i, 9)));
const all_cards_36 = new Set(Array.from({ length: 36 }, (_, i) => new Card(i, 6)));
const all_cards_52 = new Set(Array.from({ length: 52 }, (_, i) => new Card(i, 2)));

const Step = {
    PLAYER_ATTACK: 1,
    PLAYER_DEFEND: 2,
    OPPONENT_ATTACK: 3,
    OPPONENT_DEFEND: 4
};

class IllegalStep extends Error {
    constructor(message) {
        super(message);
        this.name = "IllegalStep";
    }
}

const ActionType = {
    ATTACK: 1,
    TRANSFER: 2,
    DEFEND: 3,
    TAKE: 4,
    BAT: 5,
    PASS: 6,
    STOP_ATTACK: 7
};

const finished_action_types = new Set([ActionType.TAKE, ActionType.BAT, ActionType.PASS, ActionType.STOP_ATTACK]);

class Action {
    constructor(action = null, card = null) {
        this.type = action;
        this.card = card;
    }

    toString() {
        return `${this.type} ${this.card}`;
    }

    equals(other) {
        if (other instanceof Action) {
            return this.type === other.type &&
                   (this.card === other.card ||
                    (this.card && other.card && this.card.equals(other.card)));
        }
        return false;
    }

    hashCode() {
        return `${this.type}${this.card}`.hashCode();
    }

    toDict() {
        return {
            type: this.type,
            card: this.card ? this.card.id : null
        };
    }
}

class State {
    constructor(deckSize = 36, transferable = true) {
        this.player_cards = new Set();
        this.deck = [];
        this.opponent_cards = new Set();
        this.desk = [[], []];
        this.trump = null;
        this.bat = new Set();
        this.step = null;
        this.deck_size = deckSize;
        this.transferable = transferable;

        if (this.deck_size === 24) {
            this.offset = 9;
        } else if (this.deck_size === 36) {
            this.offset = 6;
        } else {
            this.offset = 2;
        }

        this.finished = false;
        this.winner = null;
        this.player_take_mode = false;
        this.opponent_take_mode = false;
        this.max_card_desk = 5;
        this.player_known_cards = new Set();
        this.opponent_known_cards = new Set();
    }

    loadCards() {
        let cardSet;
        if (this.deck_size === 24) {
            cardSet = all_cards_24;
        } else if (this.deck_size === 36) {
            cardSet = all_cards_36;
        } else {
            cardSet = all_cards_52;
        }

        this.deck = Array.from(cardSet);
        this.shuffleArray(this.deck);
        this.trump = this.deck[this.deck.length - 1];
        this.playerGetCards();
        this.opponentGetCards();
    }

    playerGetCards() {
        while (this.player_cards.size < 6) {
            if (this.deck.length === 0) return;
            this.player_cards.add(this.deck[0]);
            this.deck.shift();
        }
    }

    opponentGetCards() {
        while (this.opponent_cards.size < 6) {
            if (this.deck.length === 0) return;
            this.opponent_cards.add(this.deck[0]);
            this.deck.shift();
        }
    }

    loadFirstStep() {
        const myTrumps = Array.from(this.player_cards)
            .filter(x => x.suit.equals(this.trump.suit))
            .map(x => x.number.valueOf());
        const opponentTrumps = Array.from(this.opponent_cards)
            .filter(x => x.suit.equals(this.trump.suit))
            .map(x => x.number.valueOf());

        if (myTrumps.length === 0 && opponentTrumps.length === 0) {
            const rand = Math.floor(Math.random() * 2) + 1;
            this.step = rand === 1 ? Step.PLAYER_ATTACK : Step.OPPONENT_ATTACK;
        } else if (myTrumps.length > 0 && opponentTrumps.length === 0) {
            this.step = Step.PLAYER_ATTACK;
        } else if (myTrumps.length === 0 && opponentTrumps.length > 0) {
            this.step = Step.OPPONENT_ATTACK;
        } else {
            const result = Math.min(...opponentTrumps) < Math.min(...myTrumps);
            this.step = result ? Step.OPPONENT_ATTACK : Step.PLAYER_ATTACK;
        }
    }

    attack(card) {
        if (this.step === Step.PLAYER_DEFEND || this.step === Step.OPPONENT_DEFEND) {
            throw new IllegalStep('Cannot attack in defend step');
        }

        let hand, opponent_hand;
        if (this.step === Step.PLAYER_ATTACK) {
            hand = this.player_cards;
            opponent_hand = this.opponent_cards;
        } else {
            hand = this.opponent_cards;
            opponent_hand = this.player_cards;
        }

        // Check if card is in hand
        let cardFound = false;
        for (const c of hand) {
            if (c.equals(card)) {
                cardFound = true;
                break;
            }
        }
        if (!cardFound) {
            throw new IllegalStep('Attack card must be in hand');
        }

        const cardNumbers = new Set([
            ...this.desk[0].filter(x => x !== null && x !== undefined).map(x => x.number.valueOf()),
            ...this.desk[1].filter(x => x !== null && x !== undefined).map(x => x.number.valueOf())
        ]);

        if (this.desk[0].length > 0 && !cardNumbers.has(card.number.valueOf())) {
            throw new IllegalStep('Card number must be in numbers at the desk');
        }

        if (this.desk[0].length >= this.max_card_desk) {
            throw new IllegalStep('Max card in attack');
        }

        const opponentCardCount = opponent_hand.size + countCards(this.desk[1]);
        if (this.desk[0].length + 1 > opponentCardCount) {
            throw new IllegalStep('Not enough cards has to defend');
        }

        this.desk[0].push(card);
        this.desk[1].push(null);

        // Remove card from hand
        const cardToRemove = Array.from(hand).find(c => c.equals(card));
        if (cardToRemove) {
            hand.delete(cardToRemove);
        }

        this.checkWin();
        if (this.finished) return;

        if (this.step === Step.PLAYER_ATTACK) {
            this.opponent_known_cards.delete(card);
        } else {
            this.player_known_cards.delete(card);
        }
    }

    defend(card, index = null) {
        if (this.step === Step.PLAYER_ATTACK || this.step === Step.OPPONENT_ATTACK) {
            throw new IllegalStep('Cannot defend in attack step');
        }

        if (this.opponent_take_mode || this.player_take_mode) {
            throw new IllegalStep('You cannot defend while taking mode');
        }

        let hand;
        if (this.step === Step.OPPONENT_DEFEND) {
            hand = this.opponent_cards;
        } else {
            hand = this.player_cards;
        }

        // Check if card is in hand
        let cardFound = false;
        for (const c of hand) {
            if (c.equals(card)) {
                cardFound = true;
                break;
            }
        }
        if (!cardFound) {
            throw new IllegalStep('Card not found in hand');
        }

        if (index === null) {
            index = this.desk[1].findIndex(c => c === null);
            if (index === -1) {
                throw new IllegalStep('No found card to defend');
            }
        }

        const attackCard = this.desk[0][index];
        const cardNumber = card.number.valueOf();
        const attackCardNumber = attackCard.number.valueOf();
        const cardSuit = card.suit.valueOf();
        const attackCardSuit = attackCard.suit.valueOf();
        const trumpSuit = this.trump.suit.valueOf();

        if ((cardSuit === attackCardSuit && cardNumber > attackCardNumber) ||
            (attackCardSuit !== trumpSuit && cardSuit === trumpSuit)) {
            this.desk[1][index] = card;

            // Remove card from hand
            const cardToRemove = Array.from(hand).find(c => c.equals(card));
            if (cardToRemove) {
                hand.delete(cardToRemove);
            }
        } else {
            throw new IllegalStep("Card is too low");
        }

        this.checkWin();
        if (this.finished) return;

        if (this.step === Step.PLAYER_DEFEND) {
            this.opponent_known_cards.delete(card);
        } else {
            this.player_known_cards.delete(card);
        }

        if (this.desk[0].length === countCards(this.desk[1])) {
            if (this.step === Step.PLAYER_DEFEND) {
                this.step = Step.OPPONENT_ATTACK;
            } else {
                this.step = Step.PLAYER_ATTACK;
            }
        }

        if (this.desk[1].length >= this.max_card_desk && this.desk[1].every(c => c !== null)) {
            this.batTable();
        }
    }

    batTable() {
        if (this.step === Step.PLAYER_DEFEND || this.step === Step.OPPONENT_DEFEND) {
            throw new IllegalStep('Cannot bat table in defend step');
        }

        if (!(this.desk[0].length > 0 && this.desk[1].length > 0 && this.desk[1].every(c => c !== null))) {
            throw new IllegalStep('Not enough cards on table');
        }

        const cards = new Set();
        for (const row of this.desk) {
            for (const card of row) {
                if (card !== null && card !== undefined) {
                    cards.add(card);
                }
            }
        }

        for (const card of cards) {
            this.bat.add(card);
        }

        this.desk = [[], []];

        if (this.step === Step.PLAYER_ATTACK) {
            this.playerGetCards();
            this.opponentGetCards();
            this.step = Step.OPPONENT_ATTACK;
        } else {
            this.opponentGetCards();
            this.playerGetCards();
            this.step = Step.PLAYER_ATTACK;
        }

        this.checkWin();
        this.max_card_desk = 6;
    }

    take() {
        if (this.step === Step.PLAYER_ATTACK || this.step === Step.OPPONENT_ATTACK) {
            throw new IllegalStep('Cannot take in attack step');
        }
        if (this.player_take_mode || this.opponent_take_mode) {
            throw new IllegalStep('Take mode is actually enabled');
        }

        if (this.desk[0].length === 0) {
            throw new IllegalStep('Take mode cannot be enabled when none cards in attack');
        }

        if (this.desk[1].every(c => c !== null)) {
            throw new IllegalStep('You can take cards only when there are cards not beated');
        }

        if (this.step === Step.OPPONENT_DEFEND) {
            this.opponent_take_mode = true;
            this.step = Step.PLAYER_ATTACK;
        } else {
            this.player_take_mode = true;
            this.step = Step.OPPONENT_ATTACK;
        }
    }

    passCards() {
        if (!this.opponent_take_mode && !this.player_take_mode) {
            throw new IllegalStep('Take mode is disabled');
        }
        if (this.step === Step.PLAYER_DEFEND || this.step === Step.OPPONENT_DEFEND) {
            throw new IllegalStep('Cannot pass cards in defend step');
        }

        const cards = new Set();
        for (const row of this.desk) {
            for (const card of row) {
                if (card !== null && card !== undefined) {
                    cards.add(card);
                }
            }
        }

        if (this.player_take_mode) {
            for (const card of cards) {
                this.opponent_known_cards.add(card);
            }
        } else {
            for (const card of cards) {
                this.player_known_cards.add(card);
            }
        }

        this.desk = [[], []];

        if (this.step === Step.PLAYER_ATTACK) {
            for (const card of cards) {
                this.opponent_cards.add(card);
            }
            this.playerGetCards();
        } else {
            for (const card of cards) {
                this.player_cards.add(card);
            }
            this.opponentGetCards();
        }

        this.checkWin();
        this.opponent_take_mode = false;
        this.player_take_mode = false;
    }

    transfer(card) {
        if (!this.transferable) {
            throw new IllegalStep("Cannot transfer in non-transferable game");
        }

        if (this.player_take_mode || this.opponent_take_mode) {
            throw new IllegalStep('Cannot transfer when take mode is enabled');
        }

        if (this.step === Step.PLAYER_ATTACK || this.step === Step.OPPONENT_ATTACK) {
            throw new IllegalStep('Cannot transfer in attack step');
        }

        if (this.desk[0].length === 0) {
            throw new IllegalStep("You can't transfer when none cards sent in attack");
        }

        if (this.desk[1].some(c => c !== null)) {
            throw new IllegalStep('You can\'t transfer when any card has beated');
        }

        if (card.number.valueOf() !== this.desk[0][0].number.valueOf()) {
            throw new IllegalStep("Card must be same number to transfer");
        }

        let hand, opposite_hand;
        if (this.step === Step.OPPONENT_DEFEND) {
            hand = this.opponent_cards;
            opposite_hand = this.player_cards;
            this.player_known_cards.delete(card);
        } else {
            hand = this.player_cards;
            opposite_hand = this.opponent_cards;
            this.opponent_known_cards.delete(card);
        }

        // Check if card is in hand
        let cardFound = false;
        for (const c of hand) {
            if (c.equals(card)) {
                cardFound = true;
                break;
            }
        }
        if (!cardFound) {
            throw new IllegalStep('Card must be in hand');
        }

        if (this.desk[0].length + 1 > opposite_hand.size) {
            throw new IllegalStep('Opponent doesn\'t have enough cards to beat');
        }

        // Remove card from hand
        const cardToRemove = Array.from(hand).find(c => c.equals(card));
        if (cardToRemove) {
            hand.delete(cardToRemove);
        }

        this.desk[0].push(card);
        this.desk[1].push(null);

        this.checkWin();
        if (this.finished) return;

        if (this.step === Step.OPPONENT_DEFEND) {
            this.step = Step.OPPONENT_ATTACK;
        } else {
            this.step = Step.PLAYER_ATTACK;
        }
    }

    checkWin() {
        if (this.deck.length > 0) return;

        if (this.opponent_cards.size === 0 && this.player_cards.size > 0) {
            this.finished = true;
            this.winner = 1;
        }
        if (this.player_cards.size === 0 && this.opponent_cards.size > 0) {
            this.finished = true;
            this.winner = 0;
        }
    }

    mirror() {
        const state = new State(this.deck_size, this.transferable);

        // Deep copy sets
        state.player_cards = new Set(Array.from(this.opponent_cards).map(card => new Card(card.id, this.offset)));
        state.opponent_cards = new Set(Array.from(this.player_cards).map(card => new Card(card.id, this.offset)));
        state.player_known_cards = new Set(Array.from(this.opponent_known_cards).map(card => new Card(card.id, this.offset)));
        state.opponent_known_cards = new Set(Array.from(this.player_known_cards).map(card => new Card(card.id, this.offset)));

        // Copy other properties
        state.deck = [...this.deck];
        state.desk = [Array.from(this.desk[0]), Array.from(this.desk[1])];
        state.trump = this.trump ? new Card(this.trump.id, this.offset) : null;
        state.bat = new Set(Array.from(this.bat).map(card => new Card(card.id, this.offset)));

        // Switch steps
        if (this.step === Step.PLAYER_ATTACK) {
            state.step = Step.OPPONENT_ATTACK;
        } else if (this.step === Step.PLAYER_DEFEND) {
            state.step = Step.OPPONENT_DEFEND;
        } else if (this.step === Step.OPPONENT_ATTACK) {
            state.step = Step.PLAYER_ATTACK;
        } else {
            state.step = Step.PLAYER_DEFEND;
        }

        // Switch take modes
        if (this.player_take_mode) {
            state.opponent_take_mode = true;
            state.player_take_mode = false;
        } else if (this.opponent_take_mode) {
            state.player_take_mode = true;
            state.opponent_take_mode = false;
        }

        state.finished = this.finished;
        state.winner = this.winner;
        state.max_card_desk = this.max_card_desk;

        return state;
    }

    stopAttack() {
        if (this.opponent_take_mode || this.player_take_mode) {
            throw new IllegalStep('Cannot stop attack while take mode is enabled');
        }
        if (countCards(this.desk[0]) === countCards(this.desk[1])) {
            throw new IllegalStep('Cannot stop attack that have not started yet or beated');
        }

        if (this.step === Step.PLAYER_DEFEND || this.step === Step.OPPONENT_DEFEND) {
            throw new IllegalStep('Cannot stop attack in defend mode');
        }

        if (this.step === Step.PLAYER_ATTACK) {
            this.step = Step.OPPONENT_DEFEND;
        } else if (this.step === Step.OPPONENT_ATTACK) {
            this.step = Step.PLAYER_DEFEND;
        }
    }

    nextStep(action) {
        if (!action) {
            console.log(this.player_cards, this.opponent_cards, this.deck, this.desk,
                        this.player_take_mode, this.opponent_take_mode, this.step);
        }

        switch (action.type) {
            case ActionType.ATTACK:
                this.attack(action.card);
                break;
            case ActionType.DEFEND:
                this.defend(action.card);
                break;
            case ActionType.BAT:
                this.batTable();
                break;
            case ActionType.PASS:
                this.passCards();
                break;
            case ActionType.TAKE:
                this.take();
                break;
            case ActionType.TRANSFER:
                this.transfer(action.card);
                break;
            case ActionType.STOP_ATTACK:
                this.stopAttack();
                break;
        }
    }

    getAvailableActions() {
        const available_actions = [];
        if (this.finished) {
            return available_actions;
        }

        let hand, opponent_hand;
        if (this.step === Step.OPPONENT_DEFEND || this.step === Step.OPPONENT_ATTACK) {
            hand = this.opponent_cards;
            opponent_hand = this.player_cards;
        } else {
            hand = this.player_cards;
            opponent_hand = this.opponent_cards;
        }

        if (this.step === Step.PLAYER_ATTACK || this.step === Step.OPPONENT_ATTACK) {
            if (this.desk[0].length > 0) {
                if (this.desk[0].length > countCards(this.desk[1])) {
                    if (!this.player_take_mode && !this.opponent_take_mode) {
                        available_actions.push(new Action(ActionType.STOP_ATTACK));
                    } else {
                        available_actions.push(new Action(ActionType.PASS));
                    }
                }

                const unbeat_cards = this.desk[0].filter((_, i) => this.desk[1][i] === null);
                if (this.desk[0].length < this.max_card_desk && opponent_hand.size > unbeat_cards.length) {
                    const desk = [...this.desk[0], ...this.desk[1].filter(c => c !== null)];
                    const numbers = new Set(desk.map(x => x.number.valueOf()));
                    const cards_available = Array.from(hand).filter(x => numbers.has(x.number.valueOf()));
                    cards_available.forEach(x =>
                        available_actions.push(new Action(ActionType.ATTACK, new Card(x.id, this.offset))));
                }
            } else {
                Array.from(hand).forEach(x =>
                    available_actions.push(new Action(ActionType.ATTACK, new Card(x.id, this.offset))));
            }

            if (this.desk[0].length !== 0 && this.desk[0].length === countCards(this.desk[1])) {
                available_actions.push(new Action(ActionType.BAT));
            }
        } else {
            if ((this.step === Step.PLAYER_DEFEND && !this.player_take_mode) ||
                (this.step === Step.OPPONENT_DEFEND && !this.opponent_take_mode)) {
                available_actions.push(new Action(ActionType.TAKE));
            }

            const numbers_hand = new Set(Array.from(hand).map(x => x.number.valueOf()));
            if (countCards(this.desk[1]) === 0 && numbers_hand.has(this.desk[0][0].number.valueOf()) &&
                opponent_hand.size > this.desk[0].length) {
                const cards_available = Array.from(hand).filter(x => x.number.valueOf() === this.desk[0][0].number.valueOf());
                cards_available.forEach(x =>
                    available_actions.push(new Action(ActionType.TRANSFER, new Card(x.id, this.offset))));
            }

            let unbeat_card = null;
            for (let i = 0; i < this.desk[0].length; i++) {
                if (this.desk[1][i] === null) {
                    unbeat_card = this.desk[0][i];
                    break;
                }
            }

            const trumpSuitValue = this.trump.suit.valueOf();
            const unbeatCardSuitValue = unbeat_card.suit.valueOf();

            Array.from(hand).forEach(card => {
                const cardSuitValue = card.suit.valueOf();
                const cardNumberValue = card.number.valueOf();
                const unbeatCardNumberValue = unbeat_card.number.valueOf();

                if ((cardSuitValue === unbeatCardSuitValue && cardNumberValue > unbeatCardNumberValue) ||
                    (cardSuitValue === trumpSuitValue && unbeatCardSuitValue !== trumpSuitValue) ||
                    (unbeatCardSuitValue === trumpSuitValue && cardSuitValue === trumpSuitValue &&
                     cardNumberValue > unbeatCardNumberValue)) {
                    available_actions.push(new Action(ActionType.DEFEND, new Card(card.id, this.offset)));
                }
            });
        }

        return available_actions;
    }

    toString() {
        return `Player cards = ${Array.from(this.player_cards)}, opponent cards = ${Array.from(this.opponent_cards)}, trump = ${this.trump}, desk = ${JSON.stringify(this.desk)}, ` +
               `step = ${this.step}, deck = ${this.deck}, player take mode = ${this.player_take_mode}, ` +
               `opponent take mode = ${this.opponent_take_mode}, player known cards = ${Array.from(this.player_known_cards)}, ` +
               `opponent known cards = ${Array.from(this.opponent_known_cards)}`;
    }

    // Helper method to shuffle array
    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
    }
}

// Add hashCode method to String prototype for compatibility
String.prototype.hashCode = function() {
    let hash = 0;
    for (let i = 0; i < this.length; i++) {
        const char = this.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return hash;
};
