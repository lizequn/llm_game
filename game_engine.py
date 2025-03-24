from pydantic_LLM import LLMInterface
from hydra import initialize, compose
from character_state import build_character_state, build_user_state
from story_state import build_story_state
from prompt_builder import build_prompt_builder
from conversation_analyse import analyze_conversation_and_update_states
from typing import Dict, List, Optional, Any, TypeVar, Generic
from pydantic import BaseModel, Field
from loguru import logger


class ConversationOutput(BaseModel):
    """Structured output for a conversation between characters"""
    dialogue: list[str] = Field(description="The generated conversation between characters")
    situation_summary: str = Field(description="A brief summary of the current situation in one to two sentences")


class GameEngine:
    """
    Main game engine that manages the story flow, character states,
    conversation generation, and state updates based on user input.
    """
    
    def __init__(self, character_ids=None):
        """
        Initialize the game engine with configuration
        
        Args:
            character_ids: Optional list of character IDs to use. If None, defaults to ["character1", "character2"]
        """
        # Default character IDs if not provided
        self.character_ids = character_ids or ["character1", "character2"]
        
        # Initialize Hydra
        with initialize(version_base="1.1", config_path="config"):
            # Compose the configuration
            self.cfg = compose(config_name="config")
            
            # Build character states
            self.character_states = {}
            for char_id in self.character_ids:
                self.character_states[char_id] = build_character_state(self.cfg)
            
            # Build user state
            self.user_state = build_user_state(self.cfg)
            
            # Build story state
            self.story_state = build_story_state(self.cfg)
            
            # Set the character and user states for the story
            for char_id, char_state in self.character_states.items():
                self.story_state.set_character_state(char_id, char_state)
            
            self.story_state.set_user_state(self.user_state)
            
            # Initialize LLM interface
            self.llm = LLMInterface(ConversationOutput)
            
            # Build the prompt builder
            self.prompt_builder = build_prompt_builder(self.story_state)
            
            # Initialize conversation history
            self.conversation_history = []
            self.current_dialogue = []
    
    async def start_story(self, start_node: str = "arrival"):
        """
        Start the story at the specified node.
        
        Args:
            start_node: The node ID to start the story at
        """
        # Start the story
        success = self.story_state.start_story(start_node)
        if not success:
            logger.error(f"Failed to start story at node: {start_node}")
            return False
        
        # Generate initial conversation
        await self.generate_conversation()
        
        return True
    
    async def generate_conversation(self):
        """
        Generate a conversation based on the current story state.
        """
        # Build the prompt
        prompt = self.prompt_builder.generate_conversation_prompt(
            history="\n".join(self.conversation_history) if self.conversation_history else None
        )
        
        # Generate the conversation
        try:
            result = await self.llm.generate_response(prompt, None)
            conversation = result.data
            
            # Store the current dialogue
            self.current_dialogue = conversation.dialogue
            
            # Print the dialogue
            for text in conversation.dialogue:
                print(text)
            
            print("\n" + conversation.situation_summary + "\n")
            
            return conversation
        except Exception as e:
            logger.error(f"Error generating conversation: {str(e)}")
            raise
    
    async def process_user_input(self, user_response: str):
        """
        Process user input, analyze the conversation, and update states.
        
        Args:
            user_response: The user's response to the conversation
        """
        if not self.current_dialogue:
            logger.warning("No current dialogue to analyze")
            return
        
        # Add user response to conversation history
        self.conversation_history.extend(self.current_dialogue)
        self.conversation_history.append(f"You: {user_response}")
        
        # Analyze the conversation and update states
        try:
            analysis_result = await analyze_conversation_and_update_states(
                self.current_dialogue, 
                user_response, 
                self.story_state
            )
            
            logger.info(f"Conversation analysis: {analysis_result['analysis']['summary']}")
            
            # Check if story should advance based on updated states
            current_node = self.story_state.get_current_node()
            if current_node and current_node.next_state:
                # Try to advance the story
                next_node = self.story_state.advance_story()
                if next_node and next_node != current_node:
                    logger.info(f"Advanced to new story node: {next_node.name}")
            
            # Generate new conversation based on updated states
            await self.generate_conversation()
            
            return analysis_result
        except Exception as e:
            logger.error(f"Error processing user input: {str(e)}")
            raise
    
    def get_character_states(self):
        """
        Get the current character states.
        
        Returns:
            Dictionary of character states
        """
        # Dynamically get all character states
        states = {
            char_id: char_state.state_values 
            for char_id, char_state in self.story_state.character_states.items()
        }
        
        # Add user state
        if self.story_state.user_state:
            states["user"] = self.story_state.user_state.state_values
        
        return states
    
    def get_current_node(self):
        """
        Get the current story node.
        
        Returns:
            The current story node
        """
        return self.story_state.get_current_node()


async def run_interactive():
    """Run the game in interactive mode"""
    engine = GameEngine()
    
    # Start the story
    await engine.start_story()
    
    # Main game loop
    while True:
        # Get user input
        user_input = input("\nYour response: ")
        
        # Check for exit command
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Exiting game...")
            break
        
        # Process user input
        await engine.process_user_input(user_input)
        
        # Print current states (for debugging)
        states = engine.get_character_states()
        print("\nCurrent States:")
        for char_id, state_values in states.items():
            if char_id != "user":
                print(f"{char_id}: {state_values}")
        print(f"User: {states.get('user', {})}")
        
        # Check if we've reached an end node
        current_node = engine.get_current_node()
        if current_node and not current_node.next_state:
            print("\nYou've reached the end of the story.")
            break


async def run_demo():
    """Run a simple demo with predefined user inputs"""
    engine = GameEngine()
    
    # Start the story
    await engine.start_story()
    
    # Predefined user responses
    responses = [
        "The room looks beautiful, Grace. And Trip, it's good to see you too. How have you both been?",
        "It sounds like you've both been busy. How is your design work going, Grace?",
        "That sounds exciting! And Trip, how's work been for you lately?"
    ]
    
    # Process each response
    for response in responses:
        print(f"\nYour response: {response}")
        await engine.process_user_input(response)
        
        # Print current states
        states = engine.get_character_states()
        print("\nCurrent States:")
        for char_id, state_values in states.items():
            if char_id != "user":
                print(f"{char_id}: {state_values}")
        print(f"User: {states.get('user', {})}")


if __name__ == "__main__":
    import asyncio
    
    # Choose which mode to run
    interactive_mode = True
    
    if interactive_mode:
        asyncio.run(run_interactive())
    else:
        asyncio.run(run_demo())