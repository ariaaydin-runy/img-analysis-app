import os
from dotenv import load_dotenv

load_dotenv()

# Your OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Analysis settings
MAX_IMAGES_PER_PROPERTY = 25
ANALYSIS_DELAY = 2  # seconds between API calls
