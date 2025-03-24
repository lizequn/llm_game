from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
# Import pydantic-ai correctly - commented out until correct import path is determined
# from pydantic_ai import ... # Correct import to be determined
from loguru import logger
from character_state import CharacterState
from story_state import StoryState

class CharacterPrompt(BaseModel):
    """Model for character-specific prompt information"""
    name: str
    background: str
    current_state_description: str = ""
    
    def __str__(self) -> str:
        """String representation of character prompt"""
        return f"## {self.name}\n{self.background}\n\nCurrent state: {self.current_state_description}"

class StoryPrompt(BaseModel):
    """Model for story-specific prompt information"""
    background: str
    current_node_name: str = ""
    current_node_description: str = ""
    
    def __str__(self) -> str:
        """String representation of story prompt"""
        return f"# Story Background\n{self.background}\n\n# Current Situation\n{self.current_node_name}: {self.current_node_description}"

class UserPrompt(BaseModel):
    """Model for user-specific prompt information"""
    current_state_description: str = ""
    
    def __str__(self) -> str:
        """String representation of user prompt"""
        return f"## User State\n{self.current_state_description}"

class PromptContext(BaseModel):
    """Complete context for generating LLM prompts"""
    story: StoryPrompt
    characters: Dict[str, CharacterPrompt]
    user: Optional[UserPrompt] = None
    # character_states: Dict[str, Dict[str, int]]
    character_state_descriptions: Dict[str, Dict[str, str]]
    # user_state: Optional[Dict[str, int]] = None
    user_state_description: Optional[Dict[str, str]] = None
    
    def __str__(self) -> str:
        """String representation of the complete prompt context"""
        story_str = str(self.story)
        characters_str = "\n\n".join(str(char) for char in self.characters.values())
        
        # Add user state if available
        user_str = ""
        if self.user:
            user_str = f"\n\n{str(self.user)}"
        
        # # Character states
        # states_str = "\n".join([f"# Character States",
        #                       "\n".join([f"{char_name}: {states}"
        #                                 for char_name, states in self.character_states.items()])])
        
        # # Add user state values if available
        # if self.user_state:
        #     states_str += f"\n\n# User State\n{self.user_state}"
        
        return f"{story_str}\n\n{characters_str}{user_str}\n\n"

# This is a placeholder class that would be replaced with the actual pydantic-ai implementation
class LLMPromptTemplate:
    """Placeholder for LLM prompt template functionality"""
    
    def __init__(self, template: str):
        self.template = template
    
    def format(self, **kwargs) -> str:
        """Format the template with the provided kwargs"""
        return self.template.format(**kwargs)

class PromptBuilder:
    """
    Builds prompts for the LLM based on story and character states.
    This class is responsible for generating prompts that will be sent to the LLM
    to generate conversation and narrative content.
    """
    
    def __init__(self, story_state: StoryState):
        """
        Initialize the PromptBuilder with story state.
        The story state contains all character states and user state.
        
        Args:
            story_state: The current state of the story, containing character states and user state
        """
        self.story_state = story_state
        
        # Define the conversation prompt template
        self.conversation_template = LLMPromptTemplate("""
You are an AI assistant helping to generate dialogue between characters for an interactive narrative game.

Based on the following history and context about the story, characters, user, and their current states,
generate a realistic conversation snippet that reflects the current situation and character dynamics.                                                   
                                                       
Context:
{context}
                                                       
History:
{history}

Generate a conversation snippet between the characters that:
1. Reflects the current story node and situation
2. Shows the characters' personalities and backgrounds
3. Incorporates their current emotional and psychological states
4. Maintains appropriate tension and dynamics based on character states
5. Takes into account the user's current state and preferences
6. Feels natural and realistic
7. End with open ended situation to wait for User's response.
                                                       
The conversation should be 3-8 exchanges between the characters and finally wait for the user's response.
""")
    
    def _build_character_prompts(self) -> Dict[str, CharacterPrompt]:
        """
        Build character prompts based on character backgrounds and current states.
        
        Returns:
            Dictionary of character prompts keyed by character ID
        """
        character_prompts = {}
        character_backgrounds = self.story_state.get_character_background()
        
        for char_id, char_info in character_backgrounds.items():
            # Create a character prompt for each character
            character_prompts[char_id] = CharacterPrompt(
                name=char_info.get("name", f"Character {char_id}"),
                background=char_info.get("background", ""),
                current_state_description=self._get_character_state_description(char_id)
            )
        
        return character_prompts
    
    def _get_character_state_description(self, char_id: str) -> str:
        """
        Get a description of the character's current state based on state rules.
        
        Args:
            char_id: The ID of the character
            
        Returns:
            A string describing the character's current state
        """
        # Check if the character state exists in the story state
        if char_id not in self.story_state.character_states:
            logger.warning(f"Character state for {char_id} not found")
            return "Unknown state"
        
        # Get the rules that apply to the current character state
        character_state = self.story_state.character_states[char_id]
        rules = character_state.get_rules()
        
        # Format the rules into a readable description
        descriptions = []
        for state_name, description in rules.items():
            descriptions.append(f"{state_name}: {description}")
        
        return "; ".join(descriptions)
    
    def _build_user_prompt(self) -> Optional[UserPrompt]:
        """
        Build user prompt based on user state.
        
        Returns:
            UserPrompt object containing user state information, or None if no user state
        """
        if not self.story_state.user_state:
            return None
        
        # Get the rules that apply to the current user state
        rules = self.story_state.user_state.get_rules()
        
        # Format the rules into a readable description
        descriptions = []
        for state_name, description in rules.items():
            descriptions.append(f"{state_name}: {description}")
        
        state_description = "; ".join(descriptions)
        
        return UserPrompt(current_state_description=state_description)
    
    def _build_story_prompt(self) -> StoryPrompt:
        """
        Build a story prompt based on the current story state.
        
        Returns:
            StoryPrompt object containing story background and current node information
        """
        current_node = self.story_state.get_current_node()
        
        return StoryPrompt(
            background=self.story_state.get_story_background(),
            current_node_name=current_node.name if current_node else "",
            current_node_description=current_node.description if current_node else ""
        )
    
    def _get_character_states(self) -> Dict[str, Dict[str, int]]:
        """
        Get the current numerical states for all characters.
        
        Returns:
            Dictionary of character states keyed by character ID
        """
        states = {}
        
        # Get states for all characters
        for char_id, char_state in self.story_state.character_states.items():
            states[char_id] = char_state.state_values
        
        return states
    
    def _get_character_state_descriptions(self) -> Dict[str, Dict[str, str]]:
        """
        Get text descriptions for all character states based on rules.
        
        Returns:
            Dictionary of character state descriptions keyed by character ID and state name
        """
        descriptions = {}
        
        # Get descriptions for all characters
        for char_id, char_state in self.story_state.character_states.items():
            descriptions[char_id] = char_state.get_rules()
        
        return descriptions
    
    def _get_user_state(self) -> Optional[Dict[str, int]]:
        """
        Get the current numerical state for the user.
        
        Returns:
            Dictionary of user state values, or None if no user state
        """
        if not self.story_state.user_state:
            return None
        
        return self.story_state.user_state.state_values
    
    def _get_user_state_description(self) -> Optional[Dict[str, str]]:
        """
        Get text descriptions for user state based on rules.
        
        Returns:
            Dictionary of user state descriptions, or None if no user state
        """
        if not self.story_state.user_state:
            return None
        
        return self.story_state.user_state.get_rules()
    
    def build_prompt_context(self) -> PromptContext:
        """
        Build the complete prompt context from story, character states, and user state.
        
        Returns:
            PromptContext object containing all information needed for prompt generation
        """
        return PromptContext(
            story=self._build_story_prompt(),
            characters=self._build_character_prompts(),
            user=self._build_user_prompt(),
            # character_states=self._get_character_states(),
            character_state_descriptions=self._get_character_state_descriptions(),
            # user_state=self._get_user_state(),
            user_state_description=self._get_user_state_description()
        )
    
    
    def generate_conversation_prompt(self,history=None) -> str:
        """
        Generate a prompt specifically for conversation generation.
        
        Returns:
            A formatted string prompt for generating conversations
        """
        context = str(self.build_prompt_context())
        return self.conversation_template.format(context=context,history=history)

def build_prompt_builder(story_state: StoryState) -> PromptBuilder:
    """
    Factory function to create a PromptBuilder instance.
    
    Args:
        story_state: The current state of the story, containing character states and user state
        
    Returns:
        A configured PromptBuilder instance
    """
    return PromptBuilder(story_state)

if __name__ == "__main__":
    # Example usage
    from hydra import initialize, compose
    
    # Initialize Hydra
    with initialize(version_base="1.1", config_path="config"):
        # Compose the configuration
        cfg = compose(config_name="config")
        
        # Build character, user, and story states
        from character_state import build_character_state, build_user_state
        from story_state import build_story_state
        
        character1_state = build_character_state(cfg)
        character2_state = build_character_state(cfg)
        user_state = build_user_state(cfg)
        story_state = build_story_state(cfg)
        
        # Set the character and user states for the story
        story_state.set_character_state("character1", character1_state)
        story_state.set_character_state("character2", character2_state)
        story_state.set_user_state(user_state)
        
        # Start the story at the "arrival" node
        story_state.start_story("arrival")
        
        # Build the prompt builder
        prompt_builder = build_prompt_builder(story_state)
        
        # Generate a prompt
        prompt = prompt_builder.generate_prompt()
        print("\nGenerated Prompt:\n")
        print(prompt)
        
        # Generate a conversation prompt
        conversation_prompt = prompt_builder.generate_conversation_prompt()
        print("\nGenerated Conversation Prompt:\n")
        print(conversation_prompt)
        
        # Note: To use this with an actual LLM, you would send the conversation_prompt
        # to your LLM API and get the generated conversation back