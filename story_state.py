from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig, OmegaConf
import hydra
import re
from loguru import logger
from character_state import StateRules, StateConfig, CharacterState, build_character_state,build_user_state

@dataclass
class StoryNodeConfig:
    """Configuration for a single story node/state"""
    name: str
    description: str
    next_state: List[Dict[str, Any]] = field(default_factory=list)
    
    def __str__(self) -> str:
        """String representation of StoryNodeConfig"""
        return f"StoryNodeConfig(name='{self.name}', description='{self.description}', next_state={self.next_state})"

@dataclass
class StoryStateConfig:
    """Configuration for the story state"""
    story_background: str = ""
    character_background: Dict[str, Dict[str, str]] = field(default_factory=dict)
    story_state: Dict[str, StoryNodeConfig] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """String representation of StoryStateConfig"""
        nodes_str = "\n  ".join(str(node) for _, node in self.story_state.items())
        return f"StoryStateConfig(\n  story_background='{self.story_background[:50]}...'\n  character_background={list(self.character_background.keys())}\n  story_state=[\n  {nodes_str}\n  ]\n)"


class StoryState:
    def __init__(self, config: StoryStateConfig):
        """Initialize the story state with configuration and optional character state"""
        self.config = config
        self.character_states = {}  # Dictionary to store multiple character states
        self.user_state = None      # User state
        self.story_background = config.story_background
        self.character_background = config.character_background
        self.story_nodes = config.story_state
        self.current_node_id = None
        self.node_history = []
        
    def set_character_state(self, character_name: str, character_state: CharacterState):
        """Set a character state to use for condition evaluation"""
        self.character_states[character_name] = character_state
        
    def set_user_state(self, user_state: CharacterState):
        """Set the user state to use for condition evaluation"""
        self.user_state = user_state
        
    def start_story(self, start_node_id: str = None):
        """Start the story at the specified node or the first node in the config"""
        if start_node_id is None:
            # Default to the first node in the config
            if self.story_nodes:
                start_node_id = next(iter(self.story_nodes))
            else:
                logger.error("No story nodes available to start")
                return False
                
        if start_node_id in self.story_nodes:
            self.current_node_id = start_node_id
            self.node_history = [start_node_id]
            logger.info(f"Story started at node: {start_node_id}")
            return True
        else:
            logger.error(f"Start node {start_node_id} not found in story config")
            return False
    
    def get_current_node(self) -> Optional[StoryNodeConfig]:
        """Get the current story node"""
        if self.current_node_id and self.current_node_id in self.story_nodes:
            return self.story_nodes[self.current_node_id]
        return None
    
    def _parse_condition(self, condition_str: str) -> tuple:
        """Parse a condition string into entity, variable, operator, and value"""
        # Match patterns like "character1.tension >= 70" or "user.evening_phase == 1"
        match = re.match(r'([\w\.]+)\s*([<>=!+-]+)\s*(-?\d+)', condition_str)
        if match:
            full_var_name, operator, value = match.groups()
            
            # Split the variable name into entity and attribute
            parts = full_var_name.split('.')
            if len(parts) == 2:
                entity, var_name = parts
                return entity, var_name, operator, int(value)
            else:
                logger.error(f"Invalid variable format in condition: {condition_str}")
                return None, None, None, None
        return None, None, None, None
    
    def _evaluate_condition(self, condition_str: str) -> bool:
        """Evaluate a single condition string against character or user state"""
        entity, var_name, operator, value = self._parse_condition(condition_str)
        
        if entity is None or var_name is None:
            logger.error(f"Failed to parse condition: {condition_str}")
            return False
        
        # Determine which state object to use based on the entity prefix
        state_obj = None
        if entity == "user":
            if not self.user_state:
                logger.warning("No user state available to evaluate condition")
                return False
            state_obj = self.user_state
        elif entity.startswith("character"):
            if entity not in self.character_states:
                logger.warning(f"Character state {entity} not available to evaluate condition")
                return False
            state_obj = self.character_states[entity]
        else:
            logger.error(f"Unknown entity in condition: {entity}")
            return False
        
        # Check if the variable exists in the state
        if var_name not in state_obj.state_values:
            logger.error(f"Variable {var_name} not found in {entity} state")
            return False
        
        current_value = state_obj.state_values[var_name]
        
        # Evaluate the condition
        if operator == "==":
            return current_value == value
        elif operator == "!=":
            return current_value != value
        elif operator == ">":
            return current_value > value
        elif operator == ">=":
            return current_value >= value
        elif operator == "<":
            return current_value < value
        elif operator == "<=":
            return current_value <= value
        else:
            logger.error(f"Unsupported operator: {operator}")
            return False
    
    def _evaluate_conditions(self, conditions: List[str]) -> bool:
        """Evaluate a list of conditions (using OR logic)"""
        if not conditions:
            return True
        
        # Use OR logic for multiple conditions
        return any(self._evaluate_condition(cond) for cond in conditions)
    
    def _apply_effect(self, effect_str: str) -> bool:
        """Apply a single effect to the character or user state"""
        entity, var_name, operator, value = self._parse_condition(effect_str)
        
        if entity is None or var_name is None:
            logger.error(f"Failed to parse effect: {effect_str}")
            return False
        
        # Determine which state object to use based on the entity prefix
        state_obj = None
        if entity == "user":
            if not self.user_state:
                logger.warning("No user state available to apply effect")
                return False
            state_obj = self.user_state
        elif entity.startswith("character"):
            if entity not in self.character_states:
                logger.warning(f"Character state {entity} not available to apply effect")
                return False
            state_obj = self.character_states[entity]
        else:
            logger.error(f"Unknown entity in effect: {entity}")
            return False
        
        # Check if the variable exists in the state
        if var_name not in state_obj.state_values:
            logger.error(f"Variable {var_name} not found in {entity} state")
            return False
        
        current_value = state_obj.state_values[var_name]
        
        # Calculate the new value
        if operator == "=":
            new_value = value
        elif operator == "+=":
            new_value = current_value + value
        elif operator == "-=":
            new_value = current_value - value
        elif operator == "*=":
            new_value = current_value * value
        elif operator == "/=":
            if value == 0:
                logger.error("Division by zero in effect")
                return False
            new_value = current_value / value
        else:
            logger.error(f"Unsupported operator: {operator}")
            return False
        
        # Update the state using its own method to ensure bounds checking
        update_dict = {var_name: new_value - current_value}  # Convert to delta for update_state
        state_obj.update_state(**update_dict)
        logger.info(f"Applied effect: {effect_str}, new value: {state_obj.state_values[var_name]}")
        return True
    
    def _apply_effects(self, effects: List[str]) -> bool:
        """Apply a list of effects to the character or user state"""
        if not effects:
            return True
        
        return all(self._apply_effect(effect) for effect in effects)
    
    def advance_story(self) -> Optional[StoryNodeConfig]:
        """Advance the story to the next node based on conditions"""
        current_node = self.get_current_node()
        if not current_node:
            logger.error("No current node to advance from")
            return None
        
        # If there are no next states, we've reached an end node
        if not current_node.next_state:
            logger.info(f"Reached end node: {self.current_node_id}")
            return current_node
        
        # Check each possible next state
        for transition in current_node.next_state:
            conditions = transition.get("condition", [])
            next_node_id = transition.get("next_node")
            effects = transition.get("effects", [])
            
            if self._evaluate_conditions(conditions):
                # Apply effects before transitioning
                self._apply_effects(effects)
                
                # Transition to the next node
                if next_node_id in self.story_nodes:
                    self.current_node_id = next_node_id
                    self.node_history.append(next_node_id)
                    logger.info(f"Advanced to node: {next_node_id}")
                    return self.story_nodes[next_node_id]
                else:
                    logger.error(f"Next node {next_node_id} not found in story config")
        
        logger.warning("No valid transitions found from current node")
        return current_node
    
    def get_node_history(self) -> List[str]:
        """Get the history of visited nodes"""
        return self.node_history
    
    def get_story_background(self) -> str:
        """Get the story background"""
        return self.story_background
    
    def get_character_background(self, character_id: str = None) -> Dict[str, str]:
        """Get character background for a specific character or all characters"""
        if character_id:
            return self.character_background.get(character_id, {})
        return self.character_background


@hydra.main(config_path="config", config_name="config", version_base="1.1")
def build_story_state(cfg: dict) -> StoryState:
    """Build a StoryState instance from configuration"""
    story_config_dict = cfg.story
    
    # Create StoryNodeConfig instances for each story node
    story_nodes = {}
    if "story_state" in story_config_dict:
        for node_id, node_data in story_config_dict.story_state.items():
            node_config = StoryNodeConfig(
                name=node_data.get("name", ""),
                description=node_data.get("description", ""),
                next_state=node_data.get("next_state", [])
            )
            story_nodes[node_id] = node_config
    
    # Create the StoryStateConfig
    story_state_config = StoryStateConfig(
        story_background=story_config_dict.get("story_background", ""),
        character_background=story_config_dict.get("character_background", {}),
        story_state=story_nodes
    )
    
    # Create and return the StoryState
    story_state = StoryState(story_state_config)
    logger.info(f"Built StoryState with {len(story_nodes)} nodes")
    return story_state

@hydra.main(config_path="config", config_name="config", version_base="1.1")
def test_story_state(cfg: dict):
    # Build character states
    character1_state = build_character_state(cfg)
    character2_state = build_character_state(cfg)
    user_state = build_user_state(cfg)
    
    # Build story state
    story_state = build_story_state(cfg)
    
    # Set character and user states
    story_state.set_character_state("character1", character1_state)
    story_state.set_character_state("character2", character2_state)
    story_state.set_user_state(user_state)

    # Start the story
    story_state.start_story("arrival")
    current_node = story_state.get_current_node()
    print(f"Started at: {current_node.name}")
    print(f"Description: {current_node.description}")
    
    # Advance the story
    story_state.advance_story()
    current_node = story_state.get_current_node()
    print(f"Advanced to: {current_node.name}")
    print(f"Description: {current_node.description}")

    # Advance the story
    character1_state.state_values['tension'] = 80
    story_state.advance_story()
    current_node = story_state.get_current_node()
    print(f"Advanced to: {current_node.name}")
    print(f"Description: {current_node.description}")


if __name__ == "__main__":
    test_story_state()