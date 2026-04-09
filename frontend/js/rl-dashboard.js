const RLDashboard = {
    chart: null,

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
            this.renderChart(data);
            this.updateMetrics(data);
        } catch (error) {
            console.error("Error loading RL Dashboard:", error);
        }
    },

    updateMetrics(data) {
        // Calculate average of last 100 episodes
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

    renderChart(data) {
        // Delay slightly to ensure the page is fully visible and canvas has dimensions
        setTimeout(() => {
            const ctx = document.getElementById('rl-convergence-chart');
            if (!ctx) return;

            // Generate labels (episodes) based on array length
            const maxLen = Math.max((data.ppo || []).length, (data.dqn || []).length);
            const labels = Array.from({length: maxLen}, (_, i) => i + 1);

            // Map Rule-Based baseline as a straight line
            const ruleBasedData = Array(maxLen).fill(data.rule_based || 0);

            const config = {
                type: 'line',
                data: {
                labels: labels,
                datasets: [
                    {
                        label: 'PPO (Proximal Policy Optimization)',
                        data: data.ppo || [],
                        borderColor: '#10b981', // green
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'DQN (Deep Q-Network)',
                        data: data.dqn || [],
                        borderColor: '#38bdf8', // blue
                        backgroundColor: 'rgba(56, 189, 248, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'Rule-Based Baseline',
                        data: ruleBasedData,
                        borderColor: '#f59e0b', // orange
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false
                    }
                ]
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
                        position: 'top',
                        labels: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary') || '#ffffff'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Training Episodes',
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted') || '#a0aec0'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: '#a0aec0'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Cumulative Reward',
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted') || '#a0aec0'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: '#a0aec0'
                        }
                    }
                }
            }
        };

        if (this.chart) {
            this.chart.destroy();
        }

        this.chart = new Chart(ctx, config);
        }, 100);
    }
};

window.RLDashboard = RLDashboard;
