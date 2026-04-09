const RLDashboard = {
    chartPPO: null,
    chartDQN: null,
    chartLearner: null,

    init() {
        console.log("RL Dashboard initializing...");
    },

    async loadStats() {
        try {
            const token = AppState.token;
            if (!token) return;

            const response = await fetch('/api/rl/stats', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) throw new Error("Failed to load RL stats");

            const data = await response.json();
            this.renderCharts(data);
            this.updateMetrics(data);
        } catch (error) {
            console.error("Error loading RL Dashboard:", error);
        }
    },

    updateMetrics(data) {
        const avg = (arr) => {
            if (!arr || arr.length === 0) return 0;
            const slice = arr.slice(-100);
            const sum = slice.reduce((a, b) => a + b, 0);
            return (sum / slice.length).toFixed(2);
        };

        const ppoAvg = avg(data.ppo);
        const dqnAvg = avg(data.dqn);
        const ruleAvg = typeof data.rule_based === "number" ? data.rule_based.toFixed(2) : 0;

        document.getElementById('rl-ppo-avg').textContent = ppoAvg;
        document.getElementById('rl-dqn-avg').textContent = dqnAvg;
        document.getElementById('rl-rule-avg').textContent = ruleAvg;
    },

    renderCharts(data) {
        setTimeout(() => {
            if (this.chartPPO) this.chartPPO.destroy();
            if (this.chartDQN) this.chartDQN.destroy();
            if (this.chartLearner) this.chartLearner.destroy();

            const ctxPPO = document.getElementById('rl-ppo-chart');
            const ctxDQN = document.getElementById('rl-dqn-chart');
            const ctxLearner = document.getElementById('rl-learner-state-chart');

            if (!ctxPPO || !ctxDQN || !ctxLearner) return;

            const maxLen = Math.max((data.ppo || []).length, (data.dqn || []).length, 100);
            const labels = Array.from({length: maxLen}, (_, i) => i + 1);
            const ruleBasedData = Array(maxLen).fill(data.rule_based || 0);

            // Base options for styling
            const baseOptions = {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { color: '#ffffff' } },
                    tooltip: {
                        callbacks: {
                            label: function(context) { return context.dataset.label + ': ' + context.parsed.y.toFixed(2); }
                        }
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Training Episodes', color: '#a0aec0' },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a0aec0' }
                    },
                    y: {
                        title: { display: true, text: 'Cumulative Reward', color: '#a0aec0' },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a0aec0' }
                    }
                }
            };

            // 1. PPO Chart
            this.chartPPO = new Chart(ctxPPO, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'PPO',
                            data: data.ppo || [],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0
                        },
                        {
                            label: 'Rule-Based Baseline',
                            data: ruleBasedData,
                            borderColor: '#f59e0b',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: false
                        }
                    ]
                },
                options: JSON.parse(JSON.stringify(baseOptions))
            });

            // 2. DQN Chart
            this.chartDQN = new Chart(ctxDQN, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'DQN',
                            data: data.dqn || [],
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0
                        },
                        {
                            label: 'Rule-Based Baseline',
                            data: ruleBasedData,
                            borderColor: '#f59e0b',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            fill: false
                        }
                    ]
                },
                options: JSON.parse(JSON.stringify(baseOptions))
            });

            // 3. Learner State Evolution Chart
            const learnerData = data.learner_state || { mastery: [], engagement: [], frustration: [] };
            const stateOptions = JSON.parse(JSON.stringify(baseOptions));
            stateOptions.scales.y.title.text = 'Metric Level (0-100)';
            stateOptions.scales.y.suggestedMin = 0;
            stateOptions.scales.y.suggestedMax = 100;

            this.chartLearner = new Chart(ctxLearner, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Mastery',
                            data: learnerData.mastery,
                            borderColor: '#8b5cf6', // purple
                            backgroundColor: 'rgba(139, 92, 246, 0.1)',
                            borderWidth: 3,
                            tension: 0.4,
                            pointRadius: 0
                        },
                        {
                            label: 'Engagement',
                            data: learnerData.engagement,
                            borderColor: '#f59e0b', // orange
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0
                        },
                        {
                            label: 'Frustration',
                            data: learnerData.frustration,
                            borderColor: '#ef4444', // red
                            borderWidth: 2,
                            borderDash: [4, 4],
                            tension: 0.3,
                            pointRadius: 0,
                            fill: false
                        }
                    ]
                },
                options: stateOptions
            });

        }, 100);
    }
};

window.RLDashboard = RLDashboard;
