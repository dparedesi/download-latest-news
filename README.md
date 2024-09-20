# Stock News Fetcher

This Python script fetches the latest news articles for specified stock symbols using the Alpha Vantage API. It saves individual news files for each symbol and creates a consolidated news file containing all the fetched news.

## Features

- Fetches news for multiple stock symbols
- Retrieves article content from news URLs
- Implements error handling and logging
- Creates individual news files for each symbol
- Generates a consolidated news file
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

2. Create a `config.ini` file in the same directory as the script with the following structure:
   ```ini
   [Symbols]
   list = AAPL,GOOGL,MSFT

   [API]
   key = YOUR_ALPHA_VANTAGE_API_KEY
   ```
   Replace `YOUR_ALPHA_VANTAGE_API_KEY` with your actual Alpha Vantage API key.

## Usage

Run the script using Python:
```
python news-stocks.py
```


The script will create an `output` folder containing:
- Individual news files for each symbol (e.g., `AAPL_news.txt`)
- A consolidated news file (`consolidated_news.txt`)

## Customization

- Adjust the number of days to look back for news by modifying the `timedelta(days=5)` in the `get_latest_news` function.
- Change the limit of news articles fetched per symbol by modifying the `limit` parameter in the `get_latest_news` function.

## Note

Be mindful of API rate limits when using this script. Alpha Vantage has usage restrictions depending on your subscription plan.
