import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.distributions import Categorical
import numpy as np
import os

class ActorCritic(nn.Module):
    def __init__(self, state_size, action_size):
        super(ActorCritic, self).__init__()
        # Shared feature extractor
        self.fc1 = nn.Linear(state_size, 64)
        
        # Actor head (Policy)
        self.actor_fc = nn.Linear(64, 64)
        self.actor_out = nn.Linear(64, action_size)
        
        # Critic head (Value)
        self.critic_fc = nn.Linear(64, 64)
        self.critic_out = nn.Linear(64, 1)
        
    def forward(self        , state):
        x = F.relu(self.fc1(state))
        
        # Actor
        act = F.relu(self.actor_fc(x))
        action_probs = F.softmax(self.actor_out(act), dim=-1)
        
        # Critic
        crit = F.relu(self.critic_fc(x))
        state_value = self.critic_out(crit)
        
        return action_probs, state_value

class PPOAgent:
    """
    Proximal Policy Optimization Agent.
    """
    def __init__(self, state_size=5, action_size=5, lr=3e-4, gamma=0.99, eps_clip=0.2):
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.eps_clip = eps_clip
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy = ActorCritic(state_size, action_size).to(self.device)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=lr)
        
        # Memory buffer
        self.states = []
        self.actions = []
        self.logprobs = []
        self.rewards = []
        self.is_terminals = []
        
    def select_action(self, state):
        state = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action_probs, _ = self.policy(state)
            
        dist = Categorical(action_probs)
        action = dist.sample()
        
        action_logprob = dist.log_prob(action)
        
        return action.item(), action_logprob.item()
        
    def select_action_deterministic(self, state):
        # Used for inference in production
        state = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action_probs, _ = self.policy(state)
        return torch.argmax(action_probs, dim=-1).item()
        
    def store_transition(self, state, action, action_logprob, reward, is_terminal):
        self.states.append(state)
        self.actions.append(action)
        self.logprobs.append(action_logprob)
        self.rewards.append(reward)
        self.is_terminals.append(is_terminal)
        
    def update(self):
        if not self.states:
            return
            
        # Compute discounted continuous rewards
        rewards = []
        discounted_reward = 0
        for reward, is_terminal in zip(reversed(self.rewards), reversed(self.is_terminals)):
            if is_terminal:
                discounted_reward = 0
            discounted_reward = reward + (self.gamma * discounted_reward)
            rewards.insert(0, discounted_reward)
            
        rewards = torch.tensor(rewards, dtype=torch.float32).to(self.device)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)
        
        # Convert lists to tensors
        old_states = torch.FloatTensor(np.array(self.states)).to(self.device)
        old_actions = torch.LongTensor(np.array(self.actions)).to(self.device)
        old_logprobs = torch.FloatTensor(np.array(self.logprobs)).to(self.device)
        
        # Optimize policy for K epochs:
        for _ in range(4): # K epochs
            action_probs, state_values = self.policy(old_states)
            dist = Categorical(action_probs)
            
            logprobs = dist.log_prob(old_actions)
            dist_entropy = dist.entropy()
            
            # Find ratio (pi_theta / pi_theta__old)
            ratios = torch.exp(logprobs - old_logprobs.detach())
            
            # Find Surrogate Loss
            advantages = rewards - state_values.squeeze().detach()
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages
            
            loss = -torch.min(surr1, surr2) + 0.5 * nn.MSELoss()(state_values.squeeze(), rewards) - 0.01 * dist_entropy
            
            # Take gradient step
            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()
            
        # Clear memory
        self.states.clear()
        self.actions.clear()
        self.logprobs.clear()
        self.rewards.clear()
        self.is_terminals.clear()
        
    def save(self, name):
        torch.save(self.policy.state_dict(), name)

    def load(self, name):
        if os.path.exists(name):
            self.policy.load_state_dict(torch.load(name, map_location=self.device))
            self.policy.eval()
            print(f"Loaded PPO model from {name}")
        else:
            print(f"Model file {name} not found. Using untrained weights.")
