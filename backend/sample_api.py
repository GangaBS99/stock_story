import json
import random
import re
import time
from typing import  Dict, List
from bs4 import BeautifulSoup
from pydantic_ai import Agent, RunContext
from openai import OpenAI, AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from dotenv import load_dotenv
from tavily import AsyncTavilyClient
import os
import shutil
from itertools import chain
from pydantic_ai.providers.openai import OpenAIProvider
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import nest_asyncio
import yfinance as yf
import pandas as pd
from pydantic import BaseModel
import datetime
import requests
from openai import OpenAI
from collections import defaultdict
from ws_braodcast import broadcast_summary
from token_tracker import add_tool_tokens
from tiktoken import encoding_for_model
encoding = encoding_for_model("gpt-4o")  # or your specific model name

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

load_dotenv(override=True)
nest_asyncio.apply()
client2 = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


openai_client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


async_openai_client = AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)

model = OpenAIModel(
    'gpt-4o',
    provider=OpenAIProvider(openai_client=async_openai_client),
)


agent = Agent(
    model=model,
    deps_type=dict,

system_prompt = '''
You are the Stock Story Generator – a smart, conversational financial agent.

🎯 Mission:
Craft compelling, data-driven narratives about a company’s stock by combining weekly price movements with relevant financial news.

🛠️ Tools Available:
• get_ticker_symbol – Retrieve the stock ticker.
• get_weekly_stock_data – Fetch weekly price data.
• find_weeks_with_significant_change – Identify weeks with >5% price change.
• build_date_ranges_from_weeks – Convert weeks into date ranges.
• summarize_date_ranges_sequentially – Sequentially fetch and summarize articles per week.
• rerank_articles – Rerank articles by relevance to stock movement.
• summarize_articles – Summarize a batch of articles.
• generatestockstory – Generate a final narrative using weekly summaries.

📌 Workflow:

1️⃣ Ask the user:  
**“Which company would you like to analyze? And what date range are you interested in?”**

2️⃣ Get the stock ticker:  
Use `get_ticker_symbol`.

3️⃣ Fetch stock data:  
Use `get_weekly_stock_data` for the user’s date range.

4️⃣ Detect significant weeks:  
Use `find_weeks_with_significant_change` to find >5% changes.

5️⃣ Build date ranges:  
Use `build_date_ranges_from_weeks` (format: MM/DD/YYYY).

6️⃣ After finding significant weeks, always display them in a formatted list showing the date and percentage then:  
Say: **“These weeks had significant movements. Would you like to analyze the related news or add more weeks?”**



7️⃣ If the user says "analyze news":
📍 Next Step show this response:
“In the next step I’m going to analyze news articles for these weeks. I’ll fetch relevant headlines, extract key content, and show you the weekly summaries. Shall I continue?”
• Call `summarize_date_ranges_sequentially` with the full list of date ranges.  
• This tool calls `gather_articles_for_summarization` **one-by-one** for each date range, enabling progressive streaming and storing summaries in order.

8️⃣ If the user wants to add a week:
📍 Next Step:
“Okay, I’ll add this week to our analysis. Then I’ll look at news stories for all selected weeks, extract insights, and show you the summaries. Shall I continue?”
• Call `build_date_ranges_from_weeks` to include the new week.
• Then call `summarize_date_ranges_sequentially` with the updated list of date ranges.
• This tool calls `gather_articles_for_summarization` **one-by-one** for each date range, enabling progressive streaming and storing summaries in order.

9️⃣ After generating all summaries show ONLY this exact message (nothing else):  
"Now I can generate a complete story using these summaries. You can also remove any summary if it seems off. Ready for the full narrative?"

🚫 DO NOT:
- List or describe the summaries
- Add any introductory text like "The news articles for the weeks..."
- Include placeholder text like "[insert summary details here]"
- Show any other commentary


🔟 If the user agrees:  
• Call `generate_stock_story`.
• **CRITICAL:** Your response to the user must be the **EXACT** text returned by the `generate_stock_story` tool. 
• Do **NOT** add any introduction like "Here is your story..." or any conclusion.
• Just output the story text directly as your entire response.

💬 After the Story is Displayed:
Once you have provided the full stock story, you can take follow-up stock-related questions. For any stock analysis questions, provide professional insights based on your financial expertise.

🚫 IMPORTANT:
If the user says anything **other than stock related questions**, respond with:
**“I can only help if you tell me the company and date range you’d like to analyze.”**

✅ MANDATORY:
**Always explain the next step *before* doing it.** This helps the user clearly understand what’s happening and follow along easily.

💬 Tone:
Keep it analytical but conversational. Guide the user through stock behavior by connecting price movements to financial news in a storytelling format.
'''

)

@agent.tool
async def web_search(ctx: RunContext, query: str):
    tavily_client = AsyncTavilyClient(api_key=os.environ['TAVILY_API_KEY'])
    response = await tavily_client.search(query=query, max_results=15, search_depth="advanced", include_domains=["https://www.wsj.com", "https://finance.yahoo.com/", "https://www.reuters.com/", "https://www.ft.com/",""])
    print(response['results'])
    return response['results']

@agent.tool
async def get_tickr_symbol(ctx:RunContext, companyName:str):
    '''
    A tool to give tickr id for the given company
    Args:
        ctx: the current context
        companyName: the company name for which Tickr has to be given
    
    '''
    tickrAgent= Agent(
        model=model,
        system_prompt='''
        you whould be given a company name, please provide the tickr of the company , only provide the tickr data
        and no other sentence.

        example 
        what is the tickr for Amazon?
        AMZN
        '''


    )
    prompt = f'the company is {companyName}'
    response=tickrAgent.run_sync(prompt)
    input_tokens = count_tokens(prompt)
    output_tokens = count_tokens(response.output)
    add_tool_tokens(input_tokens, output_tokens)
    print(f'tokens used for get_tickr_symbol: {input_tokens + output_tokens}')

    return response

class tickrInput(BaseModel):
    ticker:str
    start:datetime.date
    end:datetime.date

class WeeklyStockDataResult(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    weekly_data: list[dict]
    success: bool
    message: str


@agent.tool
def get_weekly_stock_data(ctx: RunContext, ticker: str, start_date: str, end_date: str) -> WeeklyStockDataResult:
    """
    Fetches and resamples stock data for the given ticker to weekly candlesticks (week ends on Friday).
    
    Args:
        ticker (str): The stock ticker symbol.
        start_date (str): The start date in 'YYYY-MM-DD' format.
        end_date (str): The end date in 'YYYY-MM-DD' format.
    
    Returns:
        WeeklyStockDataResult: Model containing weekly data and status message.
    """
    try:
        # Validate date order
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        if start_dt > end_dt:
            return WeeklyStockDataResult(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                weekly_data=[],
                success=False,
                message=f"❌ Invalid date range: start_date ({start_date}) is after end_date ({end_date})"
            )
        
        # Download daily stock data with retry
        import time
        max_retries = 3
        df = None
        for attempt in range(max_retries):
            try:
                df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, progress=False)
                break
            except Exception as e:
                if "Rate limit" in str(e) or "YFRateLimitError" in str(type(e).__name__):
                    if attempt < max_retries - 1:
                        wait_time = 5 * (2 ** attempt)
                        print(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 2}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                raise

        if df.empty:
            return WeeklyStockDataResult(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                weekly_data=[],
                success=False,
                message="No data returned. Check ticker or date range."
            )

        # Ensure datetime index
        df.index = pd.to_datetime(df.index)

        # Resample to weekly candlesticks (week ends on Friday)
        weekly = pd.DataFrame()
        weekly['Open'] = df['Open'].resample('W-FRI').first()
        weekly['High'] = df['High'].resample('W-FRI').max()
        weekly['Low'] = df['Low'].resample('W-FRI').min()
        weekly['Close'] = df['Close'].resample('W-FRI').last()
        weekly['Volume'] = df['Volume'].resample('W-FRI').sum()

        # Reset index for clean output
        weekly = weekly.reset_index()

        # Convert to list of dicts for JSON serialization
        weekly_data_list = weekly.to_dict(orient='records')
        # input_tokens = count_tokens(f"{ticker} {start_date} {end_date}")
        # output_tokens = count_tokens(weekly_data_list)
        # add_tool_tokens(input_tokens, output_tokens)
        # print(f'tokens used for get_weekly_stock_data: {input_tokens + output_tokens}')

        return WeeklyStockDataResult(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            weekly_data=weekly_data_list,
            success=True,
            message="✅ Weekly data fetched and resampled successfully."
        )

    except Exception as e:
        return WeeklyStockDataResult(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            weekly_data=[],
            success=False,
            message=f"❌ Error occurred: {str(e)}"
        )

# ========== 2️⃣ WeeklyChangeResult Tool ==========

class WeeklyChangeResult(BaseModel):
    weeks: list[dict]

@agent.tool
def find_weeks_with_significant_change(ctx: RunContext, weekly_data: list[dict]) -> WeeklyChangeResult:
    """
    Given weekly stock data (list of dicts), find weeks with a significant price change (>2% increase or decrease).
    """
    df = pd.DataFrame(weekly_data)

    if df.empty or 'Close' not in df.columns:
        return WeeklyChangeResult(weeks=[])

    # Calculate % change
    df['Pct_Change'] = df['Close'].pct_change() * 100

    # Identify weeks with >2% increase or decrease
    significant_weeks = df[abs(df['Pct_Change']) > 2].copy()

    # Convert to list of dicts
    weeks_list = significant_weeks[['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Pct_Change']].to_dict(orient='records')
    input_tokens = count_tokens(str(weekly_data))
    output_tokens = count_tokens(str(weeks_list))
    add_tool_tokens(input_tokens, output_tokens)
    print(f'tokens used for find_weeks_with_significant_change: {input_tokens } ---- Output: {output_tokens}   ')
    print(f'Found significant weeks: {weeks_list}')

    return WeeklyChangeResult(weeks=weeks_list)


@agent.tool
def build_date_ranges_from_weeks(ctx: RunContext, weeks: List[dict]) -> List[Dict[str, str]]:
    """
    Builds a list of date ranges (start_date to end_date) from weekly data.

    Args:
        weeks (List[dict]): List of weeks with a 'Date' field (e.g., {"Date": "2025-02-17"})

    Returns:
        List[Dict[str, str]]: Each dict has "start_date" and "end_date" as MM/DD/YYYY
    """
    date_ranges = []
    print(f"Building date ranges from weeks: {weeks}")
    for week in weeks:
        date = pd.to_datetime(week['Date'])
        start_date = (date - pd.Timedelta(days=date.weekday())).strftime('%m/%d/%Y')  # Monday
        end_date = (date + pd.Timedelta(days=(4 - date.weekday()))).strftime('%m/%d/%Y')  # Friday
        date_ranges.append({
            "start_date": start_date,
            "end_date": end_date
        })
    print(f"Built date ranges: {date_ranges}")
    input_tokens = count_tokens(str(weeks))
    output_tokens = count_tokens(str(date_ranges))
    add_tool_tokens(input_tokens, output_tokens)
    print(f'tokens used for build_date_ranges_from_weeks: {input_tokens + output_tokens}')

    return date_ranges


# ========== 2️⃣  Article Tool ==========
# === Utility ===
def build_query(main_query, site):
    return f'intitle:"{main_query}" site:{site}'

# === Tool Response Schema ===
class ArticleResult(BaseModel):
    title: str
    url: str

class ArticlesByDateRange(BaseModel):
    date_range: str
    site: str
    articles: List[ArticleResult]

class ArticlesForPeakWeeksResult(BaseModel):
    company: str
    articles: List[ArticlesByDateRange]

@agent.tool
def find_articles_for_peak_weeks(ctx: RunContext, company: str, date_ranges: Dict[str, str]) -> ArticlesForPeakWeeksResult:
    
    """
    For the given company and peak weeks (date ranges), find articles from WSJ, Reuters, FT, EconomicTimes, and TimesOfIndia
    using both SerpAPI and OpenAI web search. Filters out any article not belonging to those domains.
    """
    api_key = os.getenv("SERP_API_KEY")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    allowed_domains = {
        "wsj.com": "wsj.com",
        "reuters.com": "reuters.com",
        "ft.com": "ft.com",
        "economictimes.indiatimes.com": "economictimes.indiatimes.com",
        "timesofindia.indiatimes.com": "timesofindia.indiatimes.com"
    }

    sites = list(allowed_domains.keys())
    articles_result = []

    def build_query(main_query, site):
        return f'intitle:"{main_query}" site:{site}'

    def is_valid_source(url: str, site: str) -> bool:
        return site in url

    for site in sites:
        for start_date, end_date in date_ranges.items():
            date_range_label = f"{start_date} to {end_date}"
            
            combined_articles = []

            # --- SerpAPI Search ---
            serp_query = build_query(company, site)
            serp_params = {
                "engine": "google",
                "q": serp_query,
                "api_key": api_key,
                "num": 2,
                "hl": "en",
                "gl": "us",
                "tbs": f"cdr:1,cd_min:{start_date},cd_max:{end_date}"
            }
            print(f"Querying SerpAPI: {serp_query} from {start_date} to {end_date}")

            serp_response = requests.get("https://serpapi.com/search", params=serp_params)
            if serp_response.status_code == 200:
                serp_data = serp_response.json().get("organic_results", [])
                print(f"success {len(serp_data)} results found")
                for result in serp_data[:2]:
                    title = result.get("title")
                    url = result.get("link")
                    print(f"SerpAPI result: {title} - {url}")
                    if title and url and is_valid_source(url, site):
                        combined_articles.append(ArticleResult(title=title, url=url))

            # # --- OpenAI Web Search ---
            # try:
            #     web_client = OpenAI(api_key=openai_key)
            #     openai_query = f"{company} site:{site} in the week ending {end_date}"
            #     openai_response = web_client.responses.create(
            #         model="gpt-4.1",
            #         tools=[{
            #             "type": "web_search_preview",
            #             "search_context_size": "high"
            #         }],
            #         input=openai_query
            #     )

            #     for item in openai_response.output:
            #         if hasattr(item, 'role') and item.role == "assistant":
            #             for block in item.content:
            #                 if block.type == "output_text":
            #                     if hasattr(block, "annotations"):
            #                         for annotation in block.annotations:
            #                             if annotation.type == "url_citation" and is_valid_source(annotation.url, site):
            #                                 combined_articles.append(
            #                                     ArticleResult(title=annotation.title, url=annotation.url)
            #                                 )
            # except Exception as e:
            #     print(f"OpenAI Web search failed: {e}")

            # --- Remove duplicates by URL ---
            seen_urls = set()
            unique_articles = []
            for article in combined_articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    unique_articles.append(article)

            articles_result.append(
                ArticlesByDateRange(
                    date_range=date_range_label,
                    site=site,
                    articles=unique_articles
                )
            )

            time.sleep(5)
    input_tokens = count_tokens(f"{company} {date_ranges}")
    output_tokens = count_tokens(str(articles_result))
    add_tool_tokens(input_tokens, output_tokens)
    print(f'tokens used for find_articles_for_peak_weeks: {input_tokens + output_tokens}')  
    return ArticlesForPeakWeeksResult(
        company=company,
        articles=articles_result
    )

# ========== 2️⃣ Economic Times Article Scraper Tool ==========
class ETScrapeResult(BaseModel):
    url: str
    title: str
    content: str
    success: bool
    message: str

@agent.tool
async def scrape_et_article(ctx: RunContext, url: str, title: str) -> ETScrapeResult:
    """
    Scrapes the full article content from a Economic Times URL using Selenium and saved cookies.
     Args:
        ctx: the current context
        url: the URL of the article to scrape
        title: the title of the article to scrape
    Returns:
        ETScrapeResult: A model containing the scraped content or an error message
       
    """
    # Dynamic path for cookie file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_file_path = os.path.join(BASE_DIR, "stock_story_integration", "economictimes.indiatimes.com_json_1770573419566.json")
    with open(cookie_file_path, "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    cookies = []
    for cookie in raw_cookies:
        filtered_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain", ".wsj.com"),
            "path": cookie.get("path", "/"),
            "secure": cookie.get("secure", False),
            "httpOnly": cookie.get("httpOnly", False),
        }
        if "expirationDate" in cookie:
            filtered_cookie["expiry"] = int(cookie["expirationDate"])
        cookies.append(filtered_cookie)

    USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
   

    driver = uc.Chrome(driver_executable_path=r"C:\chromedriver-win64\chromedriver.exe", options=options)

    def accept_cookies(driver, timeout=5):
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'agree')]"))
            ).click()
        except Exception:
            pass

    def inject_cookies(driver, cookies, base_url="https://economictimes.indiatimes.com/"):
        driver.get(base_url)
        time.sleep(2)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f" Failed to add cookie {cookie['name']}: {e}")

    try:
        inject_cookies(driver, cookies)
        driver.get(url)
        time.sleep(random.uniform(2.5, 4))
        accept_cookies(driver)

        soup = BeautifulSoup(driver.page_source, "lxml")

        # Economic Times uses different selectors
        paragraphs = []
        
        # Try multiple selectors for ET articles
        article_body = soup.find('div', class_='artText') or soup.find('div', {'class': 'Normal'})
        if article_body:
            for p in article_body.find_all('p'):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)
        
        # Fallback: get all paragraphs if specific container not found
        if not paragraphs:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text and len(text) > 50:  # Filter out short snippets
                    paragraphs.append(text)

        full_text = "\n".join(paragraphs)

        driver.quit()
        print(f"Success: {full_text[:100]}...")  # Print first 100 chars for debugging
        input_tokens = count_tokens(url)
        output_tokens = count_tokens(full_text)
        add_tool_tokens(input_tokens, output_tokens)

        if full_text.strip():
            return ETScrapeResult(
                url=url,
                title=title,
                content=full_text,
                success=True,
                message="Article successfully scraped!"
            )
        else:
            return ETScrapeResult(
                url=url,
                title=title,
                content="",
                success=False,
                message="No visible text found in the article."
            )

    except Exception as e:
        driver.quit()
        return ETScrapeResult(
            url=url,
            title=title,
            content="",
            success=False,
            message=f"Error occurred: {str(e)}"
        )



# ========== 3️⃣ WSJ Article Scraper Tool ==========
class WSJScrapeResult(BaseModel):
    url: str
    title: str
    content: str
    success: bool
    message: str

@agent.tool
async def scrape_wsj_article(ctx: RunContext, url: str, title: str) -> WSJScrapeResult:
    """
    Scrapes the full article content from a WSJ URL using Selenium and saved cookies.
     Args:
        ctx: the current context
        url: the URL of the article to scrape
        title: the title of the article to scrape
    Returns:
        WSJScrapeResult: A model containing the scraped content or an error message
       
    """
    # Dynamic path for cookie file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_file_path = os.path.join(BASE_DIR, "stock_story_integration", "www.wsj.com_json_1748426594430.json")
    with open(cookie_file_path, "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    cookies = []
    for cookie in raw_cookies:
        filtered_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain", ".wsj.com"),
            "path": cookie.get("path", "/"),
            "secure": cookie.get("secure", False),
            "httpOnly": cookie.get("httpOnly", False),
        }
        if "expirationDate" in cookie:
            filtered_cookie["expiry"] = int(cookie["expirationDate"])
        cookies.append(filtered_cookie)

    USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
   

    driver = uc.Chrome(version_main=145, options=options)

    def accept_cookies(driver, timeout=5):
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'agree')]"))
            ).click()
        except Exception:
            pass

    def inject_cookies(driver, cookies, base_url="https://www.wsj.com"):
        driver.get(base_url)
        time.sleep(2)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f" Failed to add cookie {cookie['name']}: {e}")

    try:
        inject_cookies(driver, cookies)
        driver.get(url)
        time.sleep(random.uniform(2.5, 4))
        accept_cookies(driver)

        soup = BeautifulSoup(driver.page_source, "lxml")

        target_classes = {
            "css-1akm6h5-Paragraph e1e4oisd0",
            "e141zjhk0 css-18f125c-FormattedText"
        }

        paragraphs = []
        for p in soup.find_all("p"):
            class_attr = p.get("class")
            if class_attr:
                class_str = " ".join(class_attr)
                if class_str in target_classes:
                    text = p.get_text(strip=True)
                    if text:
                        paragraphs.append(text)

        full_text = "\n".join(paragraphs)

        driver.quit()
        print(f"Success: {full_text[:100]}...")  # Print first 100 chars for debugging
        input_tokens = count_tokens(url)
        output_tokens = count_tokens(full_text)
        add_tool_tokens(input_tokens, output_tokens)

        if full_text.strip():
            return WSJScrapeResult(
                url=url,
                title=title,
                content=full_text,
                success=True,
                message="Article successfully scraped!"
            )
        else:
            return WSJScrapeResult(
                url=url,
                title=title,
                content="",
                success=False,
                message="No visible text found in the article."
            )

    except Exception as e:
        driver.quit()
        return WSJScrapeResult(
            url=url,
            title=title,
            content="",
            success=False,
            message=f"Error occurred: {str(e)}"
        )




# ========== 2️⃣ FT Article Scraper Tool ==========
class FTScrapeResult(BaseModel):
    url: str
    title: str
    content: str
    success: bool
    message: str
@agent.tool
async def scrape_ft_article(ctx: RunContext, url: str, title: str) -> FTScrapeResult:
    """
    Scrapes the full article content from an FT URL using Selenium and saved cookies.
    Args:
        ctx: the current context
        url: the URL of the article to scrape
        title: the title of the article to scrape
    Returns:
        FTScrapeResult: A model containing the scraped content or an error message.
    """
    # Dynamic path for cookie file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_file_path = os.path.join(BASE_DIR, "stock_story_integration", "www.ft.com_json_1748426136782.json")
    with open(cookie_file_path, "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    cookies = []
    for cookie in raw_cookies:
        filtered_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain", ".ft.com"),
            "path": cookie.get("path", "/"),
            "secure": cookie.get("secure", False),
            "httpOnly": cookie.get("httpOnly", False),
        }
        if "expirationDate" in cookie:
            filtered_cookie["expiry"] = int(cookie["expirationDate"])
        cookies.append(filtered_cookie)

    USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
   

    driver = uc.Chrome(version_main=145, options=options)

    def accept_cookies(driver, timeout=5):
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'agree')]"))
            ).click()
        except Exception:
            pass

    def inject_cookies(driver, cookies, base_url="https://www.ft.com"):
        driver.get(base_url)
        time.sleep(2)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"Failed to add cookie {cookie['name']}: {e}")

    try:
        inject_cookies(driver, cookies)
        driver.get(url)
        time.sleep(random.uniform(2.5, 4))
        accept_cookies(driver)

        soup = BeautifulSoup(driver.page_source, "lxml")

        # Try to locate text within <body class="content"> or <article>
        text_blocks = []

        body_content = soup.find('body', class_='content') or soup.find('body.content')
        if body_content:
            text_blocks.append(body_content.get_text(separator=' ', strip=True))

        article_tag = soup.find('article')
        if article_tag:
            text_blocks.append(article_tag.get_text(separator=' ', strip=True))

        full_text = "\n\n".join(text_blocks)
        print("Success: {full_text[:100]}...")  # Print first 100 chars for debugging
        driver.quit()
        input_tokens = count_tokens(url)
        output_tokens = count_tokens(full_text) 
        add_tool_tokens(input_tokens, output_tokens)
        print(f'tokens used for scrape_ft_article: {input_tokens + output_tokens}')
        if full_text.strip():
            return FTScrapeResult(
                url=url,
                title=title,
                content=full_text,
                success=True,
                message="Article successfully scraped!"
            )
        
        else:
            return FTScrapeResult(
                url=url,
                title=title,
                content="",
                success=False,
                message="No visible text found in the article."
            )

    except Exception as e:
        driver.quit()
        return FTScrapeResult(
            url=url,
            title=title,
            content="",
            success=False,
            message=f"Error occurred: {str(e)}"
        )
# ========== 4️⃣ Reuters Article Scraper Tool ==========
class ArticleInput(BaseModel):
    url: str
    title: str


class ArticleScrapeResult(BaseModel):
    title: str
    url: str
    content: str


class ReutersScrapeResult(BaseModel):
    articles: List[ArticleScrapeResult]
    message: str
    success: bool


@agent.tool
async def scrape_reuters_articles(ctx: RunContext, articles_input: List[ArticleInput]) -> ReutersScrapeResult:
    """
    Scrapes the full article content for a list of Reuters articles using Selenium and saved cookies.
    Args:
        ctx: the current context
        articles_input: A list of articles with `url` and `title` to scrape.
    Returns:
        ReutersScrapeResult: A model containing the enriched articles with full content.
    """
    # ---------- CONFIG ----------
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_file_path = os.path.join(BASE_DIR, "stock_story_integration", "www.reuters.com_json_1748426665433.json")
    USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"

    # ---------- LOAD COOKIES ----------
    def load_cookies(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            raw_cookies = json.load(f)
        valid_cookies = []
        for cookie in raw_cookies:
            filtered = {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ".reuters.com"),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
            }
            if "expirationDate" in cookie:
                filtered["expiry"] = int(cookie["expirationDate"])
            valid_cookies.append(filtered)
        return valid_cookies

    # ---------- SELENIUM ----------
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
   
    driver = uc.Chrome(version_main=145, options=options)

    def accept_cookies(driver, timeout=5):
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'agree')]"))
            ).click()
        except Exception:
            pass

    def inject_cookies(driver, cookies, base_url="https://www.reuters.com"):
        driver.get(base_url)
        time.sleep(2)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"Failed to add cookie {cookie['name']}: {e}")

    def get_full_article(driver, url):
        try:
            driver.get(url)
            time.sleep(random.uniform(2, 3.5))
            accept_cookies(driver)

            soup = BeautifulSoup(driver.page_source, "lxml")
            article = soup.find("article")
            if not article:
                return ""

            # Extract bullet points from summary <ul>
            summary_points = []
            summary_ul = article.find("ul", {"data-testid": "Summary"})
            if summary_ul:
                bullet_items = summary_ul.find_all("li", {"data-testid": "Body"})
                summary_points = [li.get_text(strip=True) for li in bullet_items]

            # Extract paragraphs
            paragraphs = []
            for para_div in article.find_all("div", {"data-testid": lambda v: v and v.startswith("paragraph-")}):
                for span in para_div.find_all("span"):
                    style = span.get("style", "")
                    if "clip" in style and "absolute" in style:
                        span.decompose()
                para_text = para_div.get_text(strip=True)
                if para_text:
                    paragraphs.append(para_text)

            full_text = " ".join(summary_points + paragraphs)
            input_tokens = count_tokens(url)
            output_tokens = count_tokens(full_text)
            add_tool_tokens(input_tokens, output_tokens)  
            return full_text
               

        except Exception as e:
            print(f"Failed to extract article content: {e}")
            return ""

    # ---------- RUN ----------
    enriched_articles = []
    try:
        cookies = load_cookies(cookie_file_path)
        inject_cookies(driver, cookies)

        for i, article in enumerate(articles_input, 1):
            print(f"Fetching [{i}/{len(articles_input)}]: {article.title} - {article.url}")
            full_content = get_full_article(driver, article.url)
            if not full_content.strip():
                print("No content found.")
                continue

            enriched_articles.append(ArticleScrapeResult(
                title=article.title,
                url=article.url,
                content=full_content
            ))

        driver.quit()

        return ReutersScrapeResult(
            articles=enriched_articles,
            message=f"Scraped {len(enriched_articles)} articles successfully.",
            success=True
        )

    except Exception as e:
        try:
            driver.quit()
        except Exception:
            pass
        return ReutersScrapeResult(
            articles=[],
            message=f"Error occurred: {str(e)}",
            success=False
        )

# ========== 5️⃣ Times Of India Article Scraper Tool ==========
class TOIScrapeResult(BaseModel):
    url: str
    title: str
    content: str
    success: bool
    message: str

@agent.tool
async def scrape_toi_article(ctx: RunContext, url: str, title: str) -> TOIScrapeResult:
    """
    Scrapes the full article content from a Times Of India URL using Selenium and saved cookies.
     Args:
        ctx: the current context
        url: the URL of the article to scrape
        title: the title of the article to scrape
    Returns:
        TOIScrapeResult: A model containing the scraped content or an error message
       
    """
    # Dynamic path for cookie file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_file_path = os.path.join(BASE_DIR, "stock_story_integration", "timesofindia.indiatimes.com_json_1770574475288.json")
    with open(cookie_file_path, "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    cookies = []
    for cookie in raw_cookies:
        filtered_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie.get("domain", ".wsj.com"),
            "path": cookie.get("path", "/"),
            "secure": cookie.get("secure", False),
            "httpOnly": cookie.get("httpOnly", False),
        }
        if "expirationDate" in cookie:
            filtered_cookie["expiry"] = int(cookie["expirationDate"])
        cookies.append(filtered_cookie)

    USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
   

    driver = uc.Chrome(version_main=145, options=options)

    def accept_cookies(driver, timeout=5):
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept') or contains(., 'agree')]"))
            ).click()
        except Exception:
            pass

    def inject_cookies(driver, cookies, base_url="https://timesofindia.indiatimes.com/"):
        driver.get(base_url)
        time.sleep(2)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f" Failed to add cookie {cookie['name']}: {e}")

    try:
        inject_cookies(driver, cookies)
        driver.get(url)
        time.sleep(random.uniform(2.5, 4))
        accept_cookies(driver)

        soup = BeautifulSoup(driver.page_source, "lxml")

        # Times of India uses different selectors
        paragraphs = []
        
        # Try multiple selectors for TOI articles
        article_body = soup.find('div', class_='_s30J clearfix') or soup.find('div', {'class': 'Normal'}) or soup.find('article')
        if article_body:
            for p in article_body.find_all('p'):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)
        
        # Fallback: get all paragraphs if specific container not found
        if not paragraphs:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text and len(text) > 50:  # Filter out short snippets
                    paragraphs.append(text)

        full_text = "\n".join(paragraphs)

        driver.quit()
        print(f"Success: {full_text[:100]}...")  # Print first 100 chars for debugging
        input_tokens = count_tokens(url)
        output_tokens = count_tokens(full_text)
        add_tool_tokens(input_tokens, output_tokens)

        if full_text.strip():
            return TOIScrapeResult(
                url=url,
                title=title,
                content=full_text,
                success=True,
                message="Article successfully scraped!"
            )
        else:
            return TOIScrapeResult(
                url=url,
                title=title,
                content="",
                success=False,
                message="No visible text found in the article."
            )

    except Exception as e:
        driver.quit()
        return TOIScrapeResult(
            url=url,
            title=title,
            content="",
            success=False,
            message=f"Error occurred: {str(e)}"
        )






@agent.tool
async def rerank_articles(ctx: RunContext, articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Reranks articles based on relevance to stock price movements and returns them sorted from most to least relevant.

    Args:
        ctx: the current context
        articles: List of articles with 'title', 'content', and 'url'.

    Returns:
        List[Dict[str, str]]: Top 4 unique articles sorted by relevance score (descending).
    """
    print(f"🔍 Rerank called with {len(articles)} articles")
    if not articles:
        print("No articles to rerank.")
        return []

    rerank_agent = Agent(
        model=model,
        system_prompt="""
You are a financial analyst tasked with ranking news articles based on their relevance to recent stock price movements of a specific company.

Evaluate each article only by how directly it contributes to understanding short-term or recent stock performance.

✅ Consider relevant if the article includes:
- Earnings announcements or financial results
- Strategic business decisions (e.g., partnerships, mergers, acquisitions, cost-cutting, leadership changes)
- Regulatory approvals, fines, or legal actions with market implications
- Market expansion, new operational territories, or restructuring
- Broad macroeconomic or industry-level shifts that are directly tied to the company

❌ Do NOT consider relevant:
- Product announcements or launches without clear stock market impact
- General news, lifestyle content, or branding/marketing updates
- Speculative future plans with no current investor or market reaction
- Media reviews, entertainment events, or non-financial partnerships
- Any content focused on features, culture, or sentiment not tied to valuation

Rate each article from **1 to 10**:
- **10** = Highly relevant and directly explains stock movement
- **0** = Completely irrelevant to company, stock or investor movement

Base your score only on the article's ability to explain **recent or near-term valuation changes or investor sentiment**. 
Do not speculate or infer potential long-term value unless explicitly tied to market behavior.

⛔️ Do not return any explanation or commentary outside of JSON.

✅ Respond with a valid JSON list in this exact format:
[
  {"title": "<title of article 1>", "score": <rating from 1 to 10>},
  {"title": "<title of article 2>", "score": <rating from 1 to 10>}
]
"""
    )

    # Prepare prompt for reranking
    article_descriptions = ""
    for idx, article in enumerate(articles):
        article_descriptions += f"{idx+1}. Title: {article['title']}\nContent: {article['content'][:500]}...\n\n"

    prompt = f"Rate the following articles:\n\n{article_descriptions}"
    input_tokens = count_tokens(prompt)
    response = await rerank_agent.run(prompt)

    try:
        scored_articles_json_str = response.output
        output_tokens = count_tokens(scored_articles_json_str)
        add_tool_tokens(input_tokens, output_tokens)

        # Remove markdown code block if present
        if scored_articles_json_str.startswith("```"):
            scored_articles_json_str = scored_articles_json_str.strip().split("\n", 1)[-1]
        if scored_articles_json_str.endswith("```"):
            scored_articles_json_str = scored_articles_json_str.rsplit("```", 1)[0].strip()

        scored_articles = json.loads(scored_articles_json_str)

        # Build a map from (possibly truncated) agent titles -> scores
        article_score_map = {item['title']: item.get('score', 0)
                             for item in scored_articles
                             if isinstance(item, dict) and 'title' in item}

        # Assign scores to original articles, best-effort match
        for article in articles:
            # Default score is 0; try to match exactly by title
            score = article_score_map.get(article['title'], 0)
            article['score'] = score
            if score == 0:
                print(f"⚠️ No exact score found for article: '{article['title']}'. Assigned score=0.")

        # Sort articles in-place by score descending
        articles.sort(key=lambda x: x['score'], reverse=True)

        # Remove duplicates by content (preserving order of first occurrence)
        seen_contents = set()
        unique_articles = []
        for article in articles:
            content_key = article['content'].strip()
            if content_key not in seen_contents:
                unique_articles.append(article)
                seen_contents.add(content_key)

        print(f"✅ Unique articles after deduplication: {len(unique_articles)} found.")

        # Debug: print unique top articles
        print("🔝 Unique articles after reranking & deduplication:")
        for idx, article in enumerate(unique_articles, start=1):
            print(f"\nArticle {idx}:")
            print(f"Title: {article['title']}")
            print(f"Content (first 300 chars): {article['content'][:300]}...")
            print(f"Score: {article['score']}")
        
        print(f'tokens used for rerank_articles: {input_tokens + output_tokens}')
        # Remove 'score' key before returning
        for article in unique_articles:
            article.pop('score', None)

        # Return top 4 unique articles
        return unique_articles[:4]

    except Exception as e:
        print(f"Error decoding JSON from rerank_agent: {e}. Response was: '{scored_articles_json_str}'")
        return articles[:4]

class SummaryGeneratorResult(BaseModel):
    date_range: str
    summary: str
    urls: List[str]
    success: bool
    message: str

@agent.tool
async def generate_summary(ctx: RunContext, date_range: str, articles: List[Dict[str, str]]) -> SummaryGeneratorResult:
    try:
        if not articles:
            return SummaryGeneratorResult(
                date_range=date_range,
                summary="",
                urls=[],
                success=False,
                message="No articles to summarize for this week."
            )

        print(f"Generating summary for {date_range}...")
        print(f"Total articles to summarize: {len(articles)}")

        combined_content = ""
        urls = []
        for article in articles:
            combined_content += f"Title: {article['title']}\nContent: {article['content']}\n\n"
            urls.append(article['url'])

        weeklysummaryAgent = Agent(
            model=model,
            system_prompt="""
          You are a financial analyst. Carefully read the following contents of differnt articles  and extract a clear and concise summary of the key financial and business developments mentioned. Write a concise, factual, investor-focused summary under 100 words here. Highlight the most material financial and stock-impacting takeaways from the article.
            Information to look at :-
            Key financial metrics discussed, Events or news that directly & indirectly impact the company’s stock or investor sentiment, guidance updates, executive changes, regulatory issues, major deals, market trends, or macroeconomic influences. Only include factual, stock-relevant information. Avoid generic background info or non-material details.
            do not include numbers that convey change in stock price or forecasted changes in stock price.
            """
        )

        response = weeklysummaryAgent.run_sync(
            f"Generate a concise summary for the week {date_range} based on the following articles:\n\n{combined_content}",
        )

        # ✅ Prepend URLs manually to the final summary
        url_block = "🔗 **Referenced URLs:**\n" + "\n".join(f"• {url}" for url in urls) + "\n\n"
        final_summary = url_block + "\n" + response.output.strip()

        print(f"✅ Summary done for {date_range}")
        input_tokens = count_tokens(f"{date_range} {combined_content}")
        output_tokens = count_tokens(final_summary)
        add_tool_tokens(input_tokens, output_tokens)
        print(f'tokens used for generate_summary: {input_tokens + output_tokens}')
        return SummaryGeneratorResult(
            date_range=date_range,
            summary=final_summary,
            urls=urls,
            success=True,
            message="Weekly summary generated successfully."
        )

    except Exception as e:
        print(f"Errror-------------------------- {e}")
        return SummaryGeneratorResult(
            date_range=date_range,
            summary="",
            urls=[],
            success=False,
            message=f"Error generating weekly summary: {str(e)}"
        )

class WeeklySummaryResult(BaseModel):
    date_range: str
    summary: str
    success: bool
    message: str


summaries = []



@agent.tool
async def gather_articles_for_summarization(
    ctx: RunContext,
    company: str,
    start_date: str,
    end_date: str
) -> WeeklySummaryResult:
    def deep_convert(d):
        if isinstance(d, defaultdict):
            return {k: deep_convert(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [deep_convert(i) for i in d]
        return d

    try:
        date_range_label = f"{start_date} to {end_date}"
        print(f"\n🗓️ Starting summarization for: {date_range_label}")

        article_results = find_articles_for_peak_weeks(
            ctx, company=company, date_ranges={start_date: end_date}
        )
        grouped_content = defaultdict(lambda: defaultdict(list))

        for entry in article_results.articles:
            site = entry.site
            articles = entry.articles
            if not articles:
                continue

            if site == "reuters.com":
                article_inputs = [ArticleInput(title=a.title, url=a.url) for a in articles]
                reuters_result = await scrape_reuters_articles(ctx, article_inputs)
                if reuters_result.success:
                    for article in reuters_result.articles:
                        grouped_content[date_range_label][site].append({
                            "title": article.title,
                            "url": article.url,
                            "content": article.content
                        })

            elif site == "wsj.com":
                for article in articles:
                    wsj_result = await scrape_wsj_article(ctx, url=article.url, title=article.title)
                    if wsj_result.success:
                        grouped_content[date_range_label][site].append({
                            "title": wsj_result.title,
                            "url": wsj_result.url,
                            "content": wsj_result.content
                        })

            elif site == "ft.com":
                for article in articles:
                    ft_result = await scrape_ft_article(ctx, url=article.url, title=article.title)
                    if ft_result.success:
                        grouped_content[date_range_label][site].append({
                            "title": ft_result.title,
                            "url": ft_result.url,
                            "content": ft_result.content
                        })
            elif site == "economictimes.indiatimes.com":
                for article in articles:
                    et_result = await scrape_et_article(ctx, url=article.url, title=article.title)
                    if et_result.success:
                        grouped_content[date_range_label][site].append({
                            "title": et_result.title,
                            "url": et_result.url,
                            "content": et_result.content
                        })
            elif site == "timesofindia.indiatimes.com":
                for article in articles:
                    toi_result = await scrape_toi_article(ctx, url=article.url, title=article.title)
                    if toi_result.success:
                        grouped_content[date_range_label][site].append({
                            "title": toi_result.title,
                            "url": toi_result.url,
                            "content": toi_result.content
                        })
            

        grouped_content = deep_convert(grouped_content)

        all_articles = []
        for site_articles in grouped_content.get(date_range_label, {}).values():
            all_articles.extend(site_articles)

        print(f"📝 Total articles for reranking ({date_range_label}): {len(all_articles)}")
        top_articles = await  rerank_articles(ctx=ctx, articles=all_articles)
        print(f"✅ Top {len(top_articles)} articles selected after reranking")

        summary_result = await generate_summary(ctx=ctx, date_range=date_range_label, articles=top_articles)

        if summary_result.success:
            print(f"🧾 Summary successfully generated for {date_range_label}:\n{summary_result.summary[:300]}...\n")
            summaries.append(summary_result)
            print(f"📢 Broadcasting summary: {summary_result.date_range}")
            await broadcast_summary(summary_result)
          

           
        else:
            print(f"⚠️ Summary generation failed for {date_range_label}: {summary_result.message}")

      
        input_tokens = count_tokens(f"{date_range_label} {all_articles}")
        output_tokens = count_tokens(summary_result.summary)
        add_tool_tokens(input_tokens, output_tokens)
        print(f'tokens used for gather_articles_for_summarization: {input_tokens + output_tokens}')
        return WeeklySummaryResult(
            date_range=date_range_label,
            summary=summary_result.summary,
            success=summary_result.success,
            message=summary_result.message
        )

    except Exception as e:
        print(f"❌ Error processing {start_date} to {end_date}: {str(e)}")
        return WeeklySummaryResult(
            date_range=f"{start_date} to {end_date}",
            summary="",
            success=False,
            message=f"Error: {str(e)}"
        )

@agent.tool
async def summarize_date_ranges_sequentially(
    ctx: RunContext,
    company: str,
    date_ranges: List[Dict[str, str]]
) -> str:
    """
    Sequentially calls gather_articles_for_summarization for each date range to ensure ordered processing.

    Args:
        ctx: Agent context
        company: Company name
        date_ranges: List of dicts with "start_date" and "end_date" in MM/DD/YYYY format

    Returns:
        str: Status message after processing all date ranges
    """
    for dr in date_ranges:
        start_date = dr["start_date"]
        end_date = dr["end_date"]
        print(f"📅 Processing: {start_date} to {end_date}")
        await gather_articles_for_summarization(ctx, company, start_date, end_date)
    
    return f"✅ Completed summarization for {len(date_ranges)} date range(s)."


def strip_urls(summary: str) -> str:
    return re.sub(r"🔗 \*\*Referenced URLs:\*\*\n(?:• .+\n?)+", "", summary, flags=re.MULTILINE).strip()


@agent.tool
async def generate_stock_story(ctx: RunContext, summary: List[WeeklySummaryResult]) -> str:
    # Convert the list of SummaryGeneratorResult to a plain text input
    
    for item in summaries:
        clean_summary = strip_urls(item.summary)
        print(f"Summary: {clean_summary}")

    summary_text = "\n\n".join(
        f"Week: {item.date_range}\nSummary: {strip_urls(item.summary)}"
        for item in summaries
    )

    # Now pass the plain text to the LLM with an updated system prompt
    stockstoryagent = Agent(
        model=model,
        system_prompt= f'''

You are a financial content writer trained in the writing styles of Reuters, Capital Group, and WSJ.
Your task is to write a single-paragraph stock story that summarizes a company’s quarterly performance, using highlights from weeks where the stock showed notable movement.
These highlights are provided as short summaries of news events and reactions.
Follow the structure and style guidelines below:

Writing Guidelines
Start with a Company Overview
 - Use 1–2 sentences to explain what the company does and set the tone for the quarter.
 - Mention the sector, specialization, or geographic relevance.
 - Example: “CVS Health, a leading U.S. healthcare services and pharmacy chain, began the year on a stronger footing, as its fourth-quarter profit surpassed analyst expectations and lifted investor sentiment. The positive results provided some relief after a challenging 2024 marked by a sharp stock decline and pressures within its Medicare business. The appointment of new CEO David Joyner signaled a shift in strategy, with early signs that cost-cutting efforts and turnaround measures were gaining traction. Despite the encouraging progress, persistently high medical loss ratios continued to weigh on the company's operational performance. Looking ahead, investor attention remains focused on CVS Health's ability to sustain improvements and capitalize on strengthening healthcare demand.”

 Narrate the Quarter Chronologically

 - Connect the highlight weeks in time order (early → mid → late quarter).
 - Use cause-effect phrasing to show how events affected performance or sentiment.
 - Focus on developments such as earnings, product rollouts, leadership changes, macro/policy shifts, analyst moves.

Avoid Numbers and Percentages
 - Do not include figures like revenue, net income, stock change, number of hires, etc.
 - Use qualitative phrases instead: “saw gains,” “boosted sentiment,” “weighed on shares,” “added to momentum”.

Maintain Neutral, Investor-Oriented Tone
 - Avoid hype, jargon, or speculative language.
 - Be concise and highly readable. Aim for clarity over flair.
 - Use short, declarative sentences with fluid transitions.
 - End with a Forward-Looking Note (if applicable)

Optionally close with a comment on investor outlook, strategic positioning, or unresolved risks — only if it naturally emerges from the inputs.

'''
    )
    agent_response = await stockstoryagent.run(summary_text)
    input_tokens = count_tokens(summary_text)
    output_tokens = count_tokens(agent_response.output)
    print(f'Generated Stock Story: {agent_response.output}')
    add_tool_tokens(input_tokens, output_tokens)
    print(f'tokens used for generate_stock_story: {input_tokens + output_tokens}')
    
    # Store the result in deps to bypass agent commentary
    if ctx.deps and isinstance(ctx.deps, dict):
        ctx.deps["story"] = agent_response.output
        
    return agent_response.output


# uvicorn app:app --reload --host 0.0.0.0 --port 8000
#04846733878----------benzira
