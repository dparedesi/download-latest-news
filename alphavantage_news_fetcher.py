import configparser
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import re
import json

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def load_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Join multi-line values and split by comma
    queries = re.split(r',\s*', ''.join(config['Queries']['list'].splitlines()).strip())
    
    parsed_queries = []
    for query in queries:
        match = re.match(r'(\w+)\((.*?)\)', query.strip())
        if match:
            parsed_queries.append((match.group(1), match.group(2)))
        else:
            parsed_queries.append((query.strip(), query.strip()))
    return {
        'queries': parsed_queries,
        'api_key': config['API']['alphavantage_key' if 'alphavantage' in config_file else 'newsapi_key'],
        'news_limit': int(config['Settings']['news_limit'])
    }

def create_output_folder():
    folder_path = 'output'
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_article_content(url, session):
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content_elements = soup.find_all(['p', 'article', 'div'], class_=['content', 'article-body', 'story-body'])
        content = '\n'.join([elem.get_text().strip() for elem in content_elements])
        return content[:2000]
    except Exception as e:
        logging.error(f"Error fetching article content: {str(e)}")
        return ""

def get_latest_news(symbol, session, api_key, news_limit):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "time_from": (datetime.now() - timedelta(days=5)).strftime("%Y%m%dT%H%M"),
        "sort": "LATEST",
        "limit": news_limit,
        "apikey": api_key
    }

    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            if remaining < 5:
                time.sleep(1)  # Sleep for 1 second if close to rate limit
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON for symbol {symbol}: {str(e)}")
            return f"Error decoding JSON for {symbol}"

        if "feed" not in data or not data["feed"]:
            logging.info(f"No news found for {symbol}")
            return f"No news found for {symbol}"

        news_items = []
        for index, item in enumerate(data["feed"][:news_limit], 1):
            logging.info(f"Processing news item {index} for {symbol}")
            news_items.append(f"Title: {item['title']}")
            news_items.append(f"URL: {item['url']}")
            news_items.append(f"Time Published: {item['time_published']}")
            news_items.append(f"Summary: {item['summary']}")
            content = get_article_content(item['url'], session)
            if content:
                news_items.append(f"Content: {content}")
            news_items.append("-" * 50)
            time.sleep(1)

        return "\n".join(news_items)

    except requests.RequestException as e:
        error_message = f"Error fetching news for {symbol}: {str(e)}"
        logging.error(error_message)
        return error_message

def truncate_content(content, max_length=5000):
    if len(content) > max_length:
        return content[:max_length] + "... (truncated)"
    return content

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def main():
    setup_logging()
    config = load_config('config.ini')
    output_folder = create_output_folder()
    session = create_session()
    
    consolidated_news = []

    for symbol, query in config['queries']:
        logging.info(f"Processing symbol: {symbol} (Query: {query})")
        
        latest_news = get_latest_news(symbol, session, config['api_key'], config['news_limit'])
        safe_symbol = sanitize_filename(symbol)
        with open(os.path.join(output_folder, f'{safe_symbol}_news.txt'), 'w', encoding='utf-8') as f:
            f.write(latest_news)
        
        if latest_news.startswith("No news found") or latest_news.startswith("Error fetching news"):
            logging.warning(latest_news)
        else:
            logging.info(f"Successfully processed {symbol} (Query: {query})")
            consolidated_news.append(f"News for {symbol} ({query}):\n{latest_news}\n\n{'='*70}\n\n")
        logging.info("-" * 50)

    with open(os.path.join(output_folder, 'consolidated_news.txt'), 'w', encoding='utf-8') as f:
        f.write("\n".join(consolidated_news))
    logging.info("Consolidated news file created successfully")

if __name__ == "__main__":
    main()