"""
鑫洁口腔 - 患者转介绍管理系统 (Web版)
手机端 Web App
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'xinjie_dental_2024'

DB_PATH = 'referral_system.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 介绍人表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            gender TEXT,
            referrer_type TEXT DEFAULT '老患者',
            total_referrals INTEGER DEFAULT 0,
            successful_referrals INTEGER DEFAULT 0,
            total_rewards REAL DEFAULT 0,
            notes TEXT,
            status TEXT DEFAULT '活跃',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 患者表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            gender TEXT,
            age INTEGER,
            referrer_id INTEGER,
            referral_date TEXT,
            treatment_items TEXT,
            total_consumption REAL DEFAULT 0,
            is_converted INTEGER DEFAULT 0,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES referrers (id)
        )
    ''')
    
    # 奖励记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            reward_type TEXT DEFAULT '现金',
            reward_amount REAL DEFAULT 0,
            reward_date TEXT,
            status TEXT DEFAULT '待发放',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES referrers (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def update_referrer_stats(referrer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE referrers SET 
            total_referrals = (SELECT COUNT(*) FROM patients WHERE referrer_id = ?),
            successful_referrals = (SELECT COUNT(*) FROM patients WHERE referrer_id = ? AND is_converted = 1),
            total_rewards = (SELECT COALESCE(SUM(reward_amount), 0) FROM rewards WHERE referrer_id = ? AND status = '已发放')
        WHERE id = ?
    ''', (referrer_id, referrer_id, referrer_id, referrer_id))
    conn.commit()
    conn.close()

# ========== 页面路由 ==========

@app.route('/')
def index():
    """首页 - 数据总览"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 统计数据
    cursor.execute("SELECT COUNT(*) FROM referrers WHERE status = '活跃'")
    active_referrers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM patients")
    total_patients = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM patients WHERE is_converted = 1")
    converted = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(total_consumption), 0) FROM patients")
    total_revenue = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(reward_amount), 0) FROM rewards WHERE status = '已发放'")
    total_rewards = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(reward_amount), 0) FROM rewards WHERE status = '待发放'")
    pending_rewards = cursor.fetchone()[0]
    
    # 排行榜
    cursor.execute('''
        SELECT id, name, total_referrals, successful_referrals, total_rewards
        FROM referrers WHERE status = '活跃'
        ORDER BY successful_referrals DESC LIMIT 5
    ''')
    top_referrers = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'active_referrers': active_referrers,
        'total_patients': total_patients,
        'converted': converted,
        'total_revenue': total_revenue,
        'total_rewards': total_rewards,
        'pending_rewards': pending_rewards
    }
    
    return render_template('index.html', stats=stats, top_referrers=top_referrers)

@app.route('/referrers')
def referrers_page():
    """介绍人列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM referrers ORDER BY successful_referrals DESC')
    referrers = cursor.fetchall()
    conn.close()
    return render_template('referrers.html', referrers=referrers)

@app.route('/referrer/add', methods=['GET', 'POST'])
def add_referrer():
    """添加介绍人"""
    if request.method == 'POST':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO referrers (name, phone, gender, referrer_type, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            request.form['name'],
            request.form.get('phone', ''),
            request.form.get('gender', ''),
            request.form.get('referrer_type', '老患者'),
            request.form.get('notes', '')
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('referrers_page'))
    return render_template('referrer_form.html', referrer=None)

@app.route('/referrer/edit/<int:id>', methods=['GET', 'POST'])
def edit_referrer(id):
    """编辑介绍人"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        cursor.execute('''
            UPDATE referrers SET name=?, phone=?, gender=?, referrer_type=?, notes=?, status=?
            WHERE id=?
        ''', (
            request.form['name'],
            request.form.get('phone', ''),
            request.form.get('gender', ''),
            request.form.get('referrer_type', '老患者'),
            request.form.get('notes', ''),
            request.form.get('status', '活跃'),
            id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('referrers_page'))
    
    cursor.execute('SELECT * FROM referrers WHERE id = ?', (id,))
    referrer = cursor.fetchone()
    conn.close()
    return render_template('referrer_form.html', referrer=referrer)

@app.route('/referrer/delete/<int:id>')
def delete_referrer(id):
    """删除介绍人"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM referrers WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('referrers_page'))

@app.route('/patients')
def patients_page():
    """患者列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, r.name as referrer_name 
        FROM patients p 
        LEFT JOIN referrers r ON p.referrer_id = r.id 
        ORDER BY p.created_at DESC
    ''')
    patients = cursor.fetchall()
    conn.close()
    return render_template('patients.html', patients=patients)

@app.route('/patient/add', methods=['GET', 'POST'])
def add_patient():
    """添加患者"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        referrer_id = request.form.get('referrer_id')
        referrer_id = int(referrer_id) if referrer_id else None
        
        cursor.execute('''
            INSERT INTO patients (name, phone, gender, age, referrer_id, referral_date, 
                   treatment_items, total_consumption, is_converted, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.form['name'],
            request.form.get('phone', ''),
            request.form.get('gender', ''),
            int(request.form['age']) if request.form.get('age') else None,
            referrer_id,
            request.form.get('referral_date', datetime.now().strftime('%Y-%m-%d')),
            request.form.get('treatment_items', ''),
            float(request.form.get('total_consumption', 0) or 0),
            1 if request.form.get('is_converted') else 0,
            request.form.get('notes', '')
        ))
        conn.commit()
        
        if referrer_id:
            update_referrer_stats(referrer_id)
        
        conn.close()
        return redirect(url_for('patients_page'))
    
    cursor.execute("SELECT id, name, phone FROM referrers WHERE status = '活跃' ORDER BY name")
    referrers = cursor.fetchall()
    conn.close()
    return render_template('patient_form.html', patient=None, referrers=referrers)

@app.route('/patient/edit/<int:id>', methods=['GET', 'POST'])
def edit_patient(id):
    """编辑患者"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        old_referrer_id = None
        cursor.execute('SELECT referrer_id FROM patients WHERE id = ?', (id,))
        result = cursor.fetchone()
        if result:
            old_referrer_id = result[0]
        
        referrer_id = request.form.get('referrer_id')
        referrer_id = int(referrer_id) if referrer_id else None
        
        cursor.execute('''
            UPDATE patients SET name=?, phone=?, gender=?, age=?, referrer_id=?, 
                   referral_date=?, treatment_items=?, total_consumption=?, is_converted=?, notes=?
            WHERE id=?
        ''', (
            request.form['name'],
            request.form.get('phone', ''),
            request.form.get('gender', ''),
            int(request.form['age']) if request.form.get('age') else None,
            referrer_id,
            request.form.get('referral_date', ''),
            request.form.get('treatment_items', ''),
            float(request.form.get('total_consumption', 0) or 0),
            1 if request.form.get('is_converted') else 0,
            request.form.get('notes', ''),
            id
        ))
        conn.commit()
        
        if old_referrer_id:
            update_referrer_stats(old_referrer_id)
        if referrer_id and referrer_id != old_referrer_id:
            update_referrer_stats(referrer_id)
        
        conn.close()
        return redirect(url_for('patients_page'))
    
    cursor.execute('SELECT * FROM patients WHERE id = ?', (id,))
    patient = cursor.fetchone()
    cursor.execute("SELECT id, name, phone FROM referrers WHERE status = '活跃' ORDER BY name")
    referrers = cursor.fetchall()
    conn.close()
    return render_template('patient_form.html', patient=patient, referrers=referrers)

@app.route('/patient/delete/<int:id>')
def delete_patient(id):
    """删除患者"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT referrer_id FROM patients WHERE id = ?', (id,))
    result = cursor.fetchone()
    referrer_id = result[0] if result else None
    
    cursor.execute('DELETE FROM patients WHERE id = ?', (id,))
    conn.commit()
    
    if referrer_id:
        update_referrer_stats(referrer_id)
    
    conn.close()
    return redirect(url_for('patients_page'))

@app.route('/rewards')
def rewards_page():
    """奖励列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rw.*, r.name as referrer_name
        FROM rewards rw
        LEFT JOIN referrers r ON rw.referrer_id = r.id
        ORDER BY rw.created_at DESC
    ''')
    rewards = cursor.fetchall()
    conn.close()
    return render_template('rewards.html', rewards=rewards)

@app.route('/reward/add', methods=['GET', 'POST'])
def add_reward():
    """添加奖励"""
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        referrer_id = int(request.form['referrer_id'])
        status = request.form.get('status', '已发放')
        
        cursor.execute('''
            INSERT INTO rewards (referrer_id, reward_type, reward_amount, reward_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            referrer_id,
            request.form.get('reward_type', '现金'),
            float(request.form.get('reward_amount', 0) or 0),
            request.form.get('reward_date', datetime.now().strftime('%Y-%m-%d')),
            status,
            request.form.get('notes', '')
        ))
        conn.commit()
        
        if status == '已发放':
            update_referrer_stats(referrer_id)
        
        conn.close()
        return redirect(url_for('rewards_page'))
    
    cursor.execute("SELECT id, name, phone FROM referrers WHERE status = '活跃' ORDER BY name")
    referrers = cursor.fetchall()
    conn.close()
    return render_template('reward_form.html', referrers=referrers)

@app.route('/reward/pay/<int:id>')
def pay_reward(id):
    """标记奖励已发放"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT referrer_id FROM rewards WHERE id = ?', (id,))
    result = cursor.fetchone()
    
    cursor.execute("UPDATE rewards SET status = '已发放' WHERE id = ?", (id,))
    conn.commit()
    
    if result:
        update_referrer_stats(result[0])
    
    conn.close()
    return redirect(url_for('rewards_page'))

@app.route('/stats')
def stats_page():
    """统计页面"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 总体统计
    cursor.execute("SELECT COUNT(*) FROM referrers WHERE status = '活跃'")
    active_referrers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM patients")
    total_patients = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM patients WHERE is_converted = 1")
    converted = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(total_consumption), 0) FROM patients")
    total_revenue = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(reward_amount), 0) FROM rewards WHERE status = '已发放'")
    total_rewards = cursor.fetchone()[0]
    
    # 排行榜
    cursor.execute('''
        SELECT id, name, phone, total_referrals, successful_referrals, total_rewards
        FROM referrers WHERE status = '活跃'
        ORDER BY successful_referrals DESC LIMIT 10
    ''')
    top_referrers = cursor.fetchall()
    
    conn.close()
    
    conversion_rate = (converted / total_patients * 100) if total_patients > 0 else 0
    avg_consumption = total_revenue / converted if converted > 0 else 0
    roi = total_revenue / total_rewards if total_rewards > 0 else 0
    
    stats = {
        'active_referrers': active_referrers,
        'total_patients': total_patients,
        'converted': converted,
        'conversion_rate': conversion_rate,
        'total_revenue': total_revenue,
        'avg_consumption': avg_consumption,
        'total_rewards': total_rewards,
        'roi': roi
    }
    
    return render_template('stats.html', stats=stats, top_referrers=top_referrers)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)

