import os

from openai import OpenAI


def make_client() -> OpenAI:
    return OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])


def model_name() -> str:
    return os.environ["LLM_MODEL"]
