class Game {
    constructor() {
        this.gameState = new State(24, true);
        this.selectedCard = null;
        this.isAIThinking = false;
        this.eventSource = null;

        this.initEventListeners();
        this.startNewGame();
    }

    initEventListeners() {
        // Кнопка начала игры
        document.getElementById('start-game').addEventListener('click', () => {
            document.getElementById('welcome-screen').classList.remove('active');
            document.getElementById('game-screen').classList.add('active');
        });

        // Кнопка новой игры
        document.getElementById('new-game-btn').addEventListener('click', () => {
            this.startNewGame();
        });

        // Кнопка сдачи
        document.getElementById('surrender-btn').addEventListener('click', () => {
            if (confirm('Вы уверены, что хотите сдаться?')) {
                this.showGameOver('AI выиграл!');
            }
        });

        // Основная кнопка действия
        document.getElementById('action-btn').addEventListener('click', () => {
            this.handleActionButton();
        });

        // Кнопка перевода
        document.getElementById('transfer-btn').addEventListener('click', () => {
            if (this.selectedCard) {
                this.transferCard(this.selectedCard);
            }
        });

        // Кнопка отбития
        document.getElementById('defend-btn').addEventListener('click', () => {
            if (this.selectedCard) {
                this.defendCard(this.selectedCard);
            }
        });
    }

    startNewGame() {
        this.gameState = new State(24, true);
        this.gameState.loadCards();
        this.gameState.loadFirstStep();
        this.selectedCard = null;

        this.updateUI();
        this.updateActionButtons();

        // Если первым ходит ИИ
        if (this.gameState.step === Step.OPPONENT_ATTACK) {
            this.aiMove();
        }
    }

    updateUI() {
        // Обновляем счетчики карт
        document.getElementById('player-card-count').textContent =
            `${this.gameState.playerCards.size} карт`;
        document.getElementById('ai-card-count').textContent =
            `${this.gameState.opponentCards.size} карт`;
        document.getElementById('deck-count').textContent =
            this.gameState.deck.length > 0 ? this.gameState.deck.length : '';

        // Обновляем козырную карту
        const trumpCard = document.getElementById('trump-card');
        if (this.gameState.deck.length > 0) {
            trumpCard.style.background = `linear-gradient(45deg, white, #f0f0f0)`;
            trumpCard.innerHTML = `
                <div style="transform: rotate(-90deg); font-size: 1.5rem; color: ${this.gameState.trump.color};">
                    ${this.gameState.trump.value}${this.gameState.trump.suit}
                </div>
            `;
        } else {
            trumpCard.innerHTML = `<div style="font-size: 3rem; color: ${this.gameState.trump.color};">${this.gameState.trump.suit}</div>`;
        }

        // Обновляем бито
        const batPile = document.getElementById('bat-pile');
        if (this.gameState.bat.size > 0) {
            batPile.classList.add('visible');
        } else {
            batPile.classList.remove('visible');
        }

        // Обновляем карты игрока
        this.renderPlayerHand();

        // Обновляем карты на столе
        this.renderDesk();

        // Обновляем статус игры
        if (this.gameState.finished) {
            const winnerText = this.gameState.winner === 1 ?
                'Вы выиграли!' : 'AI выиграл!';
            this.showGameOver(winnerText);
        }
    }

    renderPlayerHand() {
        const handContainer = document.getElementById('hand-container');
        handContainer.innerHTML = '';

        const cards = Array.from(this.gameState.playerCards).sort((a, b) => a.id - b.id);

        cards.forEach(card => {
            const cardElement = document.createElement('div');
            cardElement.className = 'card';
            if (this.selectedCard && this.selectedCard.id === card.id) {
                cardElement.classList.add('selected');
            }

            cardElement.innerHTML = `
                <div class="card-front" style="color: ${card.color};">
                    <div class="card-value">${card.value}</div>
                    <div class="card-suit">${card.suit}</div>
                </div>
            `;

            cardElement.addEventListener('click', () => {
                this.selectCard(card);
            });

            handContainer.appendChild(cardElement);
        });
    }

    renderDesk() {
        const deskGrid = document.getElementById('desk-grid');
        deskGrid.innerHTML = '';

        // Создаем 6 ячеек для карт
        for (let i = 0; i < 6; i++) {
            const cell = document.createElement('div');
            cell.className = 'desk-cell';
            cell.dataset.index = i;
            deskGrid.appendChild(cell);
        }

        // Отображаем карты на столе
        for (let i = 0; i < this.gameState.desk[0].length; i++) {
            const attackCard = this.gameState.desk[0][i];
            const defendCard = this.gameState.desk[1][i];

            if (attackCard) {
                this.addCardToDesk(attackCard, i, 'attack');
            }
            if (defendCard) {
                this.addCardToDesk(defendCard, i, 'defend');
            }
        }
    }

    addCardToDesk(card, position, type) {
        const cells = document.querySelectorAll('.desk-cell');
        const cell = cells[position];

        const cardElement = document.createElement('div');
        cardElement.className = `desk-card ${type}`;
        cardElement.innerHTML = `
            <div class="card-front" style="color: ${card.color};">
                <div class="card-value">${card.value}</div>
                <div class="card-suit">${card.suit}</div>
            </div>
        `;

        cell.appendChild(cardElement);
    }

    selectCard(card) {
        if (this.isAIThinking) return;

        if (this.selectedCard && this.selectedCard.id === card.id) {
            this.selectedCard = null;
        } else {
            this.selectedCard = card;
        }

        this.renderPlayerHand();
        this.updateActionButtons();
    }

    updateActionButtons() {
        const actionBtn = document.getElementById('action-btn');
        const transferBtn = document.getElementById('transfer-btn');
        const defendBtn = document.getElementById('defend-btn');

        // Сбрасываем все кнопки
        actionBtn.classList.add('hidden');
        transferBtn.classList.add('hidden');
        defendBtn.classList.add('hidden');
        actionBtn.innerHTML = '';

        // Получаем доступные действия для игрока
        const availableActions = this.gameState.getAvailableActions();

        // Проверяем текущий шаг
        if (this.gameState.step === Step.PLAYER_ATTACK) {
            // Игрок атакует
            if (this.selectedCard) {
                const canAttack = this.gameState.canAttack(this.selectedCard);
                if (canAttack) {
                    actionBtn.innerHTML = '<i class="fas fa-fist-raised"></i> Атаковать';
                    actionBtn.classList.remove('hidden');
                }
            }

            // Проверяем можно ли прекратить атаку
            const canStopAttack = availableActions.some(a => a.type === ActionType.STOP_ATTACK);
            if (canStopAttack) {
                actionBtn.innerHTML = '<i class="fas fa-hand-paper"></i> Прекратить атаку';
                actionBtn.classList.remove('hidden');
            }

            // Проверяем можно ли сказать "Бито"
            const canBat = availableActions.some(a => a.type === ActionType.BAT);
            if (canBat) {
                actionBtn.innerHTML = '<i class="fas fa-check"></i> Бито';
                actionBtn.classList.remove('hidden');
            }
        }
        else if (this.gameState.step === Step.PLAYER_DEFEND) {
            // Игрок защищается
            if (this.gameState.playerTakeMode) {
                // Режим взятия карт - можно отдать
                actionBtn.innerHTML = '<i class="fas fa-hand-holding"></i> Отдать';
                actionBtn.classList.remove('hidden');
            } else {
                // Обычная защита
                if (this.selectedCard) {
                    const canDefend = this.gameState.canDefend(this.selectedCard);
                    if (canDefend) {
                        defendBtn.innerHTML = `<i class="fas fa-shield-alt"></i> Отбить ${this.selectedCard.value}${this.selectedCard.suit}`;
                        defendBtn.classList.remove('hidden');
                    }
                }

                // Кнопка "Взять"
                actionBtn.innerHTML = '<i class="fas fa-hand-rock"></i> Взять';
                actionBtn.classList.remove('hidden');

                // Кнопка "Перевести"
                const canTransfer = availableActions.some(a => a.type === ActionType.TRANSFER);
                if (canTransfer && this.selectedCard) {
                    const canTransferWithCard = this.gameState.desk[0].length > 0 &&
                        this.gameState.desk[0][0].number.value === this.selectedCard.number.value;
                    if (canTransferWithCard) {
                        transferBtn.innerHTML = `<i class="fas fa-exchange-alt"></i> Перевести ${this.selectedCard.value}${this.selectedCard.suit}`;
                        transferBtn.classList.remove('hidden');
                    }
                }
            }
        }
    }

    handleActionButton() {
        if (this.isAIThinking) return;

        const actionBtn = document.getElementById('action-btn');
        const btnText = actionBtn.textContent;

        if (btnText.includes('Атаковать') && this.selectedCard) {
            this.attackWithCard(this.selectedCard);
        }
        else if (btnText.includes('Прекратить атаку')) {
            this.stopAttack();
        }
        else if (btnText.includes('Бито')) {
            this.batTable();
        }
        else if (btnText.includes('Взять')) {
            this.takeCards();
        }
        else if (btnText.includes('Отдать')) {
            this.passCards();
        }
    }

    attackWithCard(card) {
        try {
            this.gameState.attack(card);
            this.selectedCard = null;
            this.updateUI();
            this.updateActionButtons();

            // Проверяем нужно ли передать ход ИИ
            if (this.gameState.step === Step.OPPONENT_DEFEND) {
                this.aiMove();
            }
        } catch (error) {
            alert(error.message);
        }
    }

    defendCard(card) {
        try {
            this.gameState.defend(card);
            this.selectedCard = null;
            this.updateUI();
            this.updateActionButtons();

            // Если все карты отбиты, передаем ход ИИ
            const allDefended = this.gameState.desk[1].every(c => c !== null);
            if (allDefended && this.gameState.step === Step.PLAYER_ATTACK) {
                this.aiMove();
            }
        } catch (error) {
            alert(error.message);
        }
    }

    transferCard(card) {
        try {
            this.gameState.transfer(card);
            this.selectedCard = null;
            this.updateUI();
            this.updateActionButtons();

            // После перевода ход у ИИ
            this.aiMove();
        } catch (error) {
            alert(error.message);
        }
    }

    stopAttack() {
        try {
            this.gameState.stopAttack();
            this.updateUI();
            this.updateActionButtons();

            // После остановки атаки ИИ защищается
            this.aiMove();
        } catch (error) {
            alert(error.message);
        }
    }

    batTable() {
        try {
            this.gameState.batTable();
            this.updateUI();
            this.updateActionButtons();

            // После "Бито" ход у ИИ (если это был ход игрока)
            if (this.gameState.step === Step.OPPONENT_ATTACK) {
                this.aiMove();
            }
        } catch (error) {
            alert(error.message);
        }
    }

    takeCards() {
        try {
            this.gameState.take();
            this.updateUI();
            this.updateActionButtons();

            // После взятия карт ИИ может подкинуть
            this.aiMove();
        } catch (error) {
            alert(error.message);
        }
    }

    passCards() {
        try {
            // В данном контексте "Отдать" это передать карты (PASS)
            // Нужно будет реализовать логику передачи карт
            alert('Функция отдачи карт в разработке');
        } catch (error) {
            alert(error.message);
        }
    }

    async aiMove() {
        if (this.isAIThinking || this.gameState.finished) return;

        this.isAIThinking = true;
        this.showLoading(true);

        try {
            const stateForAI = this.gameState.getStateForAI();

            // Отправляем запрос к ИИ
            const response = await this.sendToAI(stateForAI);

            // Применяем действие ИИ
            this.applyAIAction(response.action);

        } catch (error) {
            console.error('Ошибка при запросе к ИИ:', error);
            alert('Ошибка соединения с ИИ');
        } finally {
            this.isAIThinking = false;
            this.showLoading(false);
            this.updateUI();
            this.updateActionButtons();
        }
    }

    async sendToAI(state) {
        return new Promise((resolve, reject) => {
            // Здесь будет реализация SSE запроса к /predict
            // Временно используем заглушку
            setTimeout(() => {
                // Имитируем ответ ИИ
                const actions = this.gameState.getAvailableActions();
                if (actions.length > 0) {
                    // Выбираем случайное доступное действие
                    const randomAction = actions[Math.floor(Math.random() * actions.length)];
                    resolve({
                        action: {
                            type: randomAction.type,
                            card: randomAction.card ? randomAction.card.toServerId() : null
                        }
                    });
                } else {
                    reject(new Error('Нет доступных действий'));
                }
            }, 1000);
        });
    }

    applyAIAction(action) {
        const { type, card } = action;

        try {
            switch (type) {
                case ActionType.ATTACK:
                    const attackCard = this.findCardById(card);
                    this.gameState.attack(attackCard);
                    break;

                case ActionType.DEFEND:
                    const defendCard = this.findCardById(card);
                    this.gameState.defend(defendCard);
                    break;

                case ActionType.TRANSFER:
                    const transferCard = this.findCardById(card);
                    this.gameState.transfer(transferCard);
                    break;

                case ActionType.TAKE:
                    this.gameState.take();
                    break;

                case ActionType.BAT:
                    this.gameState.batTable();
                    break;

                case ActionType.PASS:
                    // Обработка передачи карт
                    break;

                case ActionType.STOP_ATTACK:
                    this.gameState.stopAttack();
                    break;
            }
        } catch (error) {
            console.error('Ошибка при применении действия ИИ:', error);
        }
    }

    findCardById(id) {
        // Ищем карту по ID во всех возможных местах
        const allCards = [
            ...this.gameState.opponentCards,
            ...this.gameState.playerCards,
            ...this.gameState.deck,
            ...this.gameState.desk[0],
            ...this.gameState.desk[1].filter(c => c !== null),
            ...this.gameState.bat
        ];

        return allCards.find(card => card && card.toServerId() === id);
    }

    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');

        if (show) {
            overlay.classList.remove('hidden');
            let progress = 0;
            const interval = setInterval(() => {
                progress += Math.random() * 20;
                if (progress > 100) progress = 100;
                progressBar.style.width = `${progress}%`;
                progressText.textContent = `Попытка ${Math.floor(progress / 10) + 1} из 10`;

                if (progress >= 100) {
                    clearInterval(interval);
                }
            }, 200);
        } else {
            overlay.classList.add('hidden');
            progressBar.style.width = '0%';
        }
    }

    showGameOver(message) {
        const overlay = document.createElement('div');
        overlay.className = 'overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <h2>Игра окончена!</h2>
                <p style="font-size: 1.5rem; margin: 1rem 0;">${message}</p>
                <button id="restart-btn" class="btn-primary" style="margin-top: 2rem;">
                    <i class="fas fa-redo"></i> Новая игра
                </button>
            </div>
        `;

        document.body.appendChild(overlay);

        document.getElementById('restart-btn').addEventListener('click', () => {
            document.body.removeChild(overlay);
            this.startNewGame();
        });
    }
}

// Инициализация игры при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.game = new Game();
});