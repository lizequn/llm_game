from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig, OmegaConf
import hydra
import re
from loguru import logger

@dataclass
class StateRules:
    """Class to hold rules for a character state"""
    ranges: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """String representation of StateRules"""
        return f"StateRules(ranges={self.ranges})"

@dataclass
class StateConfig:
    """Configuration for a single state"""
    name: str
    desc: str
    min: int
    max: int
    default: int
    no_analyse:bool = field(default=False)
    rules: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """String representation of StateConfig"""
        return f"StateConfig(name='{self.name}', desc='{self.desc}', min={self.min}, max={self.max}, default={self.default}, rules={self.rules})"

@dataclass
class CharacterStateConfig:
    # State configurations
    states: dict[str,StateConfig]

def __str__(self) -> str:
    """String representation of CharacterStateConfig"""
    states_str = "\n  ".join(str(state) for _,state in self.states.items())
    return f"{states_str}\n"



class CharacterState:
    def __init__(self, config: CharacterStateConfig):
        self.config = config
        self.state_names = self.config.states.keys()
        self.state_dicts = self.config.states
        self.state_values = {}
        self.no_analyse_name = [key for key,value in self.state_dicts.items() if value.no_analyse]
        for key,value in self.state_dicts.items():
            self.state_values[key] = value.default

    def set_name(self,name:str):
        self.name = name

    def _get_state_value(self,state_name):
        return self.state_values[state_name]

    def update_state(self,**kwards) -> None:
        """Update character state values, ensuring they stay within min/max bounds"""
        for state_name,state_value_delta in kwards.items():
            assert state_name in self.state_names, f"{state_name} not exists in {self.state_names}"
            new_value = self._get_state_value(state_name) + state_value_delta
            if new_value < self.state_dicts[state_name].min:
                new_value =  self.state_dicts[state_name].min
            elif new_value > self.state_dicts[state_name].max:
                new_value = self.state_dicts[state_name].max
            self.state_values[state_name] = new_value
            logger.info(f"update {state_name} to {new_value}")

    def _check_rules(self,curr_value:int,rule_str:str):
        if "-" not in rule_str:
            return curr_value == int(rule_str)
        min = int(rule_str.split("-")[0])
        max = int(rule_str.split("-")[1])
        return min<= curr_value <= max

    def get_rules(self):
        rule_results = {}
        for state_name in self.state_names:
            current_value = self.state_values[state_name]
            rules = self.state_dicts[state_name].rules
            for rule_condition,rule_prompt in rules.items():
                if self._check_rules(current_value,rule_condition):
                    rule_results[state_name] = rule_prompt
        return rule_results


def build_character_state(cfg:dict) -> CharacterState:
    character_state_dict = cfg.character
    character_state_names = character_state_dict.keys()

    character_state_config = CharacterStateConfig(states={})

    for character_state_name in character_state_names:
   
        state_config = StateConfig(name=character_state_name,
                    desc=character_state_dict[character_state_name]['desc'],
                    min=character_state_dict[character_state_name]['min'],
                    max=character_state_dict[character_state_name]['max'],
                    default=character_state_dict[character_state_name]['default'],
                    rules=character_state_dict[character_state_name]['rules'])
        character_state_config.states[character_state_name] = state_config
    cs = CharacterState(character_state_config)
    
    return cs

def build_user_state(cfg:dict) -> CharacterState:
    character_state_dict = cfg.user
    character_state_names = character_state_dict.keys()

    character_state_config = CharacterStateConfig(states={})

    for character_state_name in character_state_names:
        
        state_config = StateConfig(name=character_state_name,
                    desc=character_state_dict[character_state_name]['desc'],
                    min=character_state_dict[character_state_name]['min'],
                    max=character_state_dict[character_state_name]['max'],
                    default=character_state_dict[character_state_name]['default'],
                    rules=character_state_dict[character_state_name]['rules'],
                    no_analyse=character_state_dict[character_state_name].get('no_analyse',False))
        character_state_config.states[character_state_name] = state_config
    cs = CharacterState(character_state_config)
    cs.set_name == 'user'
    return cs
    
    

if __name__ == "__main__":

    build_character_state()

