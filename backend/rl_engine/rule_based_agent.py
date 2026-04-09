class RuleBasedAgent:
    """
    Baseline Rule-Based Intelligent Tutoring System logic.
    Provides a simple decision tree instructional sequencer based on hard-coded rules.
    """
    def __init__(self, num_topics=3):
        self.num_topics = num_topics
        
    def select_action(self, state, target_topic):
        """
        State: [topic_0, topic_1, topic_2, engagement, frustration]
        Actions: 
        0: Explain Topic
        1: Give Example
        2: Ask Easy Question
        3: Ask Hard Question
        4: Provide Encouragement/Remediation
        """
        mastery = state[target_topic]
        engagement = state[self.num_topics]
        frustration = state[self.num_topics + 1]
        
        # Rule 1: High frustration requires remediation immediately
        if frustration > 0.5:
            return 4
            
        # Rule 2: Low engagement requires a mix-up (Easy Question) or Engagement
        if engagement < 0.3:
            return 2 if mastery > 0.3 else 4
            
        # Rule 3: Very low mastery requires Explanation
        if mastery < 0.2:
            return 0
            
        # Rule 4: Moderate mastery requires Examples or Easy Questions
        if mastery < 0.6:
            return 1 if engagement > 0.5 else 2
            
        # Rule 5: High mastery requires Hard Questions
        if mastery >= 0.6:
            return 3
            
        # Fallback
        return 0
