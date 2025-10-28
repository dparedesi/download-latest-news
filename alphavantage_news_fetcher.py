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
import concurrent.futures

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    # Increase pool size for better parallel performance
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
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
        'api_key': config['API']['alphavantage_key'],
        'news_limit': int(config['Settings']['news_limit'])
    }

def create_output_folder():
    folder_path = 'output'
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_article_content(url, session):
    try:
        # Reduced timeout from 10s to 5s for faster processing
        response = session.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content_elements = soup.find_all(['p', 'article', 'div'], class_=['content', 'article-body', 'story-body'])
        content = '\n'.join([elem.get_text().strip() for elem in content_elements])
        return content[:2000]
    except Exception as e:
        logging.error(f"Error fetching article content: {str(e)}")
        return ""

def process_article_item(item, session):
    """Process a single article item"""
    try:
        news_items = []
        news_items.append(f"Title: {item['title']}")
        news_items.append(f"URL: {item['url']}")
        news_items.append(f"Time Published: {item['time_published']}")
        news_items.append(f"Summary: {item['summary']}")
        content = get_article_content(item['url'], session)
        if content:
            news_items.append(f"Content: {content}")
        news_items.append("-" * 50)
        return "\n".join(news_items)
    except Exception as e:
        logging.error(f"Error processing article item: {str(e)}")
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
        # Use concurrent processing for article content fetching
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_item = {executor.submit(process_article_item, item, session): idx for idx, item in enumerate(data["feed"][:news_limit], 1)}
            for future in concurrent.futures.as_completed(future_to_item):
                idx = future_to_item[future]
                try:
                    result = future.result()
                    if result:
                        logging.info(f"Processing news item {idx} for {symbol}")
                        news_items.append(result)
                except Exception as e:
                    logging.error(f"Error processing news item {idx} for {symbol}: {str(e)}")

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

def process_symbol(symbol_tuple, session, api_key, news_limit, output_folder):
    """Process a single symbol query"""
    symbol, query = symbol_tuple
    logging.info(f"Processing symbol: {symbol} (Query: {query})")
    
    latest_news = get_latest_news(symbol, session, api_key, news_limit)
    safe_symbol = sanitize_filename(symbol)
    with open(os.path.join(output_folder, f'{safe_symbol}_news.txt'), 'w', encoding='utf-8') as f:
        f.write(latest_news)
    
    if latest_news.startswith("No news found") or latest_news.startswith("Error fetching news"):
        logging.warning(latest_news)
        return None
    else:
        logging.info(f"Successfully processed {symbol} (Query: {query})")
        return f"News for {symbol} ({query}):\n{latest_news}\n\n{'='*70}\n\n"

def main():
    setup_logging()
    config = load_config('config.ini')
    output_folder = create_output_folder()
    session = create_session()
    
    consolidated_news = []

    # Use concurrent processing for better performance
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {executor.submit(process_symbol, symbol_tuple, session, config['api_key'], config['news_limit'], output_folder): symbol_tuple for symbol_tuple in config['queries']}
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol_tuple = future_to_symbol[future]
            try:
                result = future.result()
                if result:
                    consolidated_news.append(result)
            except Exception as exc:
                logging.error(f'{symbol_tuple[0]} generated an exception: {exc}')
            logging.info("-" * 50)

    with open(os.path.join(output_folder, 'consolidated_news.txt'), 'w', encoding='utf-8') as f:
        f.write("\n".join(consolidated_news))
    logging.info("Consolidated news file created successfully")

if __name__ == "__main__":
    main()