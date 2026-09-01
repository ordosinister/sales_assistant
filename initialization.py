import configparser
import logging
import os

from path import get_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def credential_init():
    """
    Initializes and sets environment variables for API keys from a configuration file.

    This function reads a configuration file named 'credentials.ini' located in the 'config' directory.
    It extracts API keys for different services (OpenAI, SERPER, and TAVILY) and sets them as environment variables.

    The configuration file should have the following structure:

    [openai]
    api_key = your_openai_api_key

    Raises:
        KeyError: If any of the required sections or keys are missing in the configuration file.
        FileNotFoundError: If the 'credentials.ini' file is not found in the specified directory.

    Example:
        To use this function, simply call it at the beginning of your script:

        credential_init()

        This will set the necessary environment variables for the APIs to be used later in your code.

    """

    credential_file = get_file("config/credentials.ini")

    credentials = configparser.ConfigParser()
    credentials.read(credential_file)
    os.environ["OLLAMA_API_KEY"] = credentials["ollama"].get("api_key")


if __name__ == "__main__":

    from langchain_ollama import ChatOllama

    credential_init()

    llm = ChatOllama(model="deepseek-v4-pro:cloud", base_url="https://ollama.com", name="main", temperature=0)

    print(llm.invoke("Hello"))
