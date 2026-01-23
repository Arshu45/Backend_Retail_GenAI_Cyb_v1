"""POC Agent: ReAct-style agent with a search and weather tool.

This script sets up:
- a DuckDuckGo search tool
- a small weather lookup tool (Weatherstack)
- a Groq-backed LLM (`ChatGroq`)
- a ReAct agent assembled and run via `AgentExecutor`

Before running, set environment variables (recommended):
- `GROQ_API_KEY` for the Groq model
- `WEATHERSTACK_KEY` for the weather API (optional; a default is used)
"""

from dotenv import load_dotenv
import os
import requests

from langchain_groq import ChatGroq
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langchain_classic.agents import create_react_agent, AgentExecutor
from langsmith import Client


# Load environment variables from .env if present
load_dotenv()


# ------------------
# Tools
# ------------------

# DuckDuckGo search tool provided by langchain_community
search_tool = DuckDuckGoSearchRun()


@tool
def get_weather_data(city: str) -> dict:
    """Fetch current weather for `city` using Weatherstack API.

    The API key can be provided via the `WEATHERSTACK_KEY` environment
    variable. The function returns the parsed JSON response.
    """
    access_key = os.getenv("WEATHERSTACK_KEY")
    url = f"https://api.weatherstack.com/current?access_key={access_key}&query={city}"

    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


# ------------------
# LLM Configuration
# ------------------

# Configure a Groq-hosted chat model. Ensure `GROQ_API_KEY` is set in env.
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)


# ------------------
# Agent assembly
# ------------------

# Pull a ReAct-style prompt template from LangSmith's prompt hub
client = Client()
prompt = client.pull_prompt("hwchase17/react")

# Create the ReAct agent with the LLM and tools
agent = create_react_agent(
    llm=llm,
    tools=[search_tool, get_weather_data],
    prompt=prompt,
)

# Wrap the agent with an executor to handle tool orchestration
agent_executor = AgentExecutor(
    agent=agent,
    tools=[search_tool, get_weather_data],
    # set verbose=True to see detailed agent step logs
)


def main() -> None:
    """Run the agent with user-provided input and print the result."""
    try:
        user_input = input("Enter your question: ")
        print("> Entering new AgentExecutor chain...")
        response = agent_executor.invoke({"input": user_input})
        print(response)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as exc:
        print("Agent run failed:", exc)


if __name__ == "__main__":
    main()


