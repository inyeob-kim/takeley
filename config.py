import os
from dotenv import load_dotenv
import logging
 
logger = logging.getLogger(__name__)

def set_environment(): 
    print("Setting Environment Variables...")
    # Load environment variables based on environment

    environment = os.getenv("ENVIRONMENT", 'local')  # Choose between [local, production]
    env_file = f'.env.{environment}'
    print(f"Environment File : {env_file}")
    load_dotenv(env_file)

    # Debugging: Print all loaded environment variables    
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY is None:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
    if TWITTER_API_KEY is None:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
    if TWITTER_API_SECRET is None:
        raise ValueError("TWITTER_API_SECRET environment variable is not set")
    
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
    if TWITTER_ACCESS_TOKEN is None:
        raise ValueError("TWITTER_ACCESS_TOKEN environment variable is not set")
    
    TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    if TWITTER_ACCESS_TOKEN_SECRET is None:
        raise ValueError("TWITTER_ACCESS_TOKEN_SECRET environment variable is not set")


    