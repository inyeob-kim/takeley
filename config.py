import os
from dotenv import load_dotenv
import logging
 
logger = logging.getLogger(__name__)

def set_environment(): 
    # Load environment variables based on environment

    environment = os.getenv("ENVIRONMENT", 'local')  # Choose between [local, production]
    env_file = f'.env.{environment}'
    load_dotenv(env_file)

    # Debugging: Print all loaded environment variables    
 
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY is None:
        logger.error("OPENAI_API_KEY environment variable is not set")
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    