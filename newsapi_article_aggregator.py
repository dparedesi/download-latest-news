import configparser
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import concurrent.futures
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
        
        main_content = soup.find(['article', 'main', 'div'], class_=['article-content', 'main-content', 'story-body'])
        
        if main_content:
            paragraphs = main_content.find_all('p')
        else:
            paragraphs = soup.find_all('p')
        
        content = ' '.join([p.get_text().strip() for p in paragraphs])
        content = ' '.join(content.split())
        
        return content
    except Exception as e:
        logging.error(f"Error fetching article content: {str(e)}")
        return ""

def get_latest_news(query, session, api_key, news_limit):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": api_key,
        "pageSize": news_limit
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
            logging.error(f"Error decoding JSON for query {query}: {str(e)}")
            return f"Error decoding JSON for {query}"

        if "articles" not in data or not data["articles"]:
            logging.info(f"No news found for {query}")
            return f"No news found for {query}"

        news_items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            news_items.append(f"List of news related to {query.replace("+", "")}:")
            future_to_item = {executor.submit(process_news_item, item, session): item for item in data["articles"][:news_limit]}
            for future in concurrent.futures.as_completed(future_to_item):
                news_items.append(future.result())

        return "\n".join(news_items)

    except requests.RequestException as e:
        error_message = f"Error fetching news for {query}: {str(e)}"
        logging.error(error_message)
        return error_message

def process_news_item(item, session):
    news_item = []
    news_item.append(f"Title: {item['title']}")
    news_item.append(f"URL: {item['url']}")
    news_item.append(f"Time Published: {item['publishedAt']}")
    
    content = get_article_content(item['url'], session)
    
    if content:
        content = truncate_content(content)
        news_item.append(f"Full Content:\n{content}")
    else:
        news_item.append(f"Description: {item['description']}")
    
    news_item.append("-" * 50)
    return "\n".join(news_item)

def truncate_content(content, max_length=5000):
    if len(content) > max_length:
        return content[:max_length] + "... (truncated)"
    return content

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def process_query(query_tuple, session, api_key, news_limit, output_folder):
    symbol, query = query_tuple
    logging.info(f"Processing query: {query} (Symbol: {symbol})")
    
    latest_news = get_latest_news(query, session, api_key, news_limit)
    safe_symbol = sanitize_filename(symbol)
    with open(os.path.join(output_folder, f'{safe_symbol}_news.txt'), 'w', encoding='utf-8') as f:
        f.write(latest_news)
    
    if latest_news.startswith("No news found") or latest_news.startswith("Error fetching news"):
        logging.warning(latest_news)
        return None
    else:
        logging.info(f"Successfully processed {query} (Symbol: {symbol})")
        return f"News for {symbol} ({query}):\n{latest_news}\n\n{'='*70}\n\n"

def main():
    setup_logging()
    config = load_config('config.ini')
    output_folder = create_output_folder()
    session = create_session()
    
    consolidated_news = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_query = {executor.submit(process_query, query_tuple, session, config['api_key'], config['news_limit'], output_folder): query_tuple for query_tuple in config['queries']}
        try:
            for future in concurrent.futures.as_completed(future_to_query, timeout=300):  # 5 minutes timeout
                query_tuple = future_to_query[future]
                try:
                    result = future.result()
                    if result:
                        consolidated_news.append(result)
                except Exception as exc:
                    logging.error(f'{query_tuple[1]} (Symbol: {query_tuple[0]}) generated an exception: {exc}')
        except concurrent.futures.TimeoutError:
            logging.error("Execution timed out after 5 minutes")

    with open(os.path.join(output_folder, 'consolidated_news.txt'), 'w', encoding='utf-8') as f:
        f.write("\n".join(consolidated_news))
    logging.info("Consolidated news file created successfully")

if __name__ == "__main__":
    main()