import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import json
from environment import StudentEnv
from dqn_agent import DQNAgent
from ppo_agent import PPOAgent
from rule_based_agent import RuleBasedAgent

def train_dqn(env, episodes=500):
    print("--- Training DQN Agent ---")
    agent = DQNAgent(state_size=env.observation_space.shape[0], action_size=env.action_space.n)
    rewards_history = []
    
    for e in range(episodes):
        state, _ = env.reset()
        total_reward = 0
        done = False
        
        while not done:
            action = agent.select_action(state)
            next_state, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            
            agent.remember(state, action, reward, next_state, done)
            state = next_state
            total_reward += reward
            
            agent.replay(batch_size=32)
            
        agent.update_target_network()
        rewards_history.append(total_reward)
        
        if (e + 1) % 50 == 0:
            print(f"Episode {e+1}/{episodes} - Reward: {total_reward:.2f} - Epsilon: {agent.epsilon:.2f}")
            
    # Save model
    os.makedirs('models', exist_ok=True)
    agent.save('models/dqn_model.pth')
    return rewards_history

def train_ppo(env, episodes=500):
    print("\n--- Training PPO Agent ---")
    agent = PPOAgent(state_size=env.observation_space.shape[0], action_size=env.action_space.n)
    rewards_history = []
    
    for e in range(episodes):
        state, _ = env.reset()
        total_reward = 0
        done = False
        
        while not done:
            action, logprob = agent.select_action(state)
            next_state, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            
            agent.store_transition(state, action, logprob, reward, done)
            state = next_state
            total_reward += reward
            
        agent.update()
        rewards_history.append(total_reward)
        
        if (e + 1) % 50 == 0:
            print(f"Episode {e+1}/{episodes} - Reward: {total_reward:.2f}")
            
    # Save model
    os.makedirs('models', exist_ok=True)
    agent.save('models/ppo_model.pth')
    return rewards_history

def evaluate_rule_based(env, episodes=100):
    print("\n--- Evaluating Rule-Based Baseline ---")
    agent = RuleBasedAgent(num_topics=env.num_topics)
    rewards_history = []
    
    for e in range(episodes):
        state, _ = env.reset()
        total_reward = 0
        done = False
        
        while not done:
            action = agent.select_action(state, env.target_topic)
            next_state, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            
            state = next_state
            total_reward += reward
            
        rewards_history.append(total_reward)
        
    print(f"Average Rule-Based Reward over {episodes} episodes: {np.mean(rewards_history):.2f}")
    return rewards_history

def plot_convergence(dqn_rewards, ppo_rewards, rb_rewards):
    # Smooth the rewards
    def moving_average(a, n=20):
        ret = np.cumsum(a, dtype=float)
        ret[n:] = ret[n:] - ret[:-n]
        return ret[n - 1:] / n
        
    plt.figure(figsize=(10, 6))
    plt.plot(moving_average(dqn_rewards), label='DQN')
    plt.plot(moving_average(ppo_rewards), label='PPO')
    plt.axhline(y=np.mean(rb_rewards), color='r', linestyle='--', label='Rule-Based Baseline')
    
    plt.title('Reward Convergence Trends (Training phase)')
    plt.xlabel('Episodes')
    plt.ylabel('Cumulative Reward (Moving Average)')
    plt.legend()
    plt.grid(True)
    
    os.makedirs('results', exist_ok=True)
    plt.savefig('results/convergence_plot.png')
    
    # Save data for the Javascript dashboard
    with open('results/training_data.json', 'w') as f:
        json.dump({
            "dqn": list(moving_average(dqn_rewards)),
            "ppo": list(moving_average(ppo_rewards)),
            "rule_based": float(np.mean(rb_rewards))
        }, f)
        
    print("Saved plot to results/convergence_plot.png and data to results/training_data.json")

if __name__ == "__main__":
    env = StudentEnv()
    
    rb_rewards = evaluate_rule_based(env, episodes=200)
    dqn_rewards = train_dqn(env, episodes=1000)
    ppo_rewards = train_ppo(env, episodes=1000)
    
    plot_convergence(dqn_rewards, ppo_rewards, rb_rewards)
