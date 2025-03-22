import os
import ccxt
import pandas as pd
import psycopg2
from datetime import datetime, time

exchange_binance = ccxt.binance({
    'rateLimit': 1200,
    'enableRateLimit': True,
})

exchange_kucoin = ccxt.kucoin({
    'rateLimit': 1200,
    'enableRateLimit': True,
})

db_params = {
    'dbname': os.getenv('DB_NAME', 'citizix_db'),
    'user': os.getenv('DB_USER', 'citizix_user'),
    'password': os.getenv('DB_PASS', 'S3cret'),
    'host': os.getenv('DB_HOST', 'postgres'),
}

def connect_postgres(params):
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    return conn

def formate_date(date):
    combined_datetime = datetime.combine(date, time(0, 0))
    formatted_datetime = combined_datetime.isoformat() + 'Z'
    return formatted_datetime

def fetch_data(pair, market, timeframe='1d', since=None):
    exchange = exchange_binance if market == 'Binance' else exchange_kucoin
    if since is None:
        since = exchange.parse8601('2017-01-01T00:00:00Z')
    else:
        since = exchange.parse8601(formate_date(since))
    all_ohlcv = []

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(pair, timeframe, since)
            if not ohlcv:
                break
            since = ohlcv[-1][0] + 86400000
            all_ohlcv.extend(ohlcv)
        except ccxt.ExchangeError as e:
            print(f"An error occurred: {e}")
            break
        except ccxt.NetworkError as e:
            print(f"Check your network connection: {e}")
            break

    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def create_tables(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cryptocurrencies (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            symbol VARCHAR(10) NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id SERIAL PRIMARY KEY,
            cryptocurrency_id INTEGER REFERENCES cryptocurrencies(id),
            market_id INTEGER REFERENCES market(id),
            open_price MONEY NOT NULL,
            close_price MONEY NOT NULL,
            low_price MONEY NOT NULL,
            high_price MONEY NOT NULL,
            volume MONEY NOT NULL,
            date TIMESTAMP WITHOUT TIME ZONE NOT NULL
        );
    """)
    conn.commit()
    cursor.close()

def todays_data_exists(conn, pair_symbol, market_name):
    cursor = conn.cursor()
    today = datetime.now().date()
    cursor.execute(f"""
        SELECT EXISTS (
            SELECT 1 FROM rates JOIN cryptocurrencies c ON c.id = cryptocurrency_id
            JOIN market m ON m.id = market_id
            WHERE date BETWEEN '{str(today)}' AND '{str(today)}' AND c.symbol = '{pair_symbol}' AND m.name = '{market_name}'
        );
    """)
    exists = cursor.fetchone()[0]
    cursor.close()
    return exists

def check_cryptocurrency_exists(conn, pair_symbol, market_name):
    cursor = conn.cursor()
    cursor.execute(f"""
                   SELECT EXISTS (SELECT 1 FROM rates JOIN cryptocurrencies c ON c.id = cryptocurrency_id 
                   JOIN market m ON m.id = market_id WHERE c.symbol = '{pair_symbol}' AND m.name = '{market_name}');
                   """)
    exists = cursor.fetchone()[0]
    cursor.close()
    return exists

def update_database(conn, pair, pair_name, pair_symbol, market_name):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM market WHERE name = %s;", (market_name,))
    market_result = cursor.fetchone()
    if market_result is None:
        cursor.execute("INSERT INTO market (name) VALUES (%s) RETURNING id;", (market_name,))
        market_id = cursor.fetchone()[0]
    else:
        market_id = market_result[0]

    cursor.execute("SELECT id FROM cryptocurrencies WHERE symbol = %s;", (pair_symbol,))
    crypto_result = cursor.fetchone()
    if crypto_result is None:
        cursor.execute("INSERT INTO cryptocurrencies (name, symbol) VALUES (%s, %s) RETURNING id;", (pair_name, pair_symbol))
        cryptocurrency_id = cursor.fetchone()[0]
    else:
        cryptocurrency_id = crypto_result[0]

    conn.commit()

    if todays_data_exists(conn, pair_symbol, market_name):
        print(f"Today's data already exists for {pair_name}. Skipping update.")
        return
    elif not check_cryptocurrency_exists(conn, pair_symbol, market_name):
        print('fetching all data')
        data = fetch_data(pair, market_name)
    else:
        print('fetching data from today')
        data = fetch_data(pair, market_name, '1d', datetime.now().date())
    print(data)
    for index, row in data.iterrows():
        cursor.execute("""
            INSERT INTO rates (cryptocurrency_id, market_id, open_price, close_price, low_price, high_price, volume, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (cryptocurrency_id, market_id, row['open'], row['close'], row['low'], row['high'], row['volume'], index))

    conn.commit()
    cursor.close()

# Main process
conn = connect_postgres(db_params)
create_tables(conn)
currencies = {
        'BTC/USDT': ('Bitcoin', 'BTC'),
        'ETH/USDT': ('Ethereum', 'ETH'),
        'BNB/USDT': ('BNB', 'BNB'),
        'ADA/USDT': ('Cardano', 'ADA'),
        'XRP/USDT': ('Ripple', 'XRP')}
markets = {
    'Binance' : currencies,
    'Kucoin' : currencies
}
for market_name, pairs_dict in markets.items():
    for pair, (name, symbol) in pairs_dict.items():
        print(f"Processing data for {pair}, {market_name}")
        update_database(conn, pair, name, symbol, market_name)

conn.close()
print("Data update complete.")
