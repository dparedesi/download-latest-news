# News Article Aggregator

This project consists of two Python scripts that fetch and aggregate news articles from different sources: NewsAPI and Alpha Vantage. Both scripts use a common configuration file and output structure.

## Features

- Fetch news articles from NewsAPI or Alpha Vantage
- Process multiple queries or stock symbols
- Retrieve full article content when possible
- Implement error handling and logging
- Create individual news files for each query/symbol
- Generate a consolidated news file
- Configurable through a config file

## Requirements

- Python 3.6+
- Required Python packages:
  - requests
  - beautifulsoup4
  - configparser

## Setup

1. Install the required packages:
   ```
   pip install requests beautifulsoup4 configparser
   ```

2. Create a `config.ini` file in the same directory as the scripts with the following structure:
   ```ini
   [Queries]
   list = 
       IFS(intercorp financial services stock price),
       KSPI(Kaspi.kz stock price),
       CRWD(CRWD stock price),
       # Add more queries as needed

   [API]
   newsapi_key = YOUR_NEWSAPI_KEY
   alphavantage_key = YOUR_ALPHAVANTAGE_KEY

   [Settings]
   news_limit = 5
   ```
   Replace `YOUR_NEWSAPI_KEY` and `YOUR_ALPHAVANTAGE_KEY` with your actual API keys.

## Usage

### NewsAPI Article Aggregator (preferable)

Run the script using Python:
    ```
    python newsapi_article_aggregator.py
    ```

### Alpha Vantage News Fetcher

Run the script using Python:
    ```
    python alphavantage_news_fetcher.py
    ```

Both scripts will create an `output` folder containing:
- Individual news files for each query/symbol (e.g., `IFS_news.txt`)
- A consolidated news file (`consolidated_news.txt`)

## Key Differences

1. **API Source**: 
   - `newsapi_article_aggregator.py` uses NewsAPI
   - `alphavantage_news_fetcher.py` uses Alpha Vantage API

2. **Query Format**:
   - NewsAPI: Uses full queries (e.g., "intercorp financial services stock price")
   - Alpha Vantage: Uses stock symbols (e.g., "IFS")

3. **Concurrency**:
   - NewsAPI script uses concurrent.futures for parallel processing
   - Alpha Vantage script processes queries sequentially

4. **Content Retrieval**:
   - Both attempt to fetch full article content, but with slightly different approaches

## Customization

- Adjust the number of days to look back for news by modifying the `timedelta(days=5)` in the respective `get_latest_news` functions.
- Change the limit of news articles fetched per query/symbol by modifying the `news_limit` in the config file.

## Note

Be mindful of API rate limits when using these scripts. Both NewsAPI and Alpha Vantage have usage restrictions depending on your subscription plan.