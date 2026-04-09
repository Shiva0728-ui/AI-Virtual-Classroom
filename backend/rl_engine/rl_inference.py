import os
import sys

# Add current dir to path to find the modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ppo_agent import PPOAgent
    from dqn_agent import DQNAgent
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    print("Warning: PyTorch not found. RL Agents disabled, using Rule-Based fallback.")

from rule_based_agent import RuleBasedAgent

class RLEngineInference:
    """Singleton helper to interface the RL models with the rest of the backend."""
    _instance = None
    
    def __init__(self, mode="ppo"):
        self.mode = mode if RL_AVAILABLE else "rule_based"
        self.num_topics = 3
        
        if RL_AVAILABLE:
            # Load PPO as default
            self.ppo = PPOAgent(state_size=5, action_size=5)
            ppo_path = os.path.join(os.path.dirname(__file__), "models", "ppo_model.pth")
            self.ppo.load(ppo_path)
            
            # Load DQN
            self.dqn = DQNAgent(state_size=5, action_size=5)
            dqn_path = os.path.join(os.path.dirname(__file__), "models", "dqn_model.pth")
            self.dqn.load(dqn_path)
        else:
            self.ppo = None
            self.dqn = None
            
        # Load Baseline
        self.rule_based = RuleBasedAgent(num_topics=3)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls("ppo")
        return cls._instance

    def get_instructional_action(self, progress_dict, current_concept_idx):
        """
        Translates student progress into an RL State Vector and returns the action text.
        """
        # 1. Build State Vector
        mastery = progress_dict.get('understanding', 0) / 100.0
        questions_asked = progress_dict.get('questions_asked', 0)
        correct_answers = progress_dict.get('correct_answers', 0)
        
        # Heuristics for the state vector simulation
        engagement = 1.0 if (questions_asked < 5) else 0.5
        frustration = 1.0 if (questions_asked > 0 and correct_answers / questions_asked < 0.4) else 0.0
        
        # State: [topic0, topic1, topic2, engagement, frustration]
        state = [
            mastery if current_concept_idx == 0 else 0.8,
            mastery if current_concept_idx == 1 else 0.1,
            mastery if current_concept_idx == 2 else 0.0,
            engagement,
            frustration
        ]
        
        # 2. Select Action Index
        if self.mode == "ppo" and RL_AVAILABLE:
            action_idx = self.ppo.select_action_deterministic(state)
        elif self.mode == "dqn" and RL_AVAILABLE:
            action_idx = self.dqn.select_action(state, explore=False)
        else:
            self.mode = "rule_based" # Force output state
            action_idx = self.rule_based.select_action(state, min(current_concept_idx, 2))
            
        # 3. Translate to text for LLM Prompt Injection
        actions = {
            0: "EXPLAIN the next concept using an analogy.",
            1: "GIVE A REAL-WORLD EXAMPLE of the current concept.",
            2: "ASK AN EASY QUESTION to check basic understanding.",
            3: "ASK A HARD, CRITICAL THINKING QUESTION to challenge the student.",
            4: "PROVIDE ENCOURAGEMENT AND REMEDIATION. Re-explain simply, as the student seems frustrated."
        }
        
        return actions.get(action_idx, actions[0]), self.mode, action_idx
