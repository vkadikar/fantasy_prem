
let currentWeekSpec = 23; // Default placeholder, will be updated by API call to server
let currentView = 'standings';
let dashboardData = null;
let statsChart = null;
let tablePointsChart = null;
// Store waivers locally for sorting
let waiversData = [];
// Store top players for chat randomization
// Store top players for chat randomization
let topPlayersList = ["Cole Palmer", "Mohamed Salah", "Bukayo Saka", "Erling Haaland"];

// Waivers View State
let currentWaiversView = 'season'; // 'season', 'per_game', 'per_90'


// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboardData(true);

    // Live Poll every 5 minutes (300,000 ms)
    setInterval(() => {
        console.log("Auto-refreshing dashboard data...");
        loadDashboardData(false);
    }, 300000);
});

async function loadDashboardData(isInitialLoad = true) {
    try {
        const response = await fetch('/api/init');
        const data = await response.json();
        dashboardData = data;

        if (data.top_players && data.top_players.length > 0) {
            topPlayersList = data.top_players;
        }

        // Only clear chat on hard reload, not soft refresh
        if (isInitialLoad) {
            clearChat();
        }

        currentWeekSpec = data.current_week;
        document.getElementById('current-week-display').textContent = currentWeekSpec;
        document.getElementById('pred-week').textContent = currentWeekSpec;

        // Render Standings
        renderStandings('table-standard', data.standings.standard);
        renderStandings('table-median', data.standings.median);
        renderStandings('table-optimal', data.standings.optimal || []); // Handle missing optimal
        renderChampionsLeague(data.champions_league || []);
        renderCupBracket(data.cup_bracket || {});

        // Setup Week Selector (Only if options change or initial?)
        // Safe to re-render, but preserve selection if user changed it?
        // Actually, if we are in "Current Week" mode, we want to stay there.
        // If user is looking at Week 1, and we refresh Week 24 stats... 
        // We probably shouldn't force view back to 24 unless we want to.
        // But invalidating dashboardData means if they switch back to 24, it's fresh.

        const weeks = data.weeks.sort((a, b) => b - a);
        const selector = document.getElementById('week-selector');

        // Only rebuild selector if it's empty (Initial) to avoid resetting user selection
        if (selector.options.length === 0) {
            selector.innerHTML = weeks.map(w => `<option value="${w}">Week ${w}</option>`).join('');
            selector.value = currentWeekSpec; // Default to current
        }

        // Load Matchups for the CURRENTLY SELECTED week (or default)
        // If isInitialLoad, use currentWeekSpec.
        // If refresh, use whatever is currently selected value? 
        // Or just reload currentWeekSpec to update the "Live" view?

        // If user is watching Week 24 (Live), they want it to update.
        // If user is watching Week 10 (History), updating Week 24 stats doesn't affect Week 10 view much.

        const selectedWeek = selector.value || currentWeekSpec;
        loadMatchups(selectedWeek);

        // Update "Last Updated" text if element exists (Optional)
        const timestamp = new Date().toLocaleTimeString();
        console.log(`Dashboard updated at ${timestamp}`);

    } catch (e) {
        console.error("Initialization failed:", e);
    }
}

// --- Navigation ---

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar-menu');
    const overlay = document.getElementById('sidebar-overlay');

    if (sidebar.classList.contains('translate-x-full')) {
        // Open
        sidebar.classList.remove('translate-x-full');
        overlay.classList.remove('hidden');
        setTimeout(() => overlay.classList.remove('opacity-0'), 10);
    } else {
        // Close
        sidebar.classList.add('translate-x-full');
        overlay.classList.add('opacity-0');
        setTimeout(() => overlay.classList.add('hidden'), 300);
    }
}

function switchTab(tabName) {
    currentView = tabName;

    // Buttons (Nav Items)
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('bg-gray-800', 'text-white', 'border-l-4', 'border-blue-500');
        btn.classList.add('text-gray-300');
    });

    const activeBtn = document.getElementById(`nav-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.add('bg-gray-800', 'text-white', 'border-l-4', 'border-blue-500');
        activeBtn.classList.remove('text-gray-300');
    }

    // View Sections
    document.querySelectorAll('.view-section').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));

    const activeView = document.getElementById(`view-${tabName}`);
    if (activeView) {
        activeView.classList.remove('hidden');
        activeView.classList.add('active');
    }

    // Close sidebar on mobile/desktop selection
    const sidebar = document.getElementById('sidebar-menu');
    if (!sidebar.classList.contains('translate-x-full')) {
        toggleSidebar();
    }

    if (tabName === 'stats' && dashboardData && dashboardData.advanced_stats) {
        renderStats(dashboardData.advanced_stats);
    }
    if (tabName === 'stats' && dashboardData && dashboardData.advanced_stats) {
        renderStats(dashboardData.advanced_stats);
    }

    if (tabName === 'waivers') {
        loadWaivers();
    }
}

function renderStats(stats) {
    // 1. Superlatives
    const supGrid = document.getElementById('stats-superlatives');
    if (stats.superlatives) {
        const sup = stats.superlatives;
        const cards = [
            { label: 'Form King', ...sup.form_king, color: 'text-yellow-400' },
            { label: 'Most Consistent', ...sup.most_consistent, color: 'text-blue-400' },
            { label: 'Wildcard', ...sup.wildcard, color: 'text-purple-400' },
            { label: 'Unluckiest', ...sup.unluckiest, color: 'text-red-400' },
            { label: 'Luckiest', ...sup.luckiest, color: 'text-green-400' },
        ];

        supGrid.innerHTML = cards.map(c => `
             <div class="glass-panel p-4 rounded-xl text-center">
                 <div class="text-xs text-gray-500 uppercase font-bold mb-1">${c.label}</div>
                 <div class="text-lg font-bold text-white mb-1">${c.team}</div>
                 <div class="text-2xl font-mono ${c.color}">${c.val}</div>
                 <div class="text-xs text-gray-500 mt-2 italic">${c.desc}</div>
             </div>
        `).join('');
    }

    // 2. Form Table
    const formBody = document.getElementById('stats-form-table');
    const sortedStats = [...stats.team_stats].sort((a, b) => b.last_5_avg - a.last_5_avg);

    formBody.innerHTML = sortedStats.map(t => {
        const formHtml = t.form.split('').map(r => {
            let col = 'text-gray-500';
            if (r === 'W') col = 'text-green-400';
            if (r === 'L') col = 'text-red-400';
            if (r === 'D') col = 'text-yellow-400';
            return `<span class="${col} font-bold mr-1">${r}</span>`;
        }).join('');

        return `
         <tr class="border-b border-gray-800 last:border-0 hover:bg-gray-800/30">
            <td class="py-2 font-medium">${t.team}</td>
            <td class="py-2 text-center font-mono text-white">${t.last_5_avg.toFixed(1)}</td>
            <td class="py-2 text-right">${formHtml}</td>
         </tr>
       `;
    }).join('');

    // 3. Charts
    if (!stats.team_stats || stats.team_stats.length === 0) return;

    // Generate consistent colors for all teams
    const teamColors = stats.team_stats.map((t, i) => {
        const hue = (i * 137.508) % 360;
        return `hsl(${hue}, 70%, 50%)`;
    });

    const labels = stats.team_stats[0].weekly_trend.map(wt => `W${wt.week}`);

    // 3a. Fantasy Points Chart
    const ctx1 = document.getElementById('seasonTrendChart').getContext('2d');
    if (statsChart) statsChart.destroy();

    const fantasyDatasets = stats.team_stats.map((t, i) => ({
        label: t.team,
        data: t.weekly_trend.map(wt => wt.score),
        borderColor: teamColors[i],
        backgroundColor: teamColors[i],
        borderWidth: 2,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4
    }));

    statsChart = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: labels,
            datasets: fantasyDatasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: false,  // Hide legend - shown on bottom chart only
                    position: 'bottom',
                    labels: {
                        color: '#9ca3af',
                        font: { size: 10 },
                        usePointStyle: true,
                        padding: 10
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#9ca3af' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9ca3af' }
                }
            }
        }
    });

    // 3b. Table Points Chart
    const ctx2 = document.getElementById('tablePointsChart').getContext('2d');
    if (tablePointsChart) tablePointsChart.destroy();

    const tableDatasets = stats.team_stats.map((t, i) => ({
        label: t.team,
        data: t.weekly_trend.map(wt => wt.table_points || 0),
        borderColor: teamColors[i],
        backgroundColor: teamColors[i],
        borderWidth: 2,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4
    }));

    tablePointsChart = new Chart(ctx2, {
        type: 'line',
        data: {
            labels: labels,
            datasets: tableDatasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: '#9ca3af',
                        font: { size: 10 },
                        usePointStyle: true,
                        padding: 10
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#9ca3af', stepSize: 3 }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9ca3af' }
                }
            }
        }
    });

    // 4. Weekly Extremes
    const extBody = document.getElementById('stats-extremes-table');
    if (stats.weekly_extremes) {
        extBody.innerHTML = stats.weekly_extremes.map(w => `
            <tr class="border-b border-gray-800 last:border-0 hover:bg-gray-800/30">
                <td class="py-2 font-mono text-gray-500">Week ${w.week}</td>
                <td class="py-2 font-medium text-green-300">${w.high_team}</td>
                <td class="py-2 text-right font-mono font-bold">${w.high_score.toFixed(2)}</td>
                <td class="py-2 pl-8 font-medium text-red-300">${w.low_team}</td>
                <td class="py-2 text-right font-mono font-bold">${w.low_score.toFixed(2)}</td>
                
                <td class="py-2 pl-8 font-medium text-blue-300">
                    ${w.best_eff ? w.best_eff.team : '-'} 
                    <span class="text-xs text-gray-500 ml-1">(${w.best_eff ? w.best_eff.pct.toFixed(1) : '0'}%)</span>
                </td>
                <td class="py-2 text-right font-mono text-xs">
                    ${w.best_eff ? w.best_eff.score.toFixed(1) : '0'} / ${w.best_eff ? w.best_eff.opt.toFixed(1) : '0'}
                </td>
                
                <td class="py-2 pl-8 font-medium text-orange-300">
                    ${w.worst_eff ? w.worst_eff.team : '-'}
                    <span class="text-xs text-gray-500 ml-1">(${w.worst_eff ? w.worst_eff.pct.toFixed(1) : '0'}%)</span>
                </td>
                <td class="py-2 text-right font-mono text-xs">
                    ${w.worst_eff ? w.worst_eff.score.toFixed(1) : '0'} / ${w.worst_eff ? w.worst_eff.opt.toFixed(1) : '0'}
                </td>
            </tr>
        `).join('');
    }

}

// --- Renderers ---

function renderStandings(tableId, data) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!data || data.length === 0) {
        if (tableId !== 'table-optimal') { // Optimal has its own placeholder
            tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-gray-500">No data available</td></tr>';
        }
        return;
    }

    tbody.innerHTML = data.map(team => `
        <tr class="hover:bg-gray-800/50 transition-colors">
            <td class="font-bold pl-2 ${getRankColor(team.rank, data.length)}">${team.rank}</td>
            <td class="font-medium">${team.team}</td>
            <td class="text-xs text-gray-400 font-mono">${team.record || ''}</td>
            <td class="text-right font-bold text-white">${team.points}</td>
            <td class="text-right text-gray-400 font-mono">${team.fpts_for.toFixed(2)}</td>
        </tr>
    `).join('');
}

function getRankColor(rank, totalTeams) {
    if (rank === 1) return 'text-yellow-400';
    if (rank <= 6) return 'text-blue-400';
    if (rank === totalTeams) return 'text-red-400';
    return 'text-gray-500';
}

function renderChampionsLeague(data) {
    const tbody = document.querySelector('#table-champleague tbody');
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-gray-500">No data available</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(team => `
        <tr class="hover:bg-gray-800/50 transition-colors border-b border-gray-800 last:border-0">
            <td class="font-medium py-3 pl-2">
                ${team.team}
                <div class="text-xs text-gray-500">${team.manager}</div>
            </td>
            <td class="text-center text-white font-mono">${team.w}</td>
            <td class="text-center text-gray-400 font-mono">${team.d}</td>
            <td class="text-center text-gray-400 font-mono">${team.l}</td>
            <td class="text-right font-bold text-yellow-400 font-mono text-lg pr-2">${team.pts}</td>
            <td class="text-right text-gray-400 font-mono pr-2">${team.fpts.toFixed(2)}</td>
        </tr>
    `).join('');
}

function renderCupBracket(bracket) {
    const container = document.getElementById('cup-bracket-container');
    if (!bracket || Object.keys(bracket).length === 0) {
        container.innerHTML = '<div class="text-center py-8 text-gray-500">Bracket not available</div>';
        return;
    }

    const rounds = [
        { key: 'qual', label: 'Qualifiers (Wk 9)' },
        { key: 'r1', label: 'Round of 16 (Wk 14)' },
        { key: 'qf', label: 'Quarter Finals (Wk 19)' },
        { key: 'sf', label: 'Semi Finals (Wk 24 & 29)' },
        { key: 'final', label: 'Final (Wk 34)' }
    ];

    let html = '<div class="flex space-x-6 min-w-max pb-4">';

    rounds.forEach(round => {
        const matches = bracket[round.key] || [];

        let matchCards = matches.map(m => {
            const p1 = m.p1 || 'TBD';
            const p2 = m.p2 || 'TBD';
            const s1 = (typeof m.s1 === 'number') ? m.s1.toFixed(2) : '-';
            const s2 = (typeof m.s2 === 'number') ? m.s2.toFixed(2) : '-';

            const p1Class = (m.winner === m.p1 && m.p1) ? 'text-green-400 font-bold' : ((m.p1) ? 'text-gray-200' : 'text-gray-500 italic');
            const p2Class = (m.winner === m.p2 && m.p2) ? 'text-green-400 font-bold' : ((m.p2) ? 'text-gray-200' : 'text-gray-500 italic');

            return `
                <div class="glass-panel p-3 rounded-lg border border-gray-700 w-56 relative flex flex-col justify-center mb-4 last:mb-0">
                    <div class="flex justify-between items-center mb-2">
                        <span class="truncate text-sm ${p1Class} w-32" title="${p1}">${p1}</span>
                        <span class="font-mono text-sm text-gray-400">${s1}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="truncate text-sm ${p2Class} w-32" title="${p2}">${p2}</span>
                        <span class="font-mono text-sm text-gray-400">${s2}</span>
                    </div>
                    ${m.status === 'Completed' ? '' : `<div class="text-[10px] text-gray-500 mt-2 text-right uppercase">${m.status}</div>`}
                </div>
            `;
        }).join('');

        html += `
            <div class="flex flex-col flex-shrink-0">
                <div class="text-center font-bold text-xs uppercase tracking-wider text-orange-400 mb-4 border-b border-orange-500/30 pb-2">
                    ${round.label}
                </div>
                <div class="flex flex-col justify-center h-full space-y-4">
                    ${matchCards}
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

function renderMatchupCardHTML(m, type = 'standard') {
    let borderClass = "glass-panel";
    if (type === 'cl') borderClass = "border border-yellow-500/30 shadow-[0_0_15px_rgba(234,179,8,0.1)]";
    if (type === 'cup') borderClass = "border border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.1)]";

    const containerClass = type !== 'standard' ? 'glass-panel ' + borderClass : 'glass-panel';

    return `
        <div class="${containerClass} p-4 sm:p-6 rounded-xl matchup-card flex justify-between items-center group cursor-pointer hover:bg-white/5 transition-colors" onclick="openMatchup('${m.matchupId}')">
            
            <!-- Home -->
            <div class="flex-1 text-left">
                <div class="font-bold text-sm sm:text-lg ${m.home_score > m.away_score ? 'text-green-400' : 'text-gray-300'}">
                    ${m.home_team}
                </div>
                <div class="text-xl sm:text-2xl font-mono mt-1">${m.home_score.toFixed(2)}</div>
                ${m.home_projected ? `<div class="text-[10px] sm:text-xs text-blue-400 font-mono mt-1">Proj: ${m.home_projected.toFixed(2)}</div>` : ''}
            </div>
            
            <!-- VS -->
            <div class="px-3 sm:px-6 text-gray-600 font-bold text-xs sm:text-sm">VS</div>
            
            <!-- Away -->
            <div class="flex-1 text-right">
                <div class="font-bold text-sm sm:text-lg ${m.away_score > m.home_score ? 'text-green-400' : 'text-gray-300'}">
                    ${m.away_team}
                </div>
                <div class="text-xl sm:text-2xl font-mono mt-1">${m.away_score.toFixed(2)}</div>
                ${m.away_projected ? `<div class="text-[10px] sm:text-xs text-blue-400 font-mono mt-1">Proj: ${m.away_projected.toFixed(2)}</div>` : ''}
            </div>
            
        </div>
    `;
}

async function loadMatchups(week) {
    const grid = document.getElementById('matchups-grid');
    const clSection = document.getElementById('cl-matchups-section');
    const clGrid = document.getElementById('cl-matchups-grid');
    const cupSection = document.getElementById('cup-matchups-section');
    const cupGrid = document.getElementById('cup-matchups-grid');

    grid.innerHTML = '<div class="col-span-full text-center py-12 text-gray-500">Loading matchups...</div>';
    if (clSection) clSection.classList.add('hidden');
    if (cupSection) cupSection.classList.add('hidden');

    try {
        const response = await fetch(`/api/matchups/${week}`);
        const data = await response.json();

        let standard = [];
        let cl = [];
        let cup = [];

        if (Array.isArray(data)) {
            standard = data;
        } else {
            standard = data.standard || [];
            cl = data.champions_league || [];
            cup = data.cup || [];
        }

        // Standard
        if (standard.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-center py-12 text-gray-500">No matchups found for this week.</div>';
        } else {
            grid.innerHTML = standard.map(m => renderMatchupCardHTML(m, 'standard')).join('');
        }

        // Champions League
        if (clSection) {
            if (cl.length > 0) {
                clSection.classList.remove('hidden');
                clGrid.innerHTML = cl.map(m => renderMatchupCardHTML(m, 'cl')).join('');
            } else {
                clSection.classList.add('hidden');
            }
        }

        // Cup
        if (cupSection) {
            if (cup.length > 0) {
                cupSection.classList.remove('hidden');
                cupGrid.innerHTML = cup.map(m => renderMatchupCardHTML(m, 'cup')).join('');
            } else {
                cupSection.classList.add('hidden');
            }
        }

    } catch (e) {
        console.error(e);
        grid.innerHTML = '<div class="col-span-full text-center py-12 text-red-500">Error loading matchups.</div>';
    }
}

// --- Modals ---

// --- Modals ---

let currentMatchupData = null;
let isOptimalView = false;

let currentMatchupWeek = null;

async function openMatchup(matchupId) {
    const modal = document.getElementById('lineup-modal');
    modal.classList.remove('hidden');

    // Reset View State
    isOptimalView = false;
    currentMatchupData = null;

    // Extract week from matchupId
    const parts = matchupId.split('_');
    if (parts[0] === 'CL' || parts[0] === 'CUP') {
        currentMatchupWeek = parseInt(parts[1]);
    } else {
        currentMatchupWeek = parseInt(parts[0]);
    }

    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="col-span-2 text-center text-gray-400">Loading Lineups from Fantrax...</div>';

    // Update modal header with correct week
    const modalNote = document.getElementById('modal-prediction-note');
    if (modalNote) {
        modalNote.textContent = `Predictions available for Week ${currentMatchupWeek}`;
    }

    try {
        const response = await fetch(`/api/lineup/${matchupId}`);
        currentMatchupData = await response.json();

        renderMatchupView();

    } catch (e) {
        console.error(e);
        content.innerHTML = '<div class="col-span-2 text-center text-red-400">Failed to load lineups.</div>';
    }
}

function renderMatchupView() {
    const content = document.getElementById('modal-content');
    // Always show predictions for all weeks
    const showPreds = true;

    // Controls
    const controlsHtml = `
        <div class="col-span-1 md:col-span-2 flex justify-end mb-4 border-b border-gray-700 pb-2">
            <label class="inline-flex items-center cursor-pointer">
                <input type="checkbox" class="sr-only peer" onchange="toggleOptimal(this)" ${isOptimalView ? 'checked' : ''}>
                <div class="relative w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-800 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                <span class="ms-3 text-sm font-medium text-gray-300">Show Optimal</span>
            </label>
        </div>
    `;

    content.innerHTML = `
        ${controlsHtml}
        ${renderTeamLineup(currentMatchupData.home_team, showPreds, isOptimalView, currentMatchupData.home_score)}
        ${renderTeamLineup(currentMatchupData.away_team, showPreds, isOptimalView, currentMatchupData.away_score)}
    `;
}

function toggleOptimal(checkbox) {
    isOptimalView = checkbox.checked;
    renderMatchupView();
}

function renderTeamLineup(team, showPreds, optimalMode = false, officialScore = null) {
    if (!team.roster || team.roster.length === 0) {
        return `
            <div class="glass-panel p-4 rounded-lg bg-gray-800/30">
                <h4 class="text-lg font-bold text-center mb-4 border-b border-gray-700 pb-2">${team.name}</h4>
                <div class="text-gray-500 text-sm italic py-4">Roster data not available yet.</div>
            </div>
        `;
    }

    // Filter valid players (remove null names)
    const validPlayers = team.roster.filter(p => p.name);

    // Determine Starters
    let starterIds = new Set();
    if (optimalMode) {
        starterIds = calculateOptimalStarters(validPlayers);
    } else {
        validPlayers.forEach(p => { if (p.status == '1') starterIds.add(p.player_id); });
    }

    let starters = validPlayers.filter(p => starterIds.has(p.player_id));
    let bench = validPlayers.filter(p => !starterIds.has(p.player_id));

    // Sort starters by position: G, D, M, F
    const posOrder = { 'G': 0, 'D': 1, 'M': 2, 'F': 3 };
    starters.sort((a, b) => {
        const pa = posOrder[a.position] !== undefined ? posOrder[a.position] : 99;
        const pb = posOrder[b.position] !== undefined ? posOrder[b.position] : 99;
        return pa - pb;
    });

    // Calculate Total Score: Use Official if available and not optimizing, else sum starters
    let totalScore = 0;
    let calculatedSum = starters.reduce((sum, p) => sum + (p.score || 0), 0);

    if (officialScore !== null && !optimalMode) {
        totalScore = officialScore;

        // Auto-Substitution Check
        // If there is a discrepancy between Official Score and Sum of Starters,
        // it likely means an auto-sub occurred (Starter DNP -> Bench Player In).
        if (Math.abs(totalScore - calculatedSum) > 0.1) {
            const { newStarters, newBench } = applyAutoSubs(starters, bench, totalScore, calculatedSum);
            starters = newStarters;
            bench = newBench;

            // Re-sort Starters by Position after swap
            starters.sort((a, b) => {
                const pa = posOrder[a.position] !== undefined ? posOrder[a.position] : 99;
                const pb = posOrder[b.position] !== undefined ? posOrder[b.position] : 99;
                return pa - pb;
            });
        }
    } else {
        totalScore = calculatedSum;
    }

    // Calculate Total Projected
    const totalProj = starters.reduce((sum, p) => {
        return sum + (p.prediction ? (p.prediction.predicted_fpts || 0) : 0);
    }, 0);

    const renderPlayer = (p) => {
        // Build stats string (exclude INJURED from generic loop)
        let statsStr = '';
        let injuryHtml = '';
        let subHtml = '';

        if (p.autoSubIn) {
            subHtml = `<span class="text-green-400 font-bold ml-2 text-xs" title="Auto-Sub In">🔄 IN</span>`;
        } else if (p.autoSubOut) {
            subHtml = `<span class="text-red-400 font-bold ml-2 text-xs" title="Auto-Sub Out">🔄 OUT</span>`;
        }

        if (p.stats) {
            // Handle Injury separately
            if (p.stats.INJURED) {
                const status = p.stats.INJURED;
                if (status === 'Out') {
                    injuryHtml = `<span class="text-red-500 font-bold ml-2">OUT</span>`;
                } else if (status === 'GTD') {
                    injuryHtml = `<span class="text-orange-500 font-bold ml-2">GTD</span>`;
                } else if (status !== 'Available' && status !== 'OK') {
                    // Catch-all for other statuses if any
                    injuryHtml = `<span class="text-red-400 font-bold ml-2">${status}</span>`;
                }
            }

            statsStr = Object.entries(p.stats)
                .filter(([k, v]) => k !== 'INJURED') // Filter out INJURED
                .map(([k, v]) => `<span class="mr-2 text-gray-400">${k}: <span class="text-gray-200">${v}</span></span>`)
                .join('');
        }

        // Score formatting: Always 2 decimals, show even if 0 or negative
        const scoreDisplay = (p.score !== undefined && p.score !== null) ? Number(p.score).toFixed(2) : '0.00';

        return `
        <div class="flex justify-between items-center py-2 border-b border-gray-800 last:border-0 ${p.autoSubOut ? 'opacity-50' : ''}">
            <div>
                <div class="flex-1 min-w-0">
                    <button onclick="showPlayerDetails('${p.player_id}')" class="font-medium text-white hover:text-blue-400 hover:underline text-left truncate w-full transition-colors">${p.name}</button>
                    <div class="flex items-center gap-1 mt-0.5">
                        ${injuryHtml}
                        ${subHtml}
                    </div>
                    <div class="text-xs text-gray-500 mb-1">${p.position} &bull; ${p.team}</div>
                </div>
                ${statsStr ? `<div class="text-xs">${statsStr}</div>` : ''}
            </div>
            <div class="text-right">
                <div class="font-bold ${p.score < 0 ? 'text-red-400' : 'text-gray-100'} text-lg">${scoreDisplay}</div> 
                ${showPreds && p.prediction && p.prediction.predicted_fpts != null ? `<div class="text-xs text-blue-400 font-bold">Proj: ${Number(p.prediction.predicted_fpts).toFixed(2)}</div>` : ''}
            </div>
        </div>
    `;
    };

    return `
        <div class="glass-panel p-4 rounded-lg bg-gray-800/30 border ${optimalMode ? 'border-blue-500/50' : 'border-transparent'}">
            <h4 class="text-lg font-bold text-center mb-2">${team.name}</h4>
            <div class="text-center mb-4">
                 <span class="text-2xl font-mono ${optimalMode ? 'text-blue-400' : 'text-white'}">${(totalScore || 0).toFixed(2)}</span>
                 ${showPreds ? `<div class="text-sm text-blue-400 font-mono mt-1">Proj: ${(totalProj || 0).toFixed(2)}</div>` : ''}
            </div>
            
            <div class="mb-4">
                <h5 class="text-xs uppercase text-gray-500 font-bold mb-2">Starters</h5>
                <div class="space-y-1">
                    ${starters.map(renderPlayer).join('')}
                </div>
            </div>

            ${bench.length > 0 ? `
            <div>
                <h5 class="text-xs uppercase text-gray-500 font-bold mb-2">Bench</h5>
                <div class="space-y-1 opacity-60 bg-gray-900/20 rounded p-2">
                    ${bench.map(renderPlayer).join('')}
                </div>
            </div>
            ` : ''}
        </div>
    `;
}

function applyAutoSubs(starters, bench, targetScore, currentSum) {
    const diff = targetScore - currentSum;
    // Don't fix tiny float errors
    if (Math.abs(diff) < 0.01) return { newStarters: starters, newBench: bench };

    console.log(`[AutoSub] Attempting to resolve discrepancy: Official ${targetScore} vs Sum ${currentSum} (Diff: ${diff})`);

    // Strategy 1: One-for-One Swap
    // Check every S in Starters and B in Bench
    // If (B.score - S.score) == diff, we found the swap.

    for (const s of starters) {
        for (const b of bench) {
            const sScore = s.score || 0;
            const bScore = b.score || 0;

            // Check if swapping S for B fixes the diff
            // NewSum = OldSum - S + B
            // Diff = NewSum - OldSum = B - S
            // Target Diff check: (bScore - sScore) should equal diff
            if (Math.abs((bScore - sScore) - diff) < 0.05) {
                console.log(`[AutoSub] Found Swap: ${s.name} (${sScore}) <-> ${b.name} (${bScore})`);

                // Create swapped objects
                const newS = { ...s, autoSubOut: true }; // Goes to bench
                const newB = { ...b, autoSubIn: true };   // Goes to starters

                // Reconstruct arrays
                const newStarters = starters.map(p => p.player_id === s.player_id ? newB : p);
                const newBench = bench.map(p => p.player_id === b.player_id ? newS : p);

                return { newStarters, newBench };
            }
        }
    }

    console.log("[AutoSub] No clean swap found.");
    return { newStarters: starters, newBench: bench };
}

function calculateOptimalStarters(allPlayers) {
    // Clone to avoid sorting in place affecting other views
    const players = [...allPlayers];

    // Detect if this is an unplayed week (everyone has 0 points)
    // If so, use predictions instead of actual scores
    // Helper function to get the score to use for optimization
    const getOptimizationScore = (player) => {
        // Hindsight Optimization for completed weeks
        if (currentMatchupWeek < currentWeekSpec) {
            return player.score || 0;
        }

        // Hybrid Logic for live/future weeks
        // If player has started/played (is_started=true from server), use ACTUAL score.
        // If player has NOT started, use PROJECTED score.
        if (player.is_started) {
            return player.score || 0;
        } else {
            return player.prediction ? (player.prediction.predicted_fpts || 0) : 0;
        }
    };

    // Helper to get sorted list by position
    const getByPos = (pos) => players
        .filter(p => p.position === pos)
        .sort((a, b) => getOptimizationScore(b) - getOptimizationScore(a));

    // Clone lists because we will shift() from them
    const gks = getByPos('G');
    const defs = getByPos('D');
    const mids = getByPos('M');
    const fwds = getByPos('F');

    const starters = [];

    // 1. Base (1G, 3D, 2M, 1F)
    if (gks.length > 0) starters.push(gks.shift());
    for (let i = 0; i < 3; i++) if (defs.length > 0) starters.push(defs.shift());
    for (let i = 0; i < 2; i++) if (mids.length > 0) starters.push(mids.shift());
    for (let i = 0; i < 1; i++) if (fwds.length > 0) starters.push(fwds.shift());

    // 2. Flex (4 spots)
    for (let i = 0; i < 4; i++) {
        // Candidates from remaining lists that satisfy max constraints
        // Max: 1G (already full), 5D, 5M, 3F.

        const cD = starters.filter(p => p.position === 'D').length;
        const cM = starters.filter(p => p.position === 'M').length;
        const cF = starters.filter(p => p.position === 'F').length;

        let best = null;
        let sourceList = null;
        let bestScore = -9999;

        // Check D
        if (cD < 5 && defs.length > 0) {
            const s = getOptimizationScore(defs[0]);
            if (s > bestScore) { best = defs[0]; sourceList = defs; bestScore = s; }
        }
        // Check M
        if (cM < 5 && mids.length > 0) {
            const s = getOptimizationScore(mids[0]);
            if (s > bestScore) { best = mids[0]; sourceList = mids; bestScore = s; }
        }
        // Check F
        if (cF < 4 && fwds.length > 0) {
            const s = getOptimizationScore(fwds[0]);
            if (s > bestScore) { best = fwds[0]; sourceList = fwds; bestScore = s; }
        }

        if (best) {
            starters.push(best);
            sourceList.shift(); // Remove from pool
        } else {
            console.warn("[Optimal] No valid flex candidate found!", { cD, cM, cF, defs: defs.length, mids: mids.length, fwds: fwds.length });
        }
    }

    const optimalSum = starters.reduce((acc, p) => acc + (p.score || 0), 0);
    console.log(`[Optimal] Calculated starters for Week ${currentMatchupWeek}. Total Points: ${optimalSum}`, starters.map(p => `${p.name} (${p.position}, ${p.score})`));

    return new Set(starters.map(p => p.player_id));
}

function closeModal() {
    document.getElementById('lineup-modal').classList.add('hidden');
}

// Close on click outside
document.getElementById('lineup-modal').addEventListener('click', (e) => {
    if (e.target.id === 'lineup-modal') closeModal();
});

// --- Chat Functions ---

let chatChart = null; // Store chat chart instance

function clearChat() {
    const messagesDiv = document.getElementById('chat-messages');

    // Pick random player from Top 50 (Fallback to Cole Palmer if list empty)
    const randomPlayer = (topPlayersList && topPlayersList.length > 0)
        ? topPlayersList[Math.floor(Math.random() * topPlayersList.length)]
        : "Cole Palmer";

    messagesDiv.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full text-center p-6 opacity-90">
            <div class="text-5xl mb-6">🍺</div>
            <h3 class="text-2xl font-bold text-white mb-2 tracking-tight">The Commissioner is IN.</h3>
            <p class="text-gray-400 text-sm max-w-sm mb-8 italic leading-relaxed">
                "Right, listen here. I've got the data, I've got the pints, and I've got absolutely zero patience for your tragic management skills. State your business."
            </p>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-md">
                <button onclick="askQuestion('Who is the biggest bottler this season?')" 
                    class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                    <span class="block text-blue-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-blue-300">Analysis</span>
                    <span class="text-gray-200 text-sm font-medium">"Who's the biggest bottler?"</span>
                </button>
                
                <button onclick="askQuestion('Roast the team in last place properly.')" 
                    class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                    <span class="block text-red-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-red-300">Banter</span>
                    <span class="text-gray-200 text-sm font-medium">"Roast the last place team"</span>
                </button>
                
                <button onclick="askQuestion('Who should I pick up from waivers? Check for injuries.')" 
                    class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                     <span class="block text-green-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-green-300">Strategy</span>
                    <span class="text-gray-200 text-sm font-medium">"Waiver wire analysis"</span>
                </button>
                
                <button onclick="askQuestion('What are the streets saying about ${randomPlayer}?')" 
                    class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                     <span class="block text-orange-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-orange-300">Social</span>
                    <span class="text-gray-200 text-sm font-medium">"What's the word on ${randomPlayer}?"</span>
                </button>
            </div>
        </div>
    `;

    // Clear any charts
    if (typeof chatChart !== 'undefined' && chatChart) {
        chatChart = null;
    }
}

function askQuestion(text) {
    const input = document.getElementById('chat-input');
    input.value = text;
    sendMessage();
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    // Clear input
    input.value = '';

    // Add user message to chat
    addChatMessage('user', message);

    // Show loading
    const loadingId = addChatMessage('assistant', 'Thinking...', true);

    // Disable send button with spinner
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    sendBtn.innerHTML = `
        <svg class="animate-spin h-5 w-5 text-white mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
    `;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        // Remove loading message
        document.getElementById(loadingId).remove();

        // Render response
        renderChatResponse(data);

    } catch (error) {
        // Remove loading message
        document.getElementById(loadingId).remove();
        addChatMessage('assistant', `Error: ${error.message}`, false, 'error');
    } finally {
        // Re-enable send button
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

function addChatMessage(role, content, isLoading = false, type = 'text') {
    const container = document.getElementById('chat-messages');

    // Remove welcome message if present (be specific to avoid removing actual messages)
    const welcome = container.querySelector('.text-gray-500.italic.text-center.py-8');
    if (welcome && welcome.parentElement === container) {
        welcome.remove();
    }

    // Remove the new clearing div too if present
    const newWelcome = container.querySelector('.opacity-90');
    if (newWelcome && newWelcome.parentElement === container) {
        newWelcome.remove(); // Note: This clears the ENTIRE welcome screen when the first message is sent. CORRECT.
        // Wait, removing the MAIN welcome div is key. 
        // The new welcome div class includes "opacity-90".
        newWelcome.remove();
    }
    // Also remove any random player buttons if they are just direct children? 
    // The structure is `div#chat-messages > div.flex-col...`
    // The `.opacity-90` is on the inner div.
    // If I clear `innerHTML` of container it's cleaner?
    // But `addChatMessage` appends.
    // So if it's the first message, I should probably clear the container.
    // Let's use a simpler check: if we have zero messages (class .flex), clear.
    if (container.children.length > 0 && container.children[0].classList.contains('opacity-90')) {
        container.innerHTML = '';
    }
    // Also handle the old welcome
    if (container.children.length > 0 && container.querySelector('.text-gray-500')) {
        // This is a bit risky. Let's just trust `.opacity-90` for the new one.
    }


    const msgId = `msg-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
    const isUser = role === 'user';

    const msgDiv = document.createElement('div');
    msgDiv.id = msgId;
    msgDiv.className = `flex ${isUser ? 'justify-end' : 'justify-start'}`;

    const bubble = document.createElement('div');
    bubble.className = `max-w-[80%] rounded-lg p-3 ${isUser
        ? 'bg-blue-600 text-white'
        : type === 'error'
            ? 'bg-red-900/50 text-red-200'
            : 'bg-gray-800 text-gray-100'
        }`;

    if (isLoading) {
        bubble.innerHTML = `<div class="flex items-center gap-2">
            <div class="animate-pulse">●</div>
            <div class="animate-pulse" style="animation-delay: 0.2s">●</div>
            <div class="animate-pulse" style="animation-delay: 0.4s">●</div>
        </div>`;
    } else {
        bubble.textContent = content;
    }

    msgDiv.appendChild(bubble);
    container.appendChild(msgDiv);

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;

    return msgId;
}

function renderChatResponse(data) {
    const container = document.getElementById('chat-messages');

    if (!data.success) {
        // Create error message with code if available
        const msgDiv = document.createElement('div');
        msgDiv.className = 'flex justify-start';

        const bubble = document.createElement('div');
        bubble.className = 'max-w-[90%] rounded-lg p-4 bg-red-900/30 border border-red-700 text-gray-100';

        const errorText = document.createElement('div');
        errorText.className = 'text-red-300 mb-2';
        errorText.textContent = data.message || 'An error occurred';
        bubble.appendChild(errorText);

        // Add code viewer if code is present
        if (data.code) {
            const codeToggle = document.createElement('button');
            codeToggle.className = 'mt-3 text-xs text-red-400 hover:text-red-300 underline';
            codeToggle.textContent = 'View Last Attempted Code';

            const codeContainer = document.createElement('div');
            codeContainer.className = 'hidden mt-2 bg-gray-900 rounded p-3 overflow-x-auto';

            const codeBlock = document.createElement('pre');
            codeBlock.className = 'text-xs text-green-400';
            codeBlock.textContent = data.code;
            codeContainer.appendChild(codeBlock);

            codeToggle.onclick = () => {
                if (codeContainer.classList.contains('hidden')) {
                    codeContainer.classList.remove('hidden');
                    codeToggle.textContent = 'Hide Code';
                } else {
                    codeContainer.classList.add('hidden');
                    codeToggle.textContent = 'View Last Attempted Code';
                }
            };

            bubble.appendChild(codeToggle);
            bubble.appendChild(codeContainer);
        }

        msgDiv.appendChild(bubble);
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
        return;
    }

    const type = data.type;
    const message = data.message;

    // Debug logging
    console.log('Chat response:', { type, hasData: !!data.data, dataKeys: data.data ? Object.keys(data.data) : [] });

    // Create message container
    const msgDiv = document.createElement('div');
    msgDiv.className = 'flex justify-start';

    const bubble = document.createElement('div');
    // Use full width for plotly charts, otherwise constrain to 90%
    const bubbleWidth = (type === 'plotly' || type === 'text+plot') ? 'w-full' : 'max-w-[90%]';
    bubble.className = `${bubbleWidth} rounded - lg p - 4 bg - gray - 800 text - gray - 100`;

    // Add text message if present (render as markdown)
    if (message) {
        const textDiv = document.createElement('div');
        textDiv.className = 'mb-3 prose prose-invert prose-sm max-w-none';
        textDiv.innerHTML = marked.parse(message);
        bubble.appendChild(textDiv);
    }

    // Handle different response types
    // Handle different response types
    if (type === 'text+plot' && data.data) {
        // NEW JSON BASED PLOT
        if (data.data.plot_json) {
            const plotlyContainer = document.createElement('div');
            plotlyContainer.className = 'mt-3 w-full';
            plotlyContainer.style.minHeight = '400px';
            bubble.appendChild(plotlyContainer);

            setTimeout(() => {
                if (window.Plotly) {
                    Plotly.newPlot(plotlyContainer, data.data.plot_json.data, data.data.plot_json.layout);
                } else {
                    console.error("Plotly not loaded");
                    plotlyContainer.innerHTML = "Error: Plotly library not found. Please refresh.";
                }
            }, 100);
        }
        // OLD HTML FALLBACK
        else if (data.data.html) {
            const plotlyContainer = document.createElement('div');
            plotlyContainer.className = 'mt-3 w-full';
            plotlyContainer.style.minHeight = '400px';
            plotlyContainer.innerHTML = data.data.html;
            bubble.appendChild(plotlyContainer);

            setTimeout(() => {
                const scripts = plotlyContainer.querySelectorAll('script');
                scripts.forEach(script => {
                    if (script.textContent && !script.src) {
                        try { new Function(script.textContent)(); } catch (e) { }
                    }
                });
            }, 100);
        }

    } else if (type === 'text+table' && data.data) {
        // Support both single table and multi-table (dict)
        if (data.data.table && Array.isArray(data.data.table)) {
            // Single table legacy format
            bubble.appendChild(createTableElement(data.data.table));
        } else {
            // Check for multi-table dict (e.g. {'Matchups': [...], 'Standings': [...]})
            Object.keys(data.data).forEach(title => {
                const tableData = data.data[title];
                if (Array.isArray(tableData) && tableData.length > 0) {
                    // Add Title
                    const titleDiv = document.createElement('div');
                    titleDiv.className = 'text-sm font-bold text-gray-400 mt-4 mb-2 uppercase tracking-wider border-b border-gray-700 pb-1';
                    titleDiv.textContent = title.replace(/_/g, ' ');
                    bubble.appendChild(titleDiv);

                    // Add Table
                    bubble.appendChild(createTableElement(tableData));
                }
            });
        }
    } else if (type === 'plotly' && data.data && data.data.html) {
        // Legacy support
        const plotlyContainer = document.createElement('div');
        plotlyContainer.className = 'mt-3 w-full';
        plotlyContainer.style.minHeight = '400px';
        plotlyContainer.innerHTML = data.data.html;
        bubble.appendChild(plotlyContainer);

        setTimeout(() => {
            const scripts = plotlyContainer.querySelectorAll('script');
            scripts.forEach(script => {
                if (script.textContent && !script.src) {
                    try {
                        const scriptFunc = new Function(script.textContent);
                        scriptFunc();
                    } catch (e) {
                        console.error('Error executing plotly script:', e);
                    }
                }
            });
        }, 100);
    } else if (type === 'chart' && data.data) {
        const chartContainer = createChartElement(data.data);
        bubble.appendChild(chartContainer);
    } else if (type === 'table' && data.data) {
        // Support both single table and multi-table
        if (Array.isArray(data.data)) {
            bubble.appendChild(createTableElement(data.data));
        } else {
            // Multi-table dict
            Object.keys(data.data).forEach(title => {
                const tableData = data.data[title];
                if (Array.isArray(tableData) && tableData.length > 0) {
                    const titleDiv = document.createElement('div');
                    titleDiv.className = 'text-sm font-bold text-gray-400 mt-4 mb-2 uppercase tracking-wider border-b border-gray-700 pb-1';
                    titleDiv.textContent = title.replace(/_/g, ' ');
                    bubble.appendChild(titleDiv);
                    bubble.appendChild(createTableElement(tableData));
                }
            });
        }
    }

    // Add collapsible code viewer if code is present
    if (data.code) {
        const codeToggle = document.createElement('button');
        codeToggle.className = 'mt-3 text-xs text-gray-400 hover:text-gray-300 underline';
        codeToggle.textContent = 'View Code';

        const codeContainer = document.createElement('div');
        codeContainer.className = 'hidden mt-2 bg-gray-900 rounded p-3 overflow-x-auto';

        const codeBlock = document.createElement('pre');
        codeBlock.className = 'text-xs text-green-400';
        codeBlock.textContent = data.code;
        codeContainer.appendChild(codeBlock);

        codeToggle.onclick = () => {
            if (codeContainer.classList.contains('hidden')) {
                codeContainer.classList.remove('hidden');
                codeToggle.textContent = 'Hide Code';
            } else {
                codeContainer.classList.add('hidden');
                codeToggle.textContent = 'View Code';
            }
        };

        bubble.appendChild(codeToggle);
        bubble.appendChild(codeContainer);
    }

    msgDiv.appendChild(bubble);
    container.appendChild(msgDiv);

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function createChartElement(chartData) {
    const container = document.createElement('div');
    container.className = 'mt-3';

    if (chartData.title) {
        const title = document.createElement('h4');
        title.className = 'text-sm font-bold mb-2 text-gray-300';
        title.textContent = chartData.title;
        container.appendChild(title);
    }

    const canvasContainer = document.createElement('div');
    canvasContainer.className = 'relative h-64 bg-gray-900/50 rounded p-2';

    const canvas = document.createElement('canvas');
    canvasContainer.appendChild(canvas);
    container.appendChild(canvasContainer);

    // Render chart after a brief delay to ensure DOM is ready
    setTimeout(() => {
        if (chatChart) chatChart.destroy();

        const ctx = canvas.getContext('2d');
        chatChart = new Chart(ctx, {
            type: chartData.chartType || 'bar',
            data: chartData.data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                ...chartData.options
            }
        });
    }, 100);

    return container;
}

function createTableElement(tableData) {
    const container = document.createElement('div');
    container.className = 'mt-3 overflow-x-auto';

    // Handle array of objects format (from pandas to_dict('records'))
    if (Array.isArray(tableData) && tableData.length > 0) {
        const table = document.createElement('table');
        table.className = 'w-full text-sm border-collapse';

        // Create headers from first object's keys
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.className = 'border-b border-gray-700';

        const headers = Object.keys(tableData[0]);
        headers.forEach(header => {
            const th = document.createElement('th');
            th.className = 'text-left py-2 px-3 text-gray-400 font-semibold';
            th.textContent = header;
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Create rows
        const tbody = document.createElement('tbody');
        tableData.forEach((row, idx) => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-gray-800 hover:bg-gray-700/30';

            headers.forEach(header => {
                const td = document.createElement('td');
                td.className = 'py-2 px-3';
                td.textContent = row[header];
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        container.appendChild(table);
        return container;
    }

    // Legacy format support
    if (tableData.title) {
        const title = document.createElement('h4');
        title.className = 'text-sm font-bold mb-2 text-gray-300';
        title.textContent = tableData.title;
        container.appendChild(title);
    }

    const table = document.createElement('table');
    table.className = 'w-full text-sm border-collapse';

    // Headers
    if (tableData.headers) {
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.className = 'border-b border-gray-700';

        tableData.headers.forEach(header => {
            const th = document.createElement('th');
            th.className = 'text-left py-2 px-3 text-gray-400';
            th.textContent = header;
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);
    }

    // Rows
    if (tableData.rows) {
        const tbody = document.createElement('tbody');

        tableData.rows.forEach((row, idx) => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-gray-800 hover:bg-gray-700/30';

            row.forEach(cell => {
                const td = document.createElement('td');
                td.className = 'py-2 px-3';
                td.textContent = cell;
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
    }

    container.appendChild(table);
    return container;
}

function createCodeSection(code, result) {
    const container = document.createElement('div');
    container.className = 'mt-3';

    const header = document.createElement('div');
    header.className = 'flex items-center justify-between bg-gray-900 px-3 py-2 rounded-t cursor-pointer';
    header.innerHTML = `
        < span class="text-xs text-gray-400" > Code</span >
            <span class="text-xs text-gray-500">▼</span>
    `;

    const codeBlock = document.createElement('pre');
    codeBlock.className = 'bg-gray-950 p-3 rounded-b text-xs overflow-x-auto';
    codeBlock.style.display = 'none';

    const codeElement = document.createElement('code');
    codeElement.className = 'text-green-400';
    codeElement.textContent = code;
    codeBlock.appendChild(codeElement);

    // Toggle code visibility
    header.onclick = () => {
        codeBlock.style.display = codeBlock.style.display === 'none' ? 'block' : 'none';
        header.querySelector('span:last-child').textContent = codeBlock.style.display === 'none' ? '▼' : '▲';
    };

    container.appendChild(header);
    container.appendChild(codeBlock);

    if (result) {
        const resultDiv = document.createElement('div');
        resultDiv.className = 'mt-2 p-2 bg-gray-900/50 rounded text-sm';
        resultDiv.textContent = `Result: ${result} `;
        container.appendChild(resultDiv);
    }

    return container;
}

// --- Waivers Logic ---

let sortCol = null;
let sortAsc = false;

async function loadWaivers() {
    // Update week display
    const weekDisp = document.getElementById('waivers-week-display');
    if (weekDisp) weekDisp.textContent = `Week ${currentWeekSpec}`;

    // Check if already loaded
    if (waiversData.length > 0) {
        renderWaivers();
        return;
    }

    const tbody = document.getElementById('waivers-table-body');
    tbody.innerHTML = '<tr><td colspan="13" class="py-8 text-center text-gray-500 animate-pulse">Scouting free agents...</td></tr>';

    try {
        const response = await fetch('/api/waivers');
        const data = await response.json();

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="13" class="py-8 text-center text-gray-500">No players found on waivers.</td></tr>';
            return;
        }

        waiversData = data;

        // Initial sort
        sortWaivers('fpts');

    } catch (e) {
        console.error("Failed to load waivers:", e);
        tbody.innerHTML = '<tr><td colspan="13" class="py-8 text-center text-red-400">Error loading waiver wire.</td></tr>';
    }
}

function setWaiversView(view) {
    if (currentWaiversView === view) return;
    currentWaiversView = view;

    // Update button styles
    ['season', 'per_game', 'per_90'].forEach(v => {
        const btn = document.getElementById(`btn-view-${v}`);
        if (v === view) {
            btn.className = "px-4 py-1.5 text-xs font-medium rounded-md text-white bg-gray-700 hover:bg-gray-600 transition-colors shadow-sm";
        } else {
            btn.className = "px-4 py-1.5 text-xs font-medium rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors";
        }
    });

    renderWaivers();
}

let currentWaiversPage = 1;
const WAIVERS_PAGE_SIZE = 100;

function prevWaiverPage() {
    if (currentWaiversPage > 1) {
        currentWaiversPage--;
        renderWaivers();
    }
}

function nextWaiverPage() {
    const totalPages = Math.ceil(waiversData.length / WAIVERS_PAGE_SIZE);
    if (currentWaiversPage < totalPages) {
        currentWaiversPage++;
        renderWaivers();
    }
}



// --- FILTERING LOGIC ---

let filteredWaiversData = []; // Data currently being displayed (after filters)
let activeWaiverFilters = {
    positions: new Set(),
    team: 'all',
    stats: [] // Array of {key, val, operator: '>='}
};

function toggleFilterPanel() {
    const panel = document.getElementById('waiver-filter-panel');
    panel.classList.toggle('hidden');

    // Populate teams if empty
    const teamSelect = document.getElementById('filter-team-select');
    if (teamSelect.options.length <= 1 && waiversData.length > 0) {
        const teams = new Set(waiversData.map(p => p.team).filter(Boolean));
        [...teams].sort().forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            teamSelect.appendChild(opt);
        });
    }
}

function togglePosFilter(pos) {
    if (activeWaiverFilters.positions.has(pos)) {
        activeWaiverFilters.positions.delete(pos);
    } else {
        activeWaiverFilters.positions.add(pos);
    }
    updatePosFilterUI();
}

function updatePosFilterUI() {
    ['G', 'D', 'M', 'F'].forEach(pos => {
        const btn = document.getElementById(`filter-pos-${pos.toLowerCase()}`);
        if (activeWaiverFilters.positions.has(pos)) {
            btn.className = "px-2 py-1 text-xs font-mono rounded border border-blue-500 bg-blue-600/20 text-blue-400 font-bold shadow-[0_0_5px_rgba(59,130,246,0.5)]";
        } else {
            btn.className = "px-2 py-1 text-xs font-mono rounded border border-gray-600 text-gray-400 hover:border-gray-500";
        }
    });
}

function addStatFilter() {
    const key = document.getElementById('filter-stat-key').value;
    const val = parseFloat(document.getElementById('filter-stat-val').value);

    if (isNaN(val)) return;

    // Remove existing filter for same key if any
    activeWaiverFilters.stats = activeWaiverFilters.stats.filter(f => f.key !== key);

    activeWaiverFilters.stats.push({ key, val, operator: '>=' });
    renderActiveStatFilters();
}

function removeStatFilter(key) {
    activeWaiverFilters.stats = activeWaiverFilters.stats.filter(f => f.key !== key);
    renderActiveStatFilters();
}

function renderActiveStatFilters() {
    const container = document.getElementById('active-stat-filters');
    container.innerHTML = activeWaiverFilters.stats.map(f => `
        <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-blue-900 text-blue-200 border border-blue-700">
            ${f.key.toUpperCase()} >= ${f.val}
            <button onclick="removeStatFilter('${f.key}')" class="ml-1 text-blue-400 hover:text-white font-bold">×</button>
        </span>
    `).join('');
}

function resetWaiverFilters() {
    activeWaiverFilters.positions.clear();
    activeWaiverFilters.team = 'all';
    activeWaiverFilters.stats = [];

    updatePosFilterUI();
    document.getElementById('filter-team-select').value = 'all';
    renderActiveStatFilters();

    applyWaiverFilters();
}

function applyWaiverFilters() {
    activeWaiverFilters.team = document.getElementById('filter-team-select').value;

    filteredWaiversData = waiversData.filter(p => {
        // Position Filter
        if (activeWaiverFilters.positions.size > 0 && !activeWaiverFilters.positions.has(p.position)) {
            return false;
        }

        // Team Filter
        if (activeWaiverFilters.team !== 'all' && p.team !== activeWaiverFilters.team) {
            return false;
        }

        // Stat Filters
        for (const rule of activeWaiverFilters.stats) {
            // Handle per game / per 90 logic if needed, OR just match visible view?
            // Usually filters apply to the raw total unless specified. 
            // Let's assume user filters on raw totals OR specifically toggles view.
            // For simplicity, let's filter on the Base Stats for now (Totals).
            // User can switch view to see PG/P90 but filtering on "Goals > 5" usually implies Total Goals.

            // Wait, if I'm in Per Game view, "Goals > 0.5" makes sense.
            // Let's map key based on current view for more advanced usage?
            // Or stick to totals for simplicity first. 
            // Given the dropdown lists "FPTS", "Goals", etc... let's check the property directly on `p`.
            // `p` has raw stats.

            const pVal = p[rule.key] || 0;
            if (pVal < rule.val) return false;
        }

        return true;
    });

    currentWaiversPage = 1; // Reset to page 1
    renderWaivers();
}


function renderWaivers() {
    // If we haven't filtered yet (first load), initialize
    if (filteredWaiversData.length === 0 && waiversData.length > 0 && activeWaiverFilters.positions.size === 0 && activeWaiverFilters.stats.length === 0) {
        filteredWaiversData = waiversData;
    }
    // If filtered data is empty but we have filters, it means 0 results. 
    // If not filtered (fresh page), ensure filteredWaiversData is waiversData.
    if (waiversData.length > 0 && filteredWaiversData.length === 0 &&
        (activeWaiverFilters.positions.size > 0 || activeWaiverFilters.stats.length > 0 || activeWaiverFilters.team !== 'all')) {
        // Should show "No results"
    } else if (filteredWaiversData.length === 0 && waiversData.length > 0) {
        // Fallback init
        filteredWaiversData = waiversData;
    }

    const tbody = document.getElementById('waivers-table-body');
    const start = (currentWaiversPage - 1) * WAIVERS_PAGE_SIZE;
    const end = start + WAIVERS_PAGE_SIZE;

    const displayData = filteredWaiversData.slice(start, end); // Use FILTERED data
    const totalPages = Math.ceil(filteredWaiversData.length / WAIVERS_PAGE_SIZE);

    // Update Pagination UI
    const pageInfo = document.getElementById('waivers-page-info');
    if (pageInfo) pageInfo.textContent = `Page ${currentWaiversPage} of ${totalPages || 1} (${filteredWaiversData.length} players)`;

    const btnPrev = document.getElementById('btn-prev-page');
    if (btnPrev) btnPrev.disabled = currentWaiversPage === 1;

    const btnNext = document.getElementById('btn-next-page');
    if (btnNext) btnNext.disabled = currentWaiversPage >= totalPages;

    // Add Rank (relative to filtered list)
    displayData.forEach((p, i) => p.rank = start + i + 1);

    if (displayData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="25" class="py-8 text-center text-gray-500">No players found matching filters.</td></tr>';
        return;
    }

    // Stats config matching user request with definitions (Short Codes + Tooltips)
    // Note: FPTS, Mins, GP are handled manually in HTML/Row generation to keep them fixed on left.
    const statsConfig = [
        { key: 'g', label: 'G', title: 'Goals scored' },
        { key: 'at', label: 'AT', title: 'Assists' },
        { key: 'sot', label: 'SOT', title: 'Shots on target' },
        { key: 'kp', label: 'KP', title: 'Key passes (assist to a shot)' },
        { key: 'tkw', label: 'TKW', title: 'Tackles won' },
        { key: 'int', label: 'INT', title: 'Interceptions' },
        { key: 'clr', label: 'CLR', title: 'Clearances' },
        { key: 'bs', label: 'BS', title: 'Blocked shots' },
        { key: 'aer', label: 'AER', title: 'Aerials won' },
        { key: 'cos', label: 'COS', title: 'Successful dribbles' }, // User wanted COS label.
        { key: 'cs', label: 'CS', title: 'Clean sheet (0 or 1)' }, // User wanted CS.
        { key: 'sv', label: 'SV', title: 'Saves (only relevant for goalkeepers)' },
        { key: 'ga', label: 'GAO', title: 'Goals against' }, // User wanted GAO label.
        { key: 'yc', label: 'YC', title: 'Yellow cards' },
        { key: 'rc', label: 'RC', title: 'Red cards' },
        { key: 'acnc', label: 'ACNC', title: 'Accurate crosses (non corners)' },
        { key: 'dis', label: 'DIS', title: 'Dispossessed' },
        { key: 'hcs', label: 'HCS', title: 'High contests succeeded' },
        { key: 'pks', label: 'PKS', title: 'Penalty kicks saved' },
        { key: 'sm', label: 'SM', title: 'Smothers' },
        { key: 'pkm', label: 'PKM', title: 'PK Missed' }, // Added missing ones if needed, or remove if not in user list? User list had 22 items.
        // User list checked: FPTS, G, AT, SOT, KP, TKW, INT, CLR, BS, AER, CS, SV, GAO, YC, RC, MIN, ACNC, COS, DIS, HCS, PKS, SM.
        // My list above covers them (FPTS/MIN handled separately).
        // I added PKM (PK Missed) and PKD (PK Drawn) and OG in previous config but user didn't explicitly list them in the "definitions" request.
        // I will keep them but maybe use short codes if I can guess them, or just hide them?
        // User said "The column headers should read like this...". implying ONLY these.
        // I will stick to the User's list primarily.
        // What about 'og'? I'll leave it out if not requested or add it with OG label.
        { key: 'og', label: 'OG', title: 'Own Goals' },
        { key: 'pkd', label: 'PKD', title: 'Penalty Drawn' }
    ];

    // Inject headers if placeholder exists
    const headerPlaceholder = document.getElementById('waivers-header-placeholder');
    if (headerPlaceholder) {
        const headersHTML = statsConfig.map(stat => `
            <th scope="col" 
                class="py-2 px-2 text-right border-r border-gray-700 cursor-pointer hover:text-white min-w-[40px] group relative" 
                onclick="sortWaivers('${stat.key}')">
                ${stat.label}
                <div class="absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-gray-900/95 text-white text-[10px] font-normal rounded shadow-xl border border-gray-600 opacity-0 group-hover:opacity-100 transition-opacity z-[60] pointer-events-none whitespace-nowrap">
                    ${stat.title}
                </div>
            </th>
        `).join('');
        headerPlaceholder.outerHTML = headersHTML;
    }

    tbody.innerHTML = displayData.map(p => {
        // Dynamic FPTS Value
        let fptsVal = p.fpts;
        if (currentWaiversView === 'per_game') fptsVal = p.fpts_per_game;
        if (currentWaiversView === 'per_90') fptsVal = p.fpts_per_90;

        // Generate stats cells dynamically based on view
        const statCells = statsConfig.map(stat => {
            let val = 0;
            let formattedVal = "";
            let dataKey = stat.key;

            if (currentWaiversView === 'season') {
                val = p[stat.key] || 0;
                formattedVal = val;
            } else if (currentWaiversView === 'per_game') {
                dataKey = `${stat.key}_per_game`;
                val = p[dataKey] || 0;
                formattedVal = val.toFixed(2);
            } else if (currentWaiversView === 'per_90') {
                dataKey = `${stat.key}_per_90`;
                val = p[dataKey] || 0;
                formattedVal = val.toFixed(2);
            }

            // Style zero values dimmer
            const style = parseFloat(val) !== 0 ? 'text-gray-300' : 'text-gray-700';

            return `<td class="py-2 px-2 text-right ${style} font-mono text-[11px] border-r border-gray-800 whitespace-nowrap">${formattedVal}</td>`;
        }).join('');

        return `
        <tr class="hover:bg-gray-800/50 transition-colors border-b border-gray-800 last:border-0 group h-[34px]">
            <td class="py-2 px-2 sticky left-0 bg-gray-900 group-hover:bg-gray-800 transition-colors border-r border-gray-800 text-gray-400 font-mono text-center z-20 text-[11px] font-bold shadow-[1px_0_0_rgba(55,65,81,1)]">${p.rank}</td>
            <td class="py-2 px-2 sticky left-[30px] bg-gray-900 group-hover:bg-gray-800 transition-colors border-r border-gray-800 font-medium text-white shadow-[2px_0_5px_rgba(0,0,0,0.5)] z-20 text-[11px] max-w-[120px] truncate" title="${p.player_name}">
                <button onclick="showPlayerDetails('${p.player_id}')" class="hover:text-blue-400 hover:underline text-left w-full truncate">${p.player_name}</button>
            </td>
            <td class="py-2 px-2 text-center font-bold text-[10px] border-r border-gray-800 whitespace-nowrap uppercase">
                ${(p.injured && p.injured !== 'Available') ?
                `<span class="${p.injured === 'Out' ? 'text-red-500' : 'text-orange-400'}">${p.injured}</span>` :
                '<span class="text-green-500/30">OK</span>'}
            </td>
            <td class="py-2 px-2 text-center text-gray-400 text-[10px] uppercase whitespace-nowrap">${p.team || '-'}</td>
            <td class="py-2 px-2 text-center font-bold text-[10px] bg-gray-800 rounded px-1 w-min whitespace-nowrap mx-auto border border-gray-700">${p.position}</td>
            
            <td class="py-2 px-2 text-right font-bold text-blue-400 font-mono text-[11px] border-r border-gray-700 whitespace-nowrap">${(fptsVal || 0).toFixed(2)}</td>
            
            <td class="py-2 px-2 text-right text-gray-500 font-mono text-[11px] border-r border-gray-800 whitespace-nowrap">${p.minutes}</td>
            <td class="py-2 px-2 text-right text-gray-500 font-mono text-[11px] border-r border-gray-800 whitespace-nowrap">${p.gp}</td>
            
            ${statCells}
        </tr>`
    }).join('');
}


// --- Player Details Modal ---

async function showPlayerDetails(playerId) {
    const modal = document.getElementById('player-modal');
    modal.classList.remove('hidden');

    // Reset Content
    document.getElementById('pm-name').textContent = "Loading...";
    document.getElementById('pm-meta').classList.add('hidden');
    document.getElementById('pm-season-stats').innerHTML = "";
    document.getElementById('pm-log-body').innerHTML = "";

    try {
        const response = await fetch(`/api/player/${playerId}`);
        const data = await response.json();

        // 1. Header
        document.getElementById('pm-name').textContent = data.profile.name;

        // Handle "False" or missing team/pos
        let pTeam = data.profile.team;
        if (!pTeam || pTeam === 'False' || pTeam === 'nan') pTeam = '-';

        let pPos = data.profile.position;
        if (!pPos || pPos === 'False' || pPos === 'nan') pPos = '-';

        document.getElementById('pm-team').textContent = pTeam;
        document.getElementById('pm-pos').textContent = pPos;
        document.getElementById('pm-meta').classList.remove('hidden');

        // 2. Season Grid
        // 2. Season Grid & 3. Game Log Headers
        const allStats = [
            { k: 'FPTS', l: 'FPTS', c: 'text-blue-400 font-bold' },
            { k: 'opp', l: 'Opp', c: 'text-gray-400 font-mono text-center' },
            { k: 'MIN', l: 'MIN', c: 'text-gray-500' },
            { k: 'G', l: 'G', c: 'text-green-400' },
            { k: 'KP', l: 'KP', c: 'text-gray-300' },
            { k: 'AT', l: 'AT', c: 'text-gray-300' },
            { k: 'SOT', l: 'SOT', c: 'text-gray-300' },
            { k: 'TKW', l: 'TKW', c: 'text-gray-400' },
            { k: 'DIS', l: 'DIS', c: 'text-red-400' },
            { k: 'YC', l: 'YC', c: 'text-yellow-400' },
            { k: 'RC', l: 'RC', c: 'text-red-500 font-bold' },
            { k: 'ACNC', l: 'ACNC', c: 'text-gray-400' },
            { k: 'INT', l: 'INT', c: 'text-gray-400' },
            { k: 'CLR', l: 'CLR', c: 'text-gray-400' },
            { k: 'COS', l: 'COS', c: 'text-gray-400' },
            { k: 'BS', l: 'BS', c: 'text-gray-400' },
            { k: 'AER', l: 'AER', c: 'text-gray-400' },
            { k: 'PKM', l: 'PKM', c: 'text-red-400' },
            { k: 'PKD', l: 'PKD', c: 'text-green-400' },
            { k: 'OG', l: 'OG', c: 'text-red-500' },
            { k: 'GAO', l: 'GAO', c: 'text-red-400' },
            { k: 'CS', l: 'CS', c: 'text-green-400 font-bold' },
            { k: 'GA', l: 'GA', c: 'text-red-400' },
            { k: 'Sv', l: 'SV', c: 'text-blue-300' },
            { k: 'PKS', l: 'PKS', c: 'text-green-400 font-bold' },
            { k: 'HCS', l: 'HCS', c: 'text-gray-400' },
            { k: 'Sm', l: 'SM', c: 'text-gray-400' }
        ];

        // --- Season Stats Grid ---
        data.season_stats['GP'] = data.game_log.length;

        // Add GP to front for Grid only
        const gridStats = [{ k: 'GP', l: 'GP', c: 'text-white font-bold' }, ...allStats.filter(s => s.k !== 'opp')];

        const gridHtml = gridStats.map(s => {
            let val = data.season_stats[s.k] || 0;
            if (s.k === 'FPTS') val = val.toFixed(2);

            // Optional: Hide zeros in grid to reduce clutter? Or show all as requested.
            // User said "display all the stats".
            return `
                <div class="bg-gray-800 p-3 rounded-lg border border-gray-700 text-center min-w-[80px]">
                    <div class="text-[10px] text-gray-500 uppercase font-bold mb-1 truncate" title="${s.l}">${s.l}</div>
                    <div class="text-lg ${s.c} font-mono">${val}</div>
                </div>
            `;
        }).join('');
        document.getElementById('pm-season-stats').innerHTML = gridHtml;

        // --- Game Log Table ---

        // Dynamic Headers
        const tableHead = document.querySelector('#player-modal thead tr');
        let headerHtml = `<th class="py-2 px-3 border-b border-gray-700 sticky left-0 bg-gray-800 z-10 w-16">Wk</th>`;
        allStats.forEach(s => {
            headerHtml += `<th class="py-2 px-2 border-b border-gray-700 text-right min-w-[50px] whitespace-nowrap text-[10px]">${s.l}</th>`;
        });
        tableHead.innerHTML = headerHtml;

        // Dynamic Rows
        const logHtml = data.game_log.map(row => {
            let cells = `<td class="py-2 px-3 border-b border-gray-700 text-gray-500 sticky left-0 bg-gray-900 z-10 font-bold border-r border-gray-800">W${row.week}</td>`;

            allStats.forEach(s => {
                let val = row[s.k] || 0;
                let displayVal = val;

                // Dim zeros
                const cellClass = val == 0 ? 'text-gray-700' : 'text-gray-300 font-mono';

                // Highlight non-zero goals acts etc
                let highlight = "";
                if (val > 0) {
                    if (['G', 'AT', 'CS', 'PKS'].includes(s.k)) highlight = "text-white font-bold bg-gray-800";
                    if (['RC', 'OG', 'PM'].includes(s.k)) highlight = "text-red-400 font-bold bg-red-900/10";
                }

                // Custom FPTS Display (Actual + Proj)
                if (s.k === 'FPTS') {
                    // Update: Round to 2 decimals
                    const actual = parseFloat(val).toFixed(2);
                    const proj = row.projected_fpts !== undefined ? parseFloat(row.projected_fpts).toFixed(2) : null;

                    highlight = val >= 15 ? "text-green-400 font-bold" : "text-blue-300 font-bold";

                    if (proj !== null) {
                        displayVal = `<div>${actual}</div><div class="text-[9px] text-gray-500 font-normal">Proj: ${proj}</div>`;
                    } else {
                        displayVal = actual;
                    }
                }

                cells += `<td class="py-2 px-2 border-b border-gray-700 text-right text-[11px] ${cellClass} ${highlight} whitespace-nowrap">${displayVal}</td>`;
            });

            return `<tr class="hover:bg-gray-800 transition-colors">${cells}</tr>`;
        }).join('');
        document.getElementById('pm-log-body').innerHTML = logHtml;

    } catch (e) {
        console.error(e);
        document.getElementById('pm-name').textContent = "Error loading player.";
    }
}

function closePlayerModal() {
    document.getElementById('player-modal').classList.add('hidden');
}

function sortWaivers(col) {
    if (sortCol === col) {
        sortAsc = !sortAsc;
    } else {
        sortCol = col;
        sortAsc = false; // Default to descending for stats

        // Exceptions for text columns
        if (['player_name', 'team', 'position'].includes(col)) sortAsc = true;
    }

    // Determine the actual key to sort by based on view
    let dataKey = col;
    // Columns that change based on view (stats + fpts)
    // Exclude: Text columns + GP + Minutes (usually fixed or no per-game variant relevant/available)
    const fixedColumns = ['rank', 'player_name', 'team', 'position', 'gp', 'minutes', 'injured'];

    if (!fixedColumns.includes(col)) {
        if (currentWaiversView === 'per_game') {
            dataKey = `${col}_per_game`;
        } else if (currentWaiversView === 'per_90') {
            dataKey = `${col}_per_90`;
        }
    }

    const compare = (a, b) => {
        let valA = a[dataKey];
        let valB = b[dataKey];

        // Handle strings
        if (typeof valA === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        } else {
            // Handle nulls/undefined as 0
            valA = valA || 0;
            valB = valB || 0;
        }

        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
    };

    // Sort filtered data (what user sees)
    filteredWaiversData.sort(compare);

    // Also sort master data so if filters cleared, order persists
    if (waiversData !== filteredWaiversData) {
        waiversData.sort(compare);
    }

    renderWaivers();
}

// --- Chat Clear Logic ---
async function clearChat() {
    try {
        // 1. Clear Backend Memory
        const response = await fetch('/api/chat/clear', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            // 2. Clear UI
            const chatContainer = document.getElementById('chat-messages');
            if (chatContainer) {
                // Restore Welcome Message
                chatContainer.innerHTML = `
                    <div class="flex flex-col items-center justify-center h-full text-center p-6 opacity-90">
                        <div class="text-5xl mb-6">🍺</div>
                        <h3 class="text-2xl font-bold text-white mb-2 tracking-tight">The Commissioner is IN.</h3>
                        <p class="text-gray-400 text-sm max-w-sm mb-8 italic leading-relaxed">
                            "Right, listen here. I've got the data, I've got the pints, and I've got absolutely zero
                            patience for your tragic management skills. State your business."
                        </p>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-md">
                            <button onclick="askQuestion('Who is the biggest bottler this season?')"
                                class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                                <span class="block text-blue-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-blue-300">Analysis</span>
                                <span class="text-gray-200 text-sm font-medium">"Who's the biggest bottler?"</span>
                            </button>

                            <button onclick="askQuestion('Roast the team in last place properly.')"
                                class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                                <span class="block text-red-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-red-300">Banter</span>
                                <span class="text-gray-200 text-sm font-medium">"Roast the last place team"</span>
                            </button>

                            <button onclick="askQuestion('Who should I pick up from waivers? Check for injuries.')"
                                class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                                <span class="block text-green-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-green-300">Strategy</span>
                                <span class="text-gray-200 text-sm font-medium">"Waiver wire analysis"</span>
                            </button>

                            <button onclick="askQuestion('What are the streets saying about Cole Palmer?')"
                                class="p-4 bg-gray-800/40 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 rounded-xl text-left transition-all hover:scale-[1.02] group shadow-lg">
                                <span class="block text-orange-400 text-[10px] uppercase tracking-wider font-bold mb-1 group-hover:text-orange-300">Social</span>
                                <span class="text-gray-200 text-sm font-medium">"What are the streets saying?"</span>
                            </button>
                        </div>
                    </div>
                `;
            }
        } else {
            console.error('Failed to clear chat history:', data.message);
        }
    } catch (error) {
        console.error('Error clearing chat:', error);
    }
}

// --- Chat PDF Download Logic ---
function downloadChatPDF() {
    const ts = document.getElementById('print-timestamp');
    if (ts) ts.textContent = new Date().toLocaleString();
    window.print();
}
