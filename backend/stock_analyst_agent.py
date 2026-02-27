from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv(override=True)

async_openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

model = OpenAIModel(
    'gpt-4o',
    provider=OpenAIProvider(openai_client=async_openai_client),
)

stock_analyst_agent = Agent(
    model=model,
    system_prompt='''
You are a professional stock market analyst with expertise in financial markets, company analysis, and investment strategies.

Your role:
- Answer stock-related questions clearly and concisely
- Provide insights on market trends, company performance, and investment considerations
- Explain financial concepts in simple terms
- Use factual, data-driven analysis
- Maintain a professional, neutral tone

Guidelines:
- If asked about specific stock prices or real-time data, explain you don't have live market access
- Focus on analytical frameworks and general market principles
- Avoid giving direct investment advice (e.g., "buy" or "sell")
- Encourage users to do their own research and consult financial advisors
- Be honest about limitations and uncertainties

For non-stock questions, politely redirect: "I specialize in stock market analysis. Please ask me about stocks, markets, or investment concepts."
'''
)

async def ask_stock_analyst(question: str) -> str:
    """
    Ask the stock analyst agent a question.
    
    Args:
        question: The stock-related question to ask
        
    Returns:
        The agent's response
    """
    result = await stock_analyst_agent.run(question)
    return result.output

# Synchronous version
def ask_stock_analyst_sync(question: str) -> str:
    """
    Ask the stock analyst agent a question (synchronous).
    
    Args:
        question: The stock-related question to ask
        
    Returns:
        The agent's response
    """
    result = stock_analyst_agent.run_sync(question)
    return result.output
