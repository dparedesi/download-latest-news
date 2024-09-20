import configparser
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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
    return {
        'symbols': config['Symbols']['list'].split(','),
        'api_key': config['API']['key']
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
        
        # Look for article content in common HTML elements
        content_elements = soup.find_all(['p', 'article', 'div'], class_=['content', 'article-body', 'story-body'])
        content = '\n'.join([elem.get_text().strip() for elem in content_elements])
        return content[:2000]  # Return first 2000 characters to keep it manageable
    except Exception as e:
        logging.error(f"Error fetching article content: {str(e)}")
        return ""

def get_latest_news(symbol, session, api_key):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "time_from": (datetime.now() - timedelta(days=60)).strftime("%Y%m%dT%H%M"),
        "sort": "LATEST",
        "limit": 50,
        "apikey": api_key
    }

    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if "feed" not in data or not data["feed"]:
            logging.info(f"No news found for {symbol}")
            return f"No news found for {symbol}"

        news_items = []
        for index, item in enumerate(data["feed"], 1):
            logging.info(f"Processing news item {index} for {symbol}")
            news_items.append(f"Title: {item['title']}")
            news_items.append(f"URL: {item['url']}")
            news_items.append(f"Time Published: {item['time_published']}")
            news_items.append(f"Summary: {item['summary']}")
            content = get_article_content(item['url'], session)
            if content:
                news_items.append(f"Content: {content}")
            news_items.append("-" * 50)
            time.sleep(1)  # Be polite to the servers

        return "\n".join(news_items)

    except requests.RequestException as e:
        error_message = f"Error fetching news for {symbol}: {str(e)}"
        logging.error(error_message)
        return error_message

def main():
    setup_logging()
    config = load_config('config.ini')
    output_folder = create_output_folder()
    session = create_session()
    
    for symbol in config['symbols']:
        logging.info(f"Processing symbol: {symbol}")
        
        # Get and save latest news
        latest_news = get_latest_news(symbol, session, config['api_key'])
        with open(os.path.join(output_folder, f'{symbol}_news.txt'), 'w', encoding='utf-8') as f:
            f.write(latest_news)
        
        if latest_news.startswith("No news found") or latest_news.startswith("Error fetching news"):
            logging.warning(latest_news)
        else:
            logging.info(f"Successfully processed {symbol}")
        logging.info("-" * 50)

if __name__ == "__main__":
    main()
