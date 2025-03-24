from pydantic_LLM import LLMInterface
from character_state import CharacterState
from story_state import StoryState
from typing import Dict, List, Optional, Any, Type
from pydantic import BaseModel, Field, create_model
from loguru import logger

class StateChange(BaseModel):
    """Model for state changes with reasoning"""
    value: int = Field(description="The delta value to apply to the state (positive or negative)")
    reasoning: str = Field(description="Reasoning for why this state should change")

def create_state_changes_model(state_names: List[str], prefix: str = "") -> Type[BaseModel]:
    """
    Dynamically create a Pydantic model for state changes based on the provided state names.
    
    Args:
        state_names: List of state names to include in the model
        prefix: Optional prefix for the field descriptions
        
    Returns:
        A dynamically created Pydantic model class
    """
    fields = {}
    for state_name in state_names:
        fields[state_name] = (Optional[StateChange], Field(None, description=f"{prefix}Change in {state_name} level"))
    
    return create_model("DynamicStateChanges", **fields)

class ConversationAnalyzer:
    """
    Analyzes conversations between characters and user responses,
    then updates character and user states based on the analysis.
    """
    
    def __init__(self, story_state: StoryState):
        """
        Initialize the ConversationAnalyzer with story state.
        
        Args:
            story_state: The current state of the story, containing character states and user state
        """
        self.story_state = story_state
        
        # Dynamically create state change models based on actual state names
        self.character_state_names = self._get_character_state_names()
        self.user_state_names = self._get_user_state_names()
        
        # Create dynamic models for character and user state changes
        self.CharacterStateChanges = create_state_changes_model(self.character_state_names, "Character ")
        self.UserStateChanges = create_state_changes_model(self.user_state_names, "User ")
        
        # Create the output model dynamically
        character_ids = list(self.story_state.character_states.keys())
        output_fields = {
            "summary": (str, Field(description="A brief summary of the conversation analysis"))
        }
        
        # Add fields for each character
        for char_id in character_ids:
            output_fields[f"{char_id}_changes"] = (
                self.CharacterStateChanges, 
                Field(description=f"State changes for {char_id}")
            )
        
        # Add field for user changes
        output_fields["user_changes"] = (
            self.UserStateChanges,
            Field(description="State changes for the user")
        )
        
        # Create the output model
        self.ConversationAnalysisOutput = create_model("DynamicConversationAnalysisOutput", **output_fields)
        
        # Initialize the LLM interface with the dynamic output model
        self.llm = LLMInterface(self.ConversationAnalysisOutput)
    
    def _get_character_state_names(self) -> List[str]:
        """
        Get the names of all character states from the configuration.
        
        Returns:
            List of character state names
        """
        # Get the first character state to extract state names
        # Assuming all characters have the same state structure
        if not self.story_state.character_states:
            logger.warning("No character states found")
            return []
        
        first_character = next(iter(self.story_state.character_states.values()))
        return list(first_character.state_values.keys())
    
    def _get_user_state_names(self) -> List[str]:
        """
        Get the names of all user states from the configuration.
        
        Returns:
            List of user state names
        """
        if not self.story_state.user_state:
            logger.warning("No user state found")
            return []
        return [name for name in list(self.story_state.user_state.state_values.keys()) if name not in self.story_state.user_state.no_analyse_name]
        
    
    def _build_analysis_prompt(self, dialogue: List[str], user_response: str) -> str:
        """
        Build a prompt for the LLM to analyze the conversation.
        
        Args:
            dialogue: List of dialogue lines from the conversation
            user_response: The user's response to the conversation
            
        Returns:
            A formatted prompt string for the LLM
        """
        # Get character names and backgrounds
        character_backgrounds = self.story_state.get_character_background()
        
        # Format dialogue
        dialogue_text = "\n".join(dialogue)
        
        # Start building the prompt
        prompt = f"""
You are an AI assistant analyzing a conversation in an interactive narrative game.

# Story Context
{self.story_state.get_story_background()}

# Current Situation
{self.story_state.get_current_node().description if self.story_state.get_current_node() else "Unknown situation"}

# Characters
"""
        
        # Add information for each character
        for char_id, char_state in self.story_state.character_states.items():
            char_name = character_backgrounds.get(char_id, {}).get("name", char_id)
            char_background = character_backgrounds.get(char_id, {}).get("background", "")
            
            prompt += f"""
## {char_name}
{char_background}

Current States:
"""
            
            # Add all states for this character
            for state_name, state_value in char_state.state_values.items():
                # Get min and max values for this state
                state_config = char_state.state_dicts.get(state_name)
                min_val = state_config.min if state_config else 0
                max_val = state_config.max if state_config else 100
                
                prompt += f"- {state_name}: {state_value} ({min_val}-{max_val})\n"
        
        # Add user state information
        if self.story_state.user_state:
            user_state = self.story_state.user_state
            
            prompt += f"""
# User
Current States:
"""
            
            # Add all user states
            for state_name, state_value in user_state.state_values.items():
                # Get min and max values for this state
                state_config = user_state.state_dicts.get(state_name)
                min_val = state_config.min if state_config else 0
                max_val = state_config.max if state_config else 100
                
                # Add special description for player_role if it exists
                if state_name == "player_role":
                    # Get character names for the description
                    char_ids = list(self.story_state.character_states.keys())
                    if len(char_ids) >= 2:
                        char1_name = character_backgrounds.get(char_ids[0], {}).get("name", char_ids[0])
                        char2_name = character_backgrounds.get(char_ids[1], {}).get("name", char_ids[1])
                        prompt += f"- {state_name}: {state_value} ({min_val}-{max_val}, where {min_val} is allied with {char2_name}, {(min_val + max_val) // 2} is neutral, {max_val} is allied with {char1_name})\n"
                    else:
                        prompt += f"- {state_name}: {state_value} ({min_val}-{max_val})\n"
                else:
                    prompt += f"- {state_name}: {state_value} ({min_val}-{max_val})\n"
        
        # Add conversation and user response
        prompt += f"""
# Recent Conversation
{dialogue_text}

# User's Response
{user_response}

Based on the conversation and the user's response, analyze how the states of the characters and user should change.
For each state, provide a delta value (positive or negative) and reasoning.

Consider:
"""
        
        # Add considerations based on character states
        for state_name in self.character_state_names:
            prompt += f"- How the dialogue affects {state_name} between characters\n"
        
        # Add considerations for user states
        for state_name in self.user_state_names:
            if state_name == "player_role":
                prompt += f"- Whether the user is taking sides or remaining neutral\n"
            else:
                prompt += f"- How the user's response affects {state_name}\n"
        
        prompt += """
Provide delta values that are reasonable (typically between -15 and +15) and proportional to the significance of the interaction.
"""
        
        return prompt
    
    async def analyze_conversation(self, dialogue: List[str], user_response: str) -> Any:
        """
        Analyze a conversation and generate state changes.
        
        Args:
            dialogue: List of dialogue lines from the conversation
            user_response: The user's response to the conversation
            
        Returns:
            ConversationAnalysisOutput containing state changes
        """
        # Build the prompt
        prompt = self._build_analysis_prompt(dialogue, user_response)
        
        # Call the LLM
        try:
            response = await self.llm.generate_response(prompt, None)
            analysis = response.data
            logger.info(f"Conversation analysis complete: {analysis.summary}")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing conversation: {str(e)}")
            raise
    
    def apply_state_changes(self, analysis: Any) -> None:
        """
        Apply the state changes from the analysis to the character and user states.
        
        Args:
            analysis: ConversationAnalysisOutput containing state changes
        """
        # Apply changes to each character
        for char_id, char_state in self.story_state.character_states.items():
            changes_field = f"{char_id}_changes"
            if hasattr(analysis, changes_field):
                char_changes = getattr(analysis, changes_field)
                changes = {}
                
                # Process each state change
                for state_name in self.character_state_names:
                    if hasattr(char_changes, state_name) and getattr(char_changes, state_name) is not None:
                        state_change = getattr(char_changes, state_name)
                        changes[state_name] = state_change.value
                        logger.info(f"{char_id} {state_name} change: {changes[state_name]} - {state_change.reasoning}")
                
                # Apply changes if any
                if changes:
                    char_state.update_state(**changes)
        
        # Apply changes to user
        user_state = self.story_state.user_state
        if user_state and hasattr(analysis, "user_changes"):
            user_changes = analysis.user_changes
            changes = {}
            
            # Process each user state change
            for state_name in self.user_state_names:
                if hasattr(user_changes, state_name) and getattr(user_changes, state_name) is not None:
                    state_change = getattr(user_changes, state_name)
                    changes[state_name] = state_change.value
                    logger.info(f"User {state_name} change: {changes[state_name]} - {state_change.reasoning}")
            
            # Apply changes if any
            if changes:
                user_state.update_state(**changes)
        
        logger.info(f"Applied all state changes from conversation analysis")

async def analyze_conversation_and_update_states(
    dialogue: List[str], 
    user_response: str, 
    story_state: StoryState
) -> Dict[str, Any]:
    """
    Analyze a conversation and update character and user states.
    
    Args:
        dialogue: List of dialogue lines from the conversation
        user_response: The user's response to the conversation
        story_state: The current story state
        
    Returns:
        Dictionary containing analysis results and updated states
    """
    analyzer = ConversationAnalyzer(story_state)
    analysis = await analyzer.analyze_conversation(dialogue, user_response)
    analyzer.apply_state_changes(analysis)
    
    # Return a dictionary with analysis results and updated states
    result = {
        "analysis": analysis.dict(),
        "updated_states": {
            char_id: state.state_values 
            for char_id, state in story_state.character_states.items()
        }
    }
    
    # Add user state if available
    if story_state.user_state:
        result["updated_states"]["user"] = story_state.user_state.state_values
    
    return result

# Example usage
if __name__ == "__main__":
    import asyncio
    from hydra import initialize, compose
    
    async def test_conversation_analysis():
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
            
            # Example dialogue
            dialogue = [
                "Grace: Welcome! I'm so glad you could make it. What do you think of the new living room arrangement?",
                "Trip: (calling from another room) I'll be right there! Just finishing up a call.",
                "Grace: (rolling her eyes slightly) He's always on a call these days.",
                "Trip: (entering) Sorry about that. Work never stops. (looks around) You changed the furniture again?",
                "Grace: Just a few adjustments. I thought it opened up the space more.",
                "Trip: (with a tight smile) It's... different. Anyway, great to see you! How have you been?"
            ]
            
            # Example user response
            user_response = "The room looks beautiful, Grace. And Trip, it's good to see you too. How have you both been?"
            
            # Analyze the conversation and update states
            result = await analyze_conversation_and_update_states(dialogue, user_response, story_state)
            
            # Print the results
            print("\nAnalysis Summary:")
            print(result["analysis"]["summary"])
            
            print("\nUpdated States:")
            for char_id, states in result["updated_states"].items():
                if char_id != "user":
                    print(f"{char_id}: {states}")
            
            print(f"User: {result['updated_states'].get('user', {})}")
    
    asyncio.run(test_conversation_analysis())