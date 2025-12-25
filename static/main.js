
let selectedPlayers = new Set();
let currentTournament = null;
let currentRound = null;
let currentMatches = [];
window.addEventListener('scroll', () => {
    const navbar = document.getElementById('navbar');
    if (window.scrollY > 10) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});
function showAlert(message, type = 'success') {
    const container = document.getElementById('alert-container');
    const alert = document.createElement('div');
    const icons = {
        success: '✓',
        error: '✕',
        info: 'ℹ',
        warning: '⚠'
    };
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `<span style="font-size: 18px;">${icons[type] || icons.info}</span><span>${message}</span>`;
    alert.style.cssText = 'animation: slideInRight 0.4s cubic-bezier(0.28, 0.11, 0.32, 1);';
    container.appendChild(alert);
    setTimeout(() => {
        alert.style.animation = 'slideOutRight 0.3s cubic-bezier(0.28, 0.11, 0.32, 1)';
        setTimeout(() => alert.remove(), 300);
    }, 4000);
}
function showModal(id) {
    document.getElementById(id).classList.add('active');
    document.body.style.overflow = 'hidden';
}
function closeModal(id) {
    document.getElementById(id).classList.remove('active');
    document.body.style.overflow = '';
}
function showAddPlayerModal() {
    document.getElementById('player-name-input').value = '';
    showModal('add-player-modal');
}
function showCreateTournamentModal() {
    document.getElementById('tournament-name-input').value = '';
    showModal('create-tournament-modal');
}
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal(modal.id);
        }
    });
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            closeModal(modal.id);
        });
    }
});
async function apiCall(url, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) options.body = JSON.stringify(data);
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Request failed');
        }
        return result;
    } catch (error) {
        showAlert(error.message, 'error');
        throw error;
    }
}
async function loadPlayers() {
    try {
        const players = await apiCall('/api/players');
        const list = document.getElementById('players-list');
        list.innerHTML = '';
        if (players.length === 0) {
            list.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">👤</div>
                            <div class="empty-state-text">No players added yet</div>
                        </div>
                    `;
            return;
        }
        players.forEach(player => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.innerHTML = `
                        <span style="font-weight: 500;">${player.name}</span>
                        <small style="color: var(--text-secondary); font-size: 13px;">${player.short_id}...</small>
                    `;
            div.onclick = () => togglePlayerSelection(player.id, div);
            list.appendChild(div);
        });
    } catch (error) {
        console.error('Failed to load players:', error);
    }
}
function togglePlayerSelection(playerId, element) {
    if (selectedPlayers.has(playerId)) {
        selectedPlayers.delete(playerId);
        element.classList.remove('selected');
    } else {
        selectedPlayers.add(playerId);
        element.classList.add('selected');
    }
}
async function createPlayer() {
    const name = document.getElementById('player-name-input').value.trim();
    if (!name) {
        showAlert('Please enter a player name', 'error');
        return;
    }
    try {
        await apiCall('/api/players', 'POST', { name });
        closeModal('add-player-modal');
        showAlert(`Player "${name}" added successfully`, 'success');
        await loadPlayers();
    } catch (error) {
        console.error('Failed to create player:', error);
    }
}
document.getElementById('player-name-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        createPlayer();
    }
});
async function loadTournaments() {
    try {
        const tournaments = await apiCall('/api/tournaments');
        const list = document.getElementById('tournaments-list');
        list.innerHTML = '';
        if (tournaments.length === 0) {
            list.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">🏅</div>
                            <div class="empty-state-text">No tournaments created yet</div>
                        </div>
                    `;
            return;
        }
        tournaments.forEach(tournament => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.innerHTML = `
                        <span style="font-weight: 500;">${tournament.name}</span>
                        <small style="color: var(--text-secondary); font-size: 13px;">${tournament.short_id}...</small>
                    `;
            div.onclick = () => loadTournament(tournament.id, div);
            list.appendChild(div);
        });
    } catch (error) {
        console.error('Failed to load tournaments:', error);
    }
}
async function loadTournament(tournamentId, element) {
    try {
        document.querySelectorAll('#tournaments-list .list-item').forEach(el => {
            el.classList.remove('selected');
        });
        element.classList.add('selected');
        currentTournament = tournamentId;
        const tournament = await apiCall(`/api/tournaments/${tournamentId}`);
        const list = document.getElementById('tournament-players-list');
        list.innerHTML = '';
        if (tournament.players.length === 0) {
            list.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-text">No players in this tournament</div>
                        </div>
                    `;
        } else {
            tournament.players.forEach(player => {
                const div = document.createElement('div');
                div.className = 'list-item';
                const status = player.able_to_play ? 'active' : 'eliminated';
                const symbol = player.able_to_play ? '✓' : '✗';
                div.innerHTML = `
                            <span style="font-weight: 500;">${player.name}</span>
                            <span class="badge badge-${status}">${symbol} ${status.toUpperCase()}</span>
                        `;
                list.appendChild(div);
            });
        }
        document.getElementById('add-players-btn').disabled = false;
        document.getElementById('create-round-btn').disabled = false;
        await loadRounds();
        showAlert('Tournament loaded successfully', 'success');
    } catch (error) {
        console.error('Failed to load tournament:', error);
    }
}
async function createTournament() {
    const name = document.getElementById('tournament-name-input').value.trim();
    if (!name) {
        showAlert('Please enter a tournament name', 'error');
        return;
    }
    try {
        await apiCall('/api/tournaments', 'POST', { name });
        closeModal('create-tournament-modal');
        showAlert(`Tournament "${name}" created successfully`, 'success');
        await loadTournaments();
    } catch (error) {
        console.error('Failed to create tournament:', error);
    }
}
document.getElementById('tournament-name-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        createTournament();
    }
});
async function addPlayersToTournament() {
    if (!currentTournament) {
        showAlert('Please select a tournament first', 'warning');
        return;
    }
    if (selectedPlayers.size === 0) {
        showAlert('Please select at least one player', 'warning');
        return;
    }
    try {
        await apiCall(`/api/tournaments/${currentTournament}/players`, 'POST', {
            player_ids: Array.from(selectedPlayers)
        });
        showAlert(`${selectedPlayers.size} player(s) added to tournament`, 'success');
        selectedPlayers.clear();
        document.querySelectorAll('#players-list .list-item').forEach(el => {
            el.classList.remove('selected');
        });
        const selectedTournament = document.querySelector('#tournaments-list .list-item.selected');
        if (selectedTournament) {
            await loadTournament(currentTournament, selectedTournament);
        }
    } catch (error) {
        console.error('Failed to add players:', error);
    }
}
async function loadCalculators() {
    try {
        const calculators = await apiCall('/api/calculators');
        const select = document.getElementById('calculator-select');
        select.innerHTML = calculators.map(c =>
            `<option value="${c}">${c}</option>`
        ).join('');
    } catch (error) {
        console.error('Failed to load calculators:', error);
    }
}
async function setCalculator() {
    if (!currentTournament) {
        showAlert('Please select a tournament first', 'warning');
        return;
    }
    try {
        const calculator = document.getElementById('calculator-select').value;
        await apiCall(`/api/tournaments/${currentTournament}/calculator`, 'POST', { calculator });
        showAlert(`Calculator set to "${calculator}"`, 'success');
    } catch (error) {
        console.error('Failed to set calculator:', error);
    }
}
async function loadStrategies() {
    try {
        const strategies = await apiCall('/api/strategies');
        const select = document.getElementById('strategy-select');
        select.innerHTML = strategies.map(s =>
            `<option value="${s}">${s}</option>`
        ).join('');
    } catch (error) {
        console.error('Failed to load strategies:', error);
    }
}
async function loadRounds() {
    if (!currentTournament) return;
    try {
        const rounds = await apiCall(`/api/tournaments/${currentTournament}/rounds`);
        const list = document.getElementById('rounds-list');
        list.innerHTML = '';
        if (rounds.length === 0) {
            list.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-text">No rounds created yet</div>
                        </div>
                    `;
            return;
        }
        rounds.forEach(round => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.innerHTML = `
                        <span style="font-weight: 500;">Round #${round.ordinal} - ${round.round_type}</span>
                        <small style="color: var(--text-secondary); font-size: 13px;">${round.short_id}...</small>
                    `;
            div.onclick = () => selectRound(round.id, div);
            list.appendChild(div);
        });
    } catch (error) {
        console.error('Failed to load rounds:', error);
    }
}
function selectRound(roundId, element) {
    document.querySelectorAll('#rounds-list .list-item').forEach(el => {
        el.classList.remove('selected');
    });
    element.classList.add('selected');
    currentRound = roundId;
    document.getElementById('load-round-btn').disabled = false;
}
async function createRound() {
    if (!currentTournament) {
        showAlert('Please select a tournament first', 'warning');
        return;
    }
    try {
        const strategy = document.getElementById('strategy-select').value;
        const playersPerMatch = parseInt(document.getElementById('players-per-match').value);
        if (playersPerMatch < 2 || playersPerMatch > 10) {
            showAlert('Players per match must be between 2 and 10', 'error');
            return;
        }
        const result = await apiCall(`/api/tournaments/${currentTournament}/rounds`, 'POST', {
            strategy,
            players_per_match: playersPerMatch
        });
        showAlert(`Round #${result.ordinal} created with ${result.matches} match(es)`, 'success');
        await loadRounds();
        const selectedTournament = document.querySelector('#tournaments-list .list-item.selected');
        if (selectedTournament) {
            await loadTournament(currentTournament, selectedTournament);
        }
    } catch (error) {
        console.error('Failed to create round:', error);
    }
}
async function loadRoundMatches() {
    if (!currentRound) {
        showAlert('Please select a round first', 'warning');
        return;
    }
    await showMatches();
}
async function showMatches() {
    if (!currentRound) {
        showAlert('Please select a round first', 'warning');
        return;
    }
    try {
        const data = await apiCall(`/api/rounds/${currentRound}/matches`);
        currentMatches = data.matches;
        const display = document.getElementById('display-area');
        let html = `
                    <h3 class="display-heading">
                        Matches — ${data.round_type.toUpperCase()}
                    </h3>
                `;
        if (data.round_type === 'knockout') {
            html += `
                        <div class="alert alert-error" style="margin-bottom: 20px;">
                            <span style="font-size: 18px;">⚠</span>
                            <span>Warning: Losers will be eliminated from the tournament</span>
                        </div>
                    `;
        }
        if (currentMatches.length === 0) {
            html += `
                        <div class="empty-state">
                            <div class="empty-state-icon">🎮</div>
                            <div class="empty-state-text">No matches in this round</div>
                        </div>
                    `;
        } else {
            html += '<div class="matches-container">';
            currentMatches.forEach((match, index) => {
                const statusClass = match.status === 'pending' ? 'pending' : 'completed';
                html += `
                            <div class="match-card">
                                <div class="match-header">Match ${index + 1}</div>
                                <div class="match-players">${match.player_names.join(' vs ')}</div>
                                <div style="margin-top: 12px;">
                                    <span class="badge badge-${statusClass}">
                                        ${match.status === 'pending' ? '⏱' : '✓'}
                                        ${match.status_text}
                                    </span>
                                </div>
                                ${match.eliminated_names.length > 0 ? `
                                    <div style="margin-top: 14px; color: var(--apple-red); font-size: 14px; font-weight: 500;">
                                        <span style="margin-right: 6px;">🚫</span>
                                        Eliminated: ${match.eliminated_names.join(', ')}
                                    </div>
                                ` : ''}
                                ${match.status === 'pending' && !match.auto_bye ? `
                                    <button class="btn btn-success" onclick="showRecordResultModal('${match.id}', ${match.players_per_match})" style="margin-top: 16px;">
                                        Record Result
                                    </button>
                                ` : ''}
                            </div>
                        `;
            });
            html += '</div>';
        }
        display.innerHTML = html;
    } catch (error) {
        console.error('Failed to show matches:', error);
    }
}
async function showStandings() {
    if (!currentTournament) {
        showAlert('Please select a tournament first', 'warning');
        return;
    }
    try {
        const standings = await apiCall(`/api/tournaments/${currentTournament}/standings`);
        const display = document.getElementById('display-area');
        let html = '<h3 class="display-heading">Tournament Standings</h3>';
        if (standings.length === 0) {
            html += `
                        <div class="empty-state">
                            <div class="empty-state-icon">📊</div>
                            <div class="empty-state-text">No statistics available yet</div>
                        </div>
                    `;
        } else {
            const totalMatches = standings.reduce((sum, s) => sum + s.matches_played, 0);
            const totalPlayers = standings.length;
            const avgPoints = standings.reduce((sum, s) => sum + s.points, 0) / totalPlayers;
            html += `
                        <div class="stats-grid" style="margin-bottom: 28px;">
                            <div class="stat-card">
                                <div class="stat-value">${totalPlayers}</div>
                                <div class="stat-label">Players</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${totalMatches}</div>
                                <div class="stat-label">Matches</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${avgPoints.toFixed(1)}</div>
                                <div class="stat-label">Avg Points</div>
                            </div>
                        </div>
                    `;
            html += `
                        <table class="standings-table">
                            <thead>
                                <tr>
                                    <th>Rank</th>
                                    <th>Player</th>
                                    <th>Points</th>
                                    <th>W</th>
                                    <th>D</th>
                                    <th>L</th>
                                    <th>Played</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
            standings.forEach((stat, index) => {
                const rankEmoji = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
                const appear = index > 2 ? stat.rank : rankEmoji
                html += `
                            <tr>
                                <td>
                                    <strong style="color: var(--apple-blue); font-size: 17px;">
                                        ${appear}
                                    </strong>
                                </td>
                                <td><strong style="font-size: 16px;">${stat.name}</strong></td>
                                <td><strong style="color: var(--apple-purple); font-size: 16px;">${stat.points.toFixed(1)}</strong></td>
                                <td><span style="color: var(--apple-green);">${stat.wins}</span></td>
                                <td><span style="color: var(--apple-orange);">${stat.draws}</span></td>
                                <td><span style="color: var(--apple-red);">${stat.losses}</span></td>
                                <td>${stat.matches_played}</td>
                            </tr>
                        `;
            });
            html += '</tbody></table>';
        }
        display.innerHTML = html;
    } catch (error) {
        console.error('Failed to show standings:', error);
    }
}
function showRecordResultModal(matchId, playersPerMatch) {
    const match = currentMatches.find(m => m.id === matchId);
    if (!match) return;
    const modal = document.getElementById('record-result-modal');
    const title = document.getElementById('result-modal-title');
    const content = document.getElementById('result-modal-content');
    title.textContent = 'Record Match Result';
    if (playersPerMatch === 2) {
        content.innerHTML = `
                    <div style="margin-bottom: 24px;">
                        <strong style="font-size: 19px; letter-spacing: -0.01em; display: block; text-align: center;">
                            ${match.player_names[0]} <span style="color: var(--text-secondary);">vs</span> ${match.player_names[1]}
                        </strong>
                    </div>
                    <div class="radio-group">
                        <label class="radio-option">
                            <input type="radio" name="result" value="win1">
                            <span>${match.player_names[0]} wins</span>
                        </label>
                        <label class="radio-option">
                            <input type="radio" name="result" value="win2">
                            <span>${match.player_names[1]} wins</span>
                        </label>
                        <label class="radio-option">
                            <input type="radio" name="result" value="draw">
                            <span>Draw / Tie</span>
                        </label>
                    </div>
                    <button class="btn btn-primary" onclick="submitMatchResult('${matchId}', ${playersPerMatch})">
                        Submit Result
                    </button>
                    <button class="btn btn-secondary" onclick="closeModal('record-result-modal')">
                        Cancel
                    </button>
                `;
    } else {
        let html = `
                    <div style="margin-bottom: 24px;">
                        <strong style="font-size: 17px; display: block; margin-bottom: 8px;">
                            Enter finishing position for each player:
                        </strong>
                        <p style="font-size: 14px; color: var(--text-secondary); line-height: 1.5;">
                            1st place gets the most points, last place gets the least.
                        </p>
                    </div>
                `;
        match.player_names.forEach((name, index) => {
            html += `
                        <div class="input-group">
                            <label>${name}</label>
                            <select id="rank-${match.player_ids[index]}">
                                ${Array.from({ length: playersPerMatch }, (_, i) =>
                `<option value="${i + 1}" ${i === index ? 'selected' : ''}>
                                        ${i + 1}${i === 0 ? 'st' : i === 1 ? 'nd' : i === 2 ? 'rd' : 'th'} Place
                                    </option>`
            ).join('')}
                            </select>
                        </div>
                    `;
        });
        html += `
                    <button class="btn btn-primary" onclick="submitMatchResult('${matchId}', ${playersPerMatch})">
                        Submit Result
                    </button>
                    <button class="btn btn-secondary" onclick="closeModal('record-result-modal')">
                        Cancel
                    </button>
                `;
        content.innerHTML = html;
    }
    showModal('record-result-modal');
}
async function submitMatchResult(matchId, playersPerMatch) {
    const match = currentMatches.find(m => m.id === matchId);
    if (!match) return;
    let resultData;
    try {
        if (playersPerMatch === 2) {
            const selected = document.querySelector('input[name="result"]:checked');
            if (!selected) {
                showAlert('Please select a result', 'error');
                return;
            }
            const value = selected.value;
            if (value === 'draw') {
                resultData = { result_type: 'draw' };
            } else if (value === 'win1') {
                resultData = { result_type: 'win', winner_id: match.player_ids[0] };
            } else {
                resultData = { result_type: 'win', winner_id: match.player_ids[1] };
            }
        } else {
            const rankings = {};
            for (let playerId of match.player_ids) {
                const rank = document.getElementById(`rank-${playerId}`).value;
                rankings[playerId] = rank;
            }
            const ranks = Object.values(rankings);
            if (new Set(ranks).size !== ranks.length) {
                showAlert('Each player must have a unique finishing position', 'error');
                return;
            }
            resultData = { result_type: 'rankings', rankings };
        }
        await apiCall(`/api/matches/${matchId}/result`, 'POST', resultData);
        closeModal('record-result-modal');
        showAlert('Match result recorded successfully', 'success');
        await showMatches();
        const selectedTournament = document.querySelector('#tournaments-list .list-item.selected');
        if (selectedTournament) {
            await loadTournament(currentTournament, selectedTournament);
        }
    } catch (error) {
        console.error('Failed to submit match result:', error);
    }
}
async function reloadPlugins() {
    try {
        await apiCall('/api/plugins/reload', 'POST');
        await loadStrategies();
        await loadCalculators();
        showAlert('Plugins reloaded successfully', 'success');
    } catch (error) {
        console.error('Failed to reload plugins:', error);
    }
}
document.addEventListener('keydown', (e) => {
    if (e.altKey && e.key === 'p') {
        e.preventDefault();
        showAddPlayerModal();
    }
    if (e.altKey && e.key === 't') {
        e.preventDefault();
        showCreateTournamentModal();
    }
    if (e.altKey && e.key === 'r') {
        e.preventDefault();
        if (!document.getElementById('create-round-btn').disabled) {
            createRound();
        }
    }
    if (e.altKey && e.key === 's') {
        e.preventDefault();
        if (currentTournament) {
            showStandings();
        }
    }
    if (e.altKey && e.key === 'm') {
        e.preventDefault();
        if (currentRound) {
            showMatches();
        }
    }
});
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
const formInputs = ['player-name-input', 'tournament-name-input', 'players-per-match'];
formInputs.forEach(id => {
    const element = document.getElementById(id);
    if (element) {
        element.addEventListener('input', (e) => {
            if (id === 'players-per-match') {
                const value = parseInt(e.target.value);
                if (value < 2) e.target.value = 2;
                if (value > 10) e.target.value = 10;
            }
        });
    }
});
let draggedPlayer = null;
document.addEventListener('DOMContentLoaded', () => {
    const playersList = document.getElementById('players-list');
    playersList.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('list-item')) {
            draggedPlayer = e.target;
            e.target.style.opacity = '0.5';
        }
    });
    playersList.addEventListener('dragend', (e) => {
        if (e.target.classList.contains('list-item')) {
            e.target.style.opacity = '1';
        }
    });
    playersList.addEventListener('dragover', (e) => {
        e.preventDefault();
    });
    playersList.addEventListener('drop', (e) => {
        e.preventDefault();
        if (draggedPlayer && e.target.classList.contains('list-item')) {
            const allPlayers = [...playersList.querySelectorAll('.list-item')];
            const draggedIndex = allPlayers.indexOf(draggedPlayer);
            const targetIndex = allPlayers.indexOf(e.target);
            if (draggedIndex < targetIndex) {
                e.target.after(draggedPlayer);
            } else {
                e.target.before(draggedPlayer);
            }
        }
    });
});
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const originalContent = element.innerHTML;
        element.innerHTML = '<div class="loading"></div>';
        element.style.pointerEvents = 'none';
        return () => {
            element.innerHTML = originalContent;
            element.style.pointerEvents = '';
        };
    }
}
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    showAlert('An unexpected error occurred. Please try again.', 'error');
});
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && currentTournament) {
        const selectedTournament = document.querySelector('#tournaments-list .list-item.selected');
        if (selectedTournament) {
            loadTournament(currentTournament, selectedTournament);
        }
    }
});
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
let standingsInterval = null;
function startStandingsAutoRefresh() {
    if (standingsInterval) clearInterval(standingsInterval);
    standingsInterval = setInterval(() => {
        const display = document.getElementById('display-area');
        if (display && display.querySelector('.standings-table')) {
            showStandings();
        }
    }, 30000);
}
function stopStandingsAutoRefresh() {
    if (standingsInterval) {
        clearInterval(standingsInterval);
        standingsInterval = null;
    }
}
document.addEventListener('DOMContentLoaded', async () => {
    try {
        showAlert('Loading tournament data...', 'info');
        await Promise.all([
            loadPlayers(),
            loadTournaments(),
            loadCalculators(),
            loadStrategies()
        ]);
        startStandingsAutoRefresh();
        showAlert('Application ready', 'success');
    } catch (error) {
        console.error('Failed to initialize application:', error);
        showAlert('Failed to load initial data. Please refresh the page.', 'error');
    }
});
window.addEventListener('beforeunload', () => {
    stopStandingsAutoRefresh();
});
document.addEventListener('contextmenu', (e) => {
    if (e.target.closest('.card')) {
        e.preventDefault();
        showAlert('Right-click menu coming soon!', 'info');
    }
});
document.addEventListener('dblclick', (e) => {
    if (e.target.closest('.list-item')) {
        console.log('Double-click detected on list item');
    }
});
window.addEventListener('beforeprint', () => {
    document.body.classList.add('printing');
});
window.addEventListener('afterprint', () => {
    document.body.classList.remove('printing');
});
window.TournamentPro = {
    exportStandings: async () => {
        if (!currentTournament) {
            showAlert('Please select a tournament first', 'warning');
            return;
        }
        try {
            const standings = await apiCall(`/api/tournaments/${currentTournament}/standings`);
            const csv = 'Rank,Player,Points,Wins,Draws,Losses,Matches Played\n' +
                standings.map(s =>
                    `${s.rank},${s.name},${s.points},${s.wins},${s.draws},${s.losses},${s.matches_played}`
                ).join('\n');
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'tournament-standings.csv';
            a.click();
            window.URL.revokeObjectURL(url);
            showAlert('Standings exported successfully', 'success');
        } catch (error) {
            console.error('Failed to export standings:', error);
        }
    },
    exportMatches: async () => {
        if (!currentRound) {
            showAlert('Please select a round first', 'warning');
            return;
        }
        try {
            const data = await apiCall(`/api/rounds/${currentRound}/matches`);
            const json = JSON.stringify(data, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'round-matches.json';
            a.click();
            window.URL.revokeObjectURL(url);
            showAlert('Matches exported successfully', 'success');
        } catch (error) {
            console.error('Failed to export matches:', error);
        }
    },
    getState: () => ({
        currentTournament,
        currentRound,
        selectedPlayers: Array.from(selectedPlayers),
        matchesCount: currentMatches.length
    })
};
console.log('%c🏆 Tournament Matchmaker',
    'font-size: 24px; font-weight: bold; color: #0071e3;');
console.log('%cWelcome to Tournament Pro! Professional tournament management made simple.',
    'font-size: 14px; color: #86868b;');
console.log('%cKeyboard Shortcuts:', 'font-weight: bold; margin-top: 10px;');
console.log('Alt + P: Add Player');
console.log('Alt + T: Create Tournament');
console.log('Alt + R: Create Round');
console.log('Alt + S: Show Standings');
console.log('Alt + M: Show Matches');
console.log('%cAPI Functions:', 'font-weight: bold; margin-top: 10px;');
console.log('TournamentPro.exportStandings() - Export standings to CSV');
console.log('TournamentPro.exportMatches() - Export matches to JSON');
console.log('TournamentPro.getState() - Get current application state');
