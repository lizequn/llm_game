from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any, TypeVar, Generic
from pydantic import BaseModel, Field
from loguru import logger

# Load environment variables
load_dotenv()
api_key = os.environ.get("OPENROUTER_API_KEY")

# Generic type for different output models
T = TypeVar('T', bound=BaseModel)

class LLMInterface(Generic[T]):
    """
    Interface for interacting with LLMs using pydantic_ai Agent.
    Supports variable prompts and structured output.
    """
    
    def __init__(self,result_type : type[T], model_name: str = "meta-llama/llama-3.3-70b-instruct"):
        """
        Initialize the LLM interface with the specified model.
        
        Args:
            model_name: The model identifier to use with OpenRouter
        """
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is not set")
        
        model = OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url='https://openrouter.ai/api/v1',
                api_key=api_key,
            ),
        )
        self.agent = Agent(model,result_type=result_type)
        
    
    async def generate_response(self, prompt_template: str, variables: Dict[str, Any]) -> T:
        """
        Generate a structured response from the LLM based on a prompt template with variables.
        
        Args:
            prompt_template: The prompt template with placeholders for variables
            variables: Dictionary of variables to substitute in the prompt template
            output_class: The Pydantic model class to structure the output
            
        Returns:
            An instance of the specified output_class containing the structured response
        """
        if variables is not None:
            # Format the prompt template with the provided variables
            formatted_prompt = prompt_template.format(**variables)
        else:
            formatted_prompt = prompt_template
        
        # Use the agent to generate a structured response
        try:
            response = await self.agent.run(
                formatted_prompt
            )
            return response
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise


# Example usage
async def example_usage():
    # Initialize the LLM interface
    llm = LLMInterface()
    
    

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())