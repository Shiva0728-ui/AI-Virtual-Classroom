import gymnasium as gym
from gymnasium import spaces
import numpy as np

class StudentEnv(gym.Env):
    """
    Simulates a student learning environment.
    The State vector:
    [
        topic_a_mastery (0.0 - 1.0),
        topic_b_mastery (0.0 - 1.0),
        topic_c_mastery (0.0 - 1.0),
        engagement_level (0.0 - 1.0),
        frustration_flag (0 = no, 1 = yes)
    ]
    
    The Action vector:
    0: Explain Topic
    1: Give Example
    2: Ask Easy Question
    3: Ask Hard Question
    4: Provide Encouragement/Remediation
    """
    def __init__(self, num_topics=3):
        super(StudentEnv, self).__init__()
        
        self.num_topics = num_topics
        # State space: 3 topics + engagement + frustration
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(num_topics + 2,), dtype=np.float32
        )
        
        # Action space: 5 possible instructional actions
        self.action_space = spaces.Discrete(5)
        
        self.state = None
        self.step_count = 0
        self.max_steps = 20
        self.target_topic = 0 # Currently teaching topic 0
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # Initialize student with low mastery, medium engagement, no frustration
        self.state = np.array([0.1, 0.1, 0.1, 0.8, 0.0], dtype=np.float32)
        self.step_count = 0
        self.target_topic = np.random.randint(0, self.num_topics)
        return self.state, {}
        
    def step(self, action):
        self.step_count += 1
        
        # Unpack state
        mastery = self.state[:self.num_topics]
        engagement = self.state[self.num_topics]
        frustration = self.state[self.num_topics + 1]
        
        reward = 0.0
        
        # Simulated Student Dynamics
        if action == 0: # Explain
            if engagement > 0.4:
                mastery[self.target_topic] = min(1.0, mastery[self.target_topic] + 0.1)
                engagement -= 0.05 # Lectures drop engagement slightly
            else:
                frustration = 1.0 # Not paying attention
            reward += 0.1

        elif action == 1: # Example
            if mastery[self.target_topic] > 0.2:
                mastery[self.target_topic] = min(1.0, mastery[self.target_topic] + 0.15)
                engagement = min(1.0, engagement + 0.1)
            reward += 0.2

        elif action == 2: # Easy Question
            if mastery[self.target_topic] > 0.3:
                # Correct answer
                engagement = min(1.0, engagement + 0.2)
                frustration = 0.0
                reward += 0.5
            else:
                # Wrong answer
                frustration = 1.0
                engagement -= 0.1
                reward -= 0.2

        elif action == 3: # Hard Question
            if mastery[self.target_topic] > 0.7:
                # Correct answer
                mastery[self.target_topic] = 1.0
                engagement = min(1.0, engagement + 0.3)
                frustration = 0.0
                reward += 1.0
            else:
                # Wrong answer
                frustration = 1.0
                engagement -= 0.2
                reward -= 0.5
                
        elif action == 4: # Encourage/Remediate
            frustration = 0.0
            engagement = min(1.0, engagement + 0.3)
            # Small bonus for keeping student engaged
            reward += 0.1
            
        # Update state
        self.state[:self.num_topics] = mastery
        self.state[self.num_topics] = engagement
        self.state[self.num_topics + 1] = frustration
        
        # Check termination
        terminated = bool(np.mean(mastery) >= 0.9)
        truncated = bool(self.step_count >= self.max_steps)
        
        # Add termination bonus
        if terminated:
            reward += 10.0
        
        return np.copy(self.state), reward, terminated, truncated, {}
