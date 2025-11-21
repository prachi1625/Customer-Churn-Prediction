from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Database initialization
def init_db():
    conn = sqlite3.connect('churn_prediction.db')
    cursor = conn.cursor()
    
    # Create customers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            tenure INTEGER,
            monthly_charges REAL,
            total_charges REAL,
            support_tickets INTEGER,
            contract TEXT,
            payment_method TEXT,
            internet_service TEXT,
            tech_support TEXT,
            online_security TEXT,
            senior_citizen TEXT,
            dependents TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create predictions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_db_id INTEGER,
            customer_id TEXT,
            probability INTEGER,
            risk_level TEXT,
            will_churn INTEGER,
            factors TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_db_id) REFERENCES customers (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

def get_db():
    conn = sqlite3.connect('churn_prediction.db')
    conn.row_factory = sqlite3.Row
    return conn

# ML Prediction Logic
def calculate_churn(data):
    score = 0
    
    tenure = data.get('tenure', 0)
    if tenure < 6:
        score += 25
    elif tenure < 12:
        score += 15
    elif tenure < 24:
        score += 5
    
    if data.get('contract') == 'month':
        score += 20
    elif data.get('contract') == 'year':
        score += 5
    
    monthly = data.get('monthlyCharges', 0)
    if monthly > 80:
        score += 15
    elif monthly > 60:
        score += 8
    
    tickets = data.get('supportTickets', 0)
    if tickets > 5:
        score += 20
    elif tickets > 2:
        score += 10
    
    if data.get('paymentMethod') == 'electronic':
        score += 5
    if data.get('internetService') == 'fiber':
        score += 8
    if data.get('techSupport') == 'no':
        score += 10
    if data.get('onlineSecurity') == 'no':
        score += 8
    if data.get('seniorCitizen') == 'yes':
        score += 5
    if data.get('dependents') == 'no':
        score += 5
    
    probability = min(max(score, 5), 95)
    
    if probability > 70:
        risk_level = 'high'
    elif probability > 40:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    return {
        'probability': probability,
        'willChurn': probability > 50,
        'riskLevel': risk_level
    }

def get_factors(data):
    factors = []
    if data.get('tenure', 0) < 12:
        factors.append('Short tenure period')
    if data.get('contract') == 'month':
        factors.append('Month-to-month contract')
    if data.get('supportTickets', 0) > 3:
        factors.append('High support ticket volume')
    if data.get('monthlyCharges', 0) > 70:
        factors.append('High monthly charges')
    if data.get('techSupport') == 'no':
        factors.append('No tech support subscription')
    if data.get('onlineSecurity') == 'no':
        factors.append('No online security')
    return factors[:3]

# Routes
@app.route('/')
def index():
    return render_template('churn_prediction.html')

@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Insert customer data
    cursor.execute('''
        INSERT INTO customers (customer_id, tenure, monthly_charges, total_charges,
            support_tickets, contract, payment_method, internet_service,
            tech_support, online_security, senior_citizen, dependents)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('customerId', 'Unknown'),
        data.get('tenure', 0),
        data.get('monthlyCharges', 0),
        data.get('totalCharges', 0),
        data.get('supportTickets', 0),
        data.get('contract', ''),
        data.get('paymentMethod', ''),
        data.get('internetService', ''),
        data.get('techSupport', ''),
        data.get('onlineSecurity', ''),
        data.get('seniorCitizen', ''),
        data.get('dependents', '')
    ))
    
    customer_db_id = cursor.lastrowid
    
    # Calculate prediction
    result = calculate_churn(data)
    factors = get_factors(data)
    
    # Insert prediction
    cursor.execute('''
        INSERT INTO predictions (customer_db_id, customer_id, probability, 
            risk_level, will_churn, factors)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        customer_db_id,
        data.get('customerId', 'Unknown'),
        result['probability'],
        result['riskLevel'],
        1 if result['willChurn'] else 0,
        ','.join(factors)
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'probability': result['probability'],
        'willChurn': result['willChurn'],
        'riskLevel': result['riskLevel'],
        'factors': factors
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM customers')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM predictions WHERE will_churn = 1')
    churn = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM predictions WHERE will_churn = 0')
    retained = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'totalCustomers': total,
        'churnCount': churn,
        'retainedCount': retained
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, c.tenure, c.monthly_charges, c.contract
        FROM predictions p
        JOIN customers c ON p.customer_db_id = c.id
        ORDER BY p.created_at DESC
        LIMIT 50
    ''')
    
    rows = cursor.fetchall()
    history = []
    for row in rows:
        history.append({
            'id': row['id'],
            'customerId': row['customer_id'],
            'probability': row['probability'],
            'riskLevel': row['risk_level'],
            'willChurn': bool(row['will_churn']),
            'tenure': row['tenure'],
            'monthlyCharges': row['monthly_charges'],
            'contract': row['contract'],
            'createdAt': row['created_at']
        })
    
    conn.close()
    return jsonify(history)

if __name__ == '__main__':
    print("=" * 50)
    print("Customer Churn Prediction System")
    print("=" * 50)
    print("Server running at: http://127.0.0.1:5000")
    print("Database file: churn_prediction.db")
    print("Open with DB Browser for SQLite to view data")
    print("=" * 50)
    app.run(debug=True)