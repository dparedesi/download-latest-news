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
        'api_key': config['API']['alphavantage_key'],
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
            return []

        if "feed" not in data or not data["feed"]:
            logging.info(f"No news found for {symbol}")
            return []

        news_items = []
        for index, item in enumerate(data["feed"][:news_limit], 1):
            logging.info(f"Processing news item {index} for {symbol}")

            # Map AlphaVantage fields to our common schema
            news_item = {
                'title': item['title'],
                'url': item['url'],
                'published_at': item['time_published'], # format is YYYYMMDDTHHMMSS
                'description': item['summary'],
                'sentiment_score': float(item.get('overall_sentiment_score', 0)),
                'sentiment_label': item.get('overall_sentiment_label', 'Neutral').capitalize() # Usually "Bullish", "Bearish", etc. or "Neutral"
            }

            # Normalize sentiment label to match TextBlob's Positive/Negative/Neutral
            # AlphaVantage labels: Bearish, Somewhat-Bearish, Neutral, Somewhat-Bullish, Bullish
            label = news_item['sentiment_label']
            if 'Bullish' in label:
                news_item['sentiment_label'] = 'Positive'
            elif 'Bearish' in label:
                news_item['sentiment_label'] = 'Negative'
            else:
                news_item['sentiment_label'] = 'Neutral'

            content = get_article_content(item['url'], session)
            if content:
                news_item['content'] = content
            else:
                news_item['content'] = item['summary']

            news_items.append(news_item)
            time.sleep(1)

        return news_items

    except requests.RequestException as e:
        error_message = f"Error fetching news for {symbol}: {str(e)}"
        logging.error(error_message)
        return []

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def main():
    setup_logging()
    config = load_config('config.ini')
    output_folder = create_output_folder()
    session = create_session()
    
    all_news = []

    for symbol, query in config['queries']:
        logging.info(f"Processing symbol: {symbol} (Query: {query})")
        
        latest_news = get_latest_news(symbol, session, config['api_key'], config['news_limit'])
        safe_symbol = sanitize_filename(symbol)
        
        if not latest_news:
            logging.warning(f"No news found for {symbol}")
            with open(os.path.join(output_folder, f'{safe_symbol}_news.json'), 'w', encoding='utf-8') as f:
                json.dump([], f)
        else:
            logging.info(f"Successfully processed {symbol} (Query: {query})")
            # Save individual JSON
            with open(os.path.join(output_folder, f'{safe_symbol}_news.json'), 'w', encoding='utf-8') as f:
                json.dump(latest_news, f, indent=2)

            all_news.extend(latest_news)

        logging.info("-" * 50)

    # Sort all news items by date (AlphaVantage format YYYYMMDDTHHMMSS)
    # We might need to ensure the sorting key works for both string formats if we were mixing, but here we are consistent within the script.
    if all_news:
        sorted_all_news = sorted(all_news, key=lambda x: x['published_at'], reverse=True)
        with open(os.path.join(output_folder, 'consolidated_news.json'), 'w', encoding='utf-8') as f:
            json.dump(sorted_all_news, f, indent=2)
        logging.info("Consolidated news file created successfully")
    else:
        logging.warning("No news found for any query. Consolidated news file not created.")

if __name__ == "__main__":
    main()
