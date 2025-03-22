from flask import Flask, jsonify, request
import psycopg2
import os
from psycopg2.extras import RealDictCursor
from flask_cors import CORS
import numpy as np
from scipy.stats import zscore

db_params = {
    'dbname': os.getenv('DB_NAME', 'citizix_db'),
    'user': os.getenv('DB_USER', 'citizix_user'),
    'password': os.getenv('DB_PASS', 'S3cret'),
    'host': os.getenv('DB_HOST', '0.0.0.0'),
}

app = Flask(__name__)
CORS(app)

def connect_postgres(params):
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    return conn

@app.route('/rates', methods=['GET'])
def get_rates():
    currency_name = request.args.get('currency_name')
    market_name = request.args.get('market_name')
    conn = connect_postgres(db_params)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT TO_CHAR(r.date, 'YYYY-MM-DD') date, r.open_price, r.close_price,
        r.low_price, r.high_price FROM rates r
        JOIN cryptocurrencies c ON r.cryptocurrency_id = c.id
        JOIN market m ON r.market_id = m.id
        WHERE c.name = %s AND m.name = %s
        ORDER BY r.date ASC;
    """
    cursor.execute(query, (currency_name, market_name))
    rates = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rates)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    currency_name = data.get('currency')
    market_name = data.get('market')
    start_date = data['start_date']
    end_date = data['end_date']
    conn = connect_postgres(db_params)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT TO_CHAR(r.date, 'YYYY-MM-DD') date, r.close_price FROM rates r
        JOIN cryptocurrencies c ON r.cryptocurrency_id = c.id
        JOIN market m ON r.market_id = m.id
        WHERE c.name = %s AND m.name = %s AND r.date BETWEEN %s AND %s
        ORDER BY r.date ASC;
    """
    cursor.execute(query, (currency_name, market_name, start_date, end_date))
    rates = cursor.fetchall()
    cursor.close()
    conn.close()

    close_prices = np.array([float(rate['close_price'][1:].replace(',', '')) for rate in rates])
    
    z_scores = zscore(close_prices)
    
    threshold = 3
    anomalies = np.where(np.abs(z_scores) > threshold)[0]
    anomaly_dates = [rates[i]['date'] for i in anomalies]
    
    return jsonify({
        'anomalies': [{'date': date} for date in anomaly_dates]
    })

@app.route('/analyze_iqr', methods=['POST'])
def analyze_iqr():
    data = request.get_json()
    currency_name = data.get('currency')
    market_name = data.get('market')
    start_date = data['start_date']
    end_date = data['end_date']
    conn = connect_postgres(db_params)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT TO_CHAR(r.date, 'YYYY-MM-DD') date, r.close_price FROM rates r
        JOIN cryptocurrencies c ON r.cryptocurrency_id = c.id
        JOIN market m ON r.market_id = m.id
        WHERE c.name = %s AND m.name = %s AND r.date BETWEEN %s AND %s
        ORDER BY r.date ASC;
    """
    cursor.execute(query, (currency_name, market_name, start_date, end_date))
    rates = cursor.fetchall()
    cursor.close()
    conn.close()

    close_prices = np.array([float(rate['close_price'][1:].replace(',', '')) for rate in rates])
    
    q1 = np.percentile(close_prices, 25)
    q3 = np.percentile(close_prices, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    anomalies = []
    for i, price in enumerate(close_prices):
        if price < lower_bound or price > upper_bound:
            anomalies.append(rates[i])

    return jsonify({
        'anomalies': anomalies
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
