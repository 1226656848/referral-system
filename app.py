"""
鑫洁口腔 - 患者转介绍管理系统 (智能版)
"""

from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'xinjie_dental_2024'

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

# 默认提成比例（可在设置中修改）
DEFAULT_COMMISSION_RATE = 10  # 10%

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 系统设置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # 介绍人表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            type TEXT DEFAULT '老患者',
            gender TEXT DEFAULT '',
            birthday TEXT DEFAULT '',
            address TEXT DEFAULT '',
            workplace TEXT DEFAULT '',
            commission_rate REAL DEFAULT 10,
            notes TEXT DEFAULT '',
            referrals INTEGER DEFAULT 0,
            converted INTEGER DEFAULT 0,
            rewards REAL DEFAULT 0,
            pending_rewards REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 患者表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            referrer_id INTEGER,
            treatment TEXT,
            amount REAL DEFAULT 0,
            is_converted INTEGER DEFAULT 0,
            reward_amount REAL DEFAULT 0,
            reward_status TEXT DEFAULT '待发放',
            referral_date TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 奖励记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            patient_id INTEGER,
            type TEXT DEFAULT '现金',
            amount REAL DEFAULT 0,
            date TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 礼品库表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT '实物礼品',
            cost REAL DEFAULT 0,
            value REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 添加 value 字段（兼容旧数据）
    try:
        cursor.execute("ALTER TABLE gift_items ADD COLUMN value REAL DEFAULT 0")
    except: pass
    
    # 初始化默认设置
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('commission_rate', '10')")
    
    # 添加新字段（兼容旧数据库）
    new_columns = [
        ("referrers", "gender", "TEXT DEFAULT ''"),
        ("referrers", "birthday", "TEXT DEFAULT ''"),
        ("referrers", "address", "TEXT DEFAULT ''"),
        ("referrers", "workplace", "TEXT DEFAULT ''"),
        ("referrers", "commission_rate", "REAL DEFAULT 10"),
        ("referrers", "notes", "TEXT DEFAULT ''"),
        ("referrers", "pending_rewards", "REAL DEFAULT 0"),
        ("patients", "reward_amount", "REAL DEFAULT 0"),
        ("patients", "reward_status", "TEXT DEFAULT '待发放'"),
        ("rewards", "patient_id", "INTEGER"),
        ("rewards", "notes", "TEXT DEFAULT ''"),
    ]
    for table, col, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except: pass
    
    conn.commit()
    conn.close()

def get_setting(key, default=''):
    conn = get_db()
    r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return r['value'] if r else default

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_referrer_commission_rate(referrer_id):
    conn = get_db()
    r = conn.execute("SELECT commission_rate FROM referrers WHERE id = ?", (referrer_id,)).fetchone()
    conn.close()
    if r and r['commission_rate']:
        return r['commission_rate']
    return float(get_setting('commission_rate', DEFAULT_COMMISSION_RATE))

def calculate_reward(amount, referrer_id):
    """计算奖励金额"""
    rate = get_referrer_commission_rate(referrer_id)
    return round(amount * rate / 100, 2)

def update_referrer_stats(referrer_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM patients WHERE referrer_id = ?', (referrer_id,))
    referrals = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM patients WHERE referrer_id = ? AND is_converted = 1', (referrer_id,))
    converted = cursor.fetchone()[0]
    cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE referrer_id = ?', (referrer_id,))
    rewards = cursor.fetchone()[0]
    # 计算待发放奖励
    cursor.execute('''SELECT COALESCE(SUM(reward_amount), 0) FROM patients 
                     WHERE referrer_id = ? AND is_converted = 1 AND reward_status = '待发放' ''', (referrer_id,))
    pending = cursor.fetchone()[0]
    cursor.execute('UPDATE referrers SET referrals=?, converted=?, rewards=?, pending_rewards=? WHERE id=?', 
                   (referrals, converted, rewards, pending, referrer_id))
    conn.commit()
    conn.close()

# HTML模板
BASE_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <title>转介绍管理</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #F1F5F9; color: #1E293B; padding-bottom: 70px; }
        .header { background: linear-gradient(135deg, #3B82F6, #2563EB); color: white; padding: 15px 20px; position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 18px; }
        .content { padding: 15px; }
        .card { background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .card-title { font-size: 16px; font-weight: 600; margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .stat-item { text-align: center; padding: 12px 5px; background: #F8FAFC; border-radius: 10px; }
        .stat-icon { font-size: 24px; margin-bottom: 5px; }
        .stat-value { font-size: 18px; font-weight: 700; color: #3B82F6; }
        .stat-label { font-size: 11px; color: #64748B; }
        .btn { display: block; width: 100%; padding: 12px; border-radius: 10px; font-size: 15px; font-weight: 600; text-decoration: none; text-align: center; border: none; cursor: pointer; margin-bottom: 10px; }
        .btn-primary { background: linear-gradient(135deg, #3B82F6, #2563EB); color: white; }
        .btn-success { background: linear-gradient(135deg, #10B981, #059669); color: white; }
        .btn-warning { background: linear-gradient(135deg, #F59E0B, #D97706); color: white; }
        .btn-danger { background: #EF4444; color: white; }
        .btn-gray { background: #94A3B8; color: white; }
        .btn-sm { display: inline-block; width: auto; padding: 6px 12px; font-size: 12px; margin: 2px; }
        .form-group { margin-bottom: 15px; }
        .form-label { display: block; font-size: 14px; margin-bottom: 6px; color: #374151; }
        .form-input, .form-select { width: 100%; padding: 12px; border: 1px solid #D1D5DB; border-radius: 10px; font-size: 16px; }
        .form-hint { font-size: 12px; color: #64748B; margin-top: 4px; }
        .list-item { display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid #E2E8F0; }
        .list-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #3B82F6, #8B5CF6); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; margin-right: 12px; font-size: 14px; flex-shrink: 0; }
        .list-info { flex: 1; min-width: 0; }
        .list-name { font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .list-detail { font-size: 12px; color: #64748B; margin-top: 2px; }
        .badge { padding: 3px 8px; border-radius: 10px; font-size: 11px; white-space: nowrap; }
        .badge-success { background: #D1FAE5; color: #059669; }
        .badge-warning { background: #FEF3C7; color: #D97706; }
        .badge-danger { background: #FEE2E2; color: #DC2626; }
        .badge-info { background: #DBEAFE; color: #2563EB; }
        .alert { padding: 12px 15px; border-radius: 10px; margin-bottom: 15px; font-size: 14px; }
        .alert-warning { background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; }
        .alert-success { background: #D1FAE5; color: #065F46; border: 1px solid #6EE7B7; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: white; display: flex; justify-content: space-around; padding: 8px 0; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); }
        .nav-item { display: flex; flex-direction: column; align-items: center; color: #64748B; font-size: 11px; text-decoration: none; padding: 5px 15px; }
        .nav-item.active { color: #3B82F6; }
        .nav-item span { font-size: 20px; }
        .nav-badge { background: #EF4444; color: white; font-size: 10px; padding: 2px 6px; border-radius: 10px; position: absolute; top: -5px; right: -5px; }
        .empty { text-align: center; padding: 30px; color: #94A3B8; }
        .reward-pending { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
    </style>
</head>
<body>
    <header class="header"><h1>{{ title }}</h1></header>
    <div class="content">{{ content | safe }}</div>
    <nav class="bottom-nav">
        <a href="/" class="nav-item {{ 'active' if page == 'home' else '' }}"><span>🏠</span>首页</a>
        <a href="/referrers" class="nav-item {{ 'active' if page == 'referrers' else '' }}"><span>👥</span>介绍人</a>
        <a href="/patients" class="nav-item {{ 'active' if page == 'patients' else '' }}"><span>🧑‍⚕️</span>患者</a>
        <a href="/pending-rewards" class="nav-item {{ 'active' if page == 'pending' else '' }}" style="position:relative"><span>💰</span>待发奖励{{ pending_badge | safe }}</a>
        <a href="/settings" class="nav-item {{ 'active' if page == 'settings' else '' }}"><span>⚙️</span>设置</a>
    </nav>
</body>
</html>
'''

def get_pending_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM patients WHERE is_converted = 1 AND reward_status = '待发放' AND referrer_id IS NOT NULL").fetchone()[0]
    conn.close()
    return count

def render_page(title, content, page):
    pending = get_pending_count()
    pending_badge = f'<span class="nav-badge">{pending}</span>' if pending > 0 else ''
    return render_template_string(BASE_HTML, title=title, content=content, page=page, pending_badge=pending_badge)

@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrers")
    ref_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM patients")
    pat_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM patients WHERE is_converted = 1")
    converted = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM patients WHERE is_converted = 1")
    revenue = c.fetchone()[0]
    
    # 分开统计现金和实物奖励
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE type LIKE '%现金%' OR type LIKE '%红包%'")
    cash_rewards = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE type NOT LIKE '%现金%' AND type NOT LIKE '%红包%'")
    gift_rewards = c.fetchone()[0]
    total_rewards = cash_rewards + gift_rewards
    
    c.execute("SELECT COUNT(*) FROM patients WHERE is_converted = 1 AND reward_status = '待发放' AND referrer_id IS NOT NULL")
    pending_count = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(reward_amount), 0) FROM patients WHERE is_converted = 1 AND reward_status = '待发放' AND referrer_id IS NOT NULL")
    pending_amount = c.fetchone()[0]
    rate = (converted / pat_count * 100) if pat_count > 0 else 0
    
    c.execute("SELECT * FROM referrers ORDER BY converted DESC LIMIT 5")
    top = c.fetchall()
    conn.close()
    
    # 待发奖励提醒
    alert_html = ""
    if pending_count > 0:
        alert_html = f'''<div class="alert alert-warning reward-pending">
            ⚠️ 有 <strong>{pending_count}</strong> 笔奖励待发放，共 <strong>¥{pending_amount:.0f}</strong>
            <a href="/pending-rewards" style="float:right;color:#92400E;font-weight:600">去处理 →</a>
        </div>'''
    
    rank_html = ""
    for i, r in enumerate(top):
        pending = r["pending_rewards"] if "pending_rewards" in r.keys() else 0
        pending_tag = f'<span class="badge badge-warning">待发¥{pending:.0f}</span>' if pending > 0 else ''
        rank_html += f'''<div class="list-item">
            <div class="list-avatar">{i+1}</div>
            <div class="list-info">
                <div class="list-name">{r["name"]} {pending_tag}</div>
                <div class="list-detail">介绍{r["referrals"]}人·成交{r["converted"]}人·已发¥{r["rewards"]:.0f}</div>
            </div>
        </div>'''
    if not top:
        rank_html = '<div class="empty">暂无数据</div>'
    
    content = f'''
    {alert_html}
    <div class="card">
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-icon">👥</div><div class="stat-value">{ref_count}</div><div class="stat-label">介绍人</div></div>
            <div class="stat-item"><div class="stat-icon">🧑‍⚕️</div><div class="stat-value">{pat_count}</div><div class="stat-label">总患者</div></div>
            <div class="stat-item"><div class="stat-icon">✅</div><div class="stat-value">{converted}</div><div class="stat-label">已成交</div></div>
            <div class="stat-item"><div class="stat-icon">💰</div><div class="stat-value">{revenue:.0f}</div><div class="stat-label">总营收</div></div>
            <div class="stat-item"><div class="stat-icon">💵</div><div class="stat-value">{cash_rewards:.0f}</div><div class="stat-label">现金奖励</div></div>
            <div class="stat-item"><div class="stat-icon">🎁</div><div class="stat-value">{gift_rewards:.0f}</div><div class="stat-label">实物奖励</div></div>
        </div>
    </div>
    <div class="card" style="padding:10px 15px">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="color:#64748B">📊 转化率: <strong style="color:#3B82F6">{rate:.0f}%</strong></span>
            <span style="color:#64748B">🎁 奖励合计: <strong style="color:#F59E0B">¥{total_rewards:.0f}</strong></span>
        </div>
    </div>
    <div class="card">
        <div class="card-title">⚡ 快捷操作</div>
        <a href="/referrer/add" class="btn btn-primary">➕ 新增介绍人</a>
        <a href="/patient/add" class="btn btn-success">➕ 新增患者</a>
        <a href="/pending-rewards" class="btn btn-warning">💰 处理待发奖励 ({pending_count})</a>
    </div>
    <div class="card">
        <div class="card-title">🏆 介绍人排行</div>
        {rank_html}
    </div>
    '''
    return render_page("🦷 转介绍管理系统", content, "home")

@app.route('/referrers')
def referrers():
    conn = get_db()
    refs = conn.execute("SELECT * FROM referrers ORDER BY converted DESC").fetchall()
    conn.close()
    
    html = '''<a href="/" class="btn btn-primary" style="margin-bottom:10px">🏠 返回主页</a>
    <a href="/referrer/add" class="btn btn-success">➕ 新增介绍人</a><div class="card">'''
    if refs:
        for r in refs:
            gender = r["gender"] if "gender" in r.keys() else ""
            birthday = r["birthday"] if "birthday" in r.keys() else ""
            address = r["address"] if "address" in r.keys() else ""
            workplace = r["workplace"] if "workplace" in r.keys() else ""
            commission = r["commission_rate"] if "commission_rate" in r.keys() and r["commission_rate"] else 10
            pending = r["pending_rewards"] if "pending_rewards" in r.keys() else 0
            
            pending_tag = f'<span class="badge badge-warning reward-pending">待发¥{pending:.0f}</span>' if pending > 0 else ''
            
            html += f'''<div class="list-item">
                <div class="list-avatar">{r["name"][0]}</div>
                <div class="list-info">
                    <div class="list-name">{r["name"]} <span style="font-size:12px;color:#64748B">{gender}</span> {pending_tag}</div>
                    <div class="list-detail">📱{r["phone"] or "-"} · {r["type"]} · 提成{commission:.0f}%</div>
                    <div class="list-detail">🎂{birthday or "-"} · 🏠{address or "-"}</div>
                    <div class="list-detail">介绍{r["referrals"]}人·成交{r["converted"]}人·已发¥{r["rewards"]:.0f}</div>
                    <div style="margin-top:8px">
                        <a href="/referrer/edit/{r["id"]}" class="btn btn-primary btn-sm">编辑</a>
                        <a href="/referrer/del/{r["id"]}" class="btn btn-danger btn-sm" onclick="return confirm('确定删除?')">删除</a>
                    </div>
                </div>
            </div>'''
    else:
        html += '<div class="empty">暂无介绍人</div>'
    html += '</div>'
    return render_page("👥 介绍人管理", html, "referrers")

@app.route('/referrer/add', methods=['GET', 'POST'])
def add_referrer():
    default_rate = get_setting('commission_rate', DEFAULT_COMMISSION_RATE)
    if request.method == 'POST':
        conn = get_db()
        conn.execute("""INSERT INTO referrers (name, phone, type, gender, birthday, address, workplace, commission_rate, notes) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (request.form['name'], request.form.get('phone', ''), request.form.get('type', '老患者'),
                     request.form.get('gender', ''), request.form.get('birthday', ''),
                     request.form.get('address', ''), request.form.get('workplace', ''),
                     float(request.form.get('commission_rate', default_rate
