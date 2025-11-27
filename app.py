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
                     float(request.form.get('commission_rate', default_rate) or default_rate),
                     request.form.get('notes', '')))
        conn.commit()
        conn.close()
        return redirect('/referrers')
    
    html = f'''<div class="card">
        <div class="card-title">👥 新增介绍人</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">姓名 *</label><input name="name" class="form-input" required></div>
            <div class="form-group"><label class="form-label">性别</label>
                <select name="gender" class="form-select">
                    <option value="">请选择</option><option>男</option><option>女</option>
                </select>
            </div>
            <div class="form-group"><label class="form-label">电话</label><input name="phone" class="form-input" type="tel"></div>
            <div class="form-group"><label class="form-label">生日</label><input name="birthday" class="form-input" type="date"></div>
            <div class="form-group"><label class="form-label">地址</label><input name="address" class="form-input" placeholder="家庭住址"></div>
            <div class="form-group"><label class="form-label">工作单位</label><input name="workplace" class="form-input"></div>
            <div class="form-group"><label class="form-label">类型</label>
                <select name="type" class="form-select">
                    <option>老患者</option><option>员工推荐</option><option>合作商家</option><option>朋友介绍</option><option>其他</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">提成比例 (%)</label>
                <input name="commission_rate" class="form-input" type="number" step="0.1" value="{default_rate}">
                <div class="form-hint">患者成交后，按消费金额的此比例计算奖励</div>
            </div>
            <div class="form-group"><label class="form-label">备注</label><textarea name="notes" class="form-input" rows="2"></textarea></div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/referrers" class="btn btn-gray">取消</a>
        </form>
    </div>'''
    return render_page("新增介绍人", html, "referrers")

@app.route('/referrer/edit/<int:id>', methods=['GET', 'POST'])
def edit_referrer(id):
    conn = get_db()
    if request.method == 'POST':
        conn.execute("""UPDATE referrers SET name=?, phone=?, type=?, gender=?, birthday=?, address=?, workplace=?, commission_rate=?, notes=? 
                       WHERE id=?""",
                    (request.form['name'], request.form.get('phone', ''), request.form.get('type', '老患者'),
                     request.form.get('gender', ''), request.form.get('birthday', ''),
                     request.form.get('address', ''), request.form.get('workplace', ''),
                     float(request.form.get('commission_rate', 10) or 10),
                     request.form.get('notes', ''), id))
        conn.commit()
        conn.close()
        return redirect('/referrers')
    
    r = conn.execute("SELECT * FROM referrers WHERE id = ?", (id,)).fetchone()
    conn.close()
    
    if not r:
        return redirect('/referrers')
    
    gender = r["gender"] if "gender" in r.keys() else ""
    birthday = r["birthday"] if "birthday" in r.keys() else ""
    address = r["address"] if "address" in r.keys() else ""
    workplace = r["workplace"] if "workplace" in r.keys() else ""
    commission = r["commission_rate"] if "commission_rate" in r.keys() and r["commission_rate"] else 10
    notes = r["notes"] if "notes" in r.keys() else ""
    
    html = f'''<div class="card">
        <div class="card-title">👥 编辑介绍人</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">姓名 *</label><input name="name" class="form-input" value="{r["name"]}" required></div>
            <div class="form-group"><label class="form-label">性别</label>
                <select name="gender" class="form-select">
                    <option value="">请选择</option>
                    <option {"selected" if gender == "男" else ""}>男</option>
                    <option {"selected" if gender == "女" else ""}>女</option>
                </select>
            </div>
            <div class="form-group"><label class="form-label">电话</label><input name="phone" class="form-input" type="tel" value="{r["phone"] or ""}"></div>
            <div class="form-group"><label class="form-label">生日</label><input name="birthday" class="form-input" type="date" value="{birthday}"></div>
            <div class="form-group"><label class="form-label">地址</label><input name="address" class="form-input" value="{address}"></div>
            <div class="form-group"><label class="form-label">工作单位</label><input name="workplace" class="form-input" value="{workplace}"></div>
            <div class="form-group"><label class="form-label">类型</label>
                <select name="type" class="form-select">
                    <option {"selected" if r["type"] == "老患者" else ""}>老患者</option>
                    <option {"selected" if r["type"] == "员工推荐" else ""}>员工推荐</option>
                    <option {"selected" if r["type"] == "合作商家" else ""}>合作商家</option>
                    <option {"selected" if r["type"] == "朋友介绍" else ""}>朋友介绍</option>
                    <option {"selected" if r["type"] == "其他" else ""}>其他</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">提成比例 (%)</label>
                <input name="commission_rate" class="form-input" type="number" step="0.1" value="{commission}">
            </div>
            <div class="form-group"><label class="form-label">备注</label><textarea name="notes" class="form-input" rows="2">{notes}</textarea></div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/referrers" class="btn btn-gray">取消</a>
        </form>
    </div>'''
    return render_page("编辑介绍人", html, "referrers")

@app.route('/referrer/del/<int:id>')
def del_referrer(id):
    conn = get_db()
    conn.execute("DELETE FROM referrers WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/referrers')

@app.route('/patients')
def patients():
    conn = get_db()
    pats = conn.execute("""SELECT p.*, r.name as ref_name, r.commission_rate FROM patients p 
                          LEFT JOIN referrers r ON p.referrer_id = r.id 
                          ORDER BY p.created_at DESC""").fetchall()
    
    # 获取所有奖励记录，用于显示奖励类型
    rewards_dict = {}
    rewards_data = conn.execute("SELECT patient_id, type, amount FROM rewards WHERE patient_id IS NOT NULL").fetchall()
    for rw in rewards_data:
        rewards_dict[rw['patient_id']] = {'type': rw['type'], 'amount': rw['amount']}
    
    conn.close()
    
    html = '''<a href="/" class="btn btn-primary" style="margin-bottom:10px">🏠 返回主页</a>
    <a href="/patient/add" class="btn btn-success">➕ 新增患者</a><div class="card">'''
    if pats:
        for p in pats:
            status = "已成交" if p["is_converted"] else "待跟进"
            badge_class = "badge-success" if p["is_converted"] else "badge-warning"
            
            reward_status = p["reward_status"] if "reward_status" in p.keys() else "待发放"
            reward_amount = p["reward_amount"] if "reward_amount" in p.keys() else 0
            
            reward_tag = ""
            reward_detail = ""
            if p["is_converted"] and p["referrer_id"]:
                if reward_status == "已发放":
                    # 获取奖励类型
                    if p["id"] in rewards_dict:
                        rw = rewards_dict[p["id"]]
                        reward_type = rw['type']
                        reward_amt = rw['amount']
                        # 根据类型选择图标
                        if "现金" in reward_type:
                            icon = "💵"
                        elif "红包" in reward_type:
                            icon = "🧧"
                        elif "代金券" in reward_type:
                            icon = "🎫"
                        elif "实物" in reward_type or "礼品" in reward_type or "产品" in reward_type:
                            icon = "🎁"
                        elif "服务" in reward_type:
                            icon = "💆"
                        elif "积分" in reward_type:
                            icon = "⭐"
                        else:
                            icon = "✅"
                        reward_tag = f'<span class="badge badge-success">{icon} ¥{reward_amt:.0f}</span>'
                        reward_detail = f'<div class="list-detail" style="color:#059669">✅ 已发: {reward_type}</div>'
                    else:
                        reward_tag = f'<span class="badge badge-success">已发¥{reward_amount:.0f}</span>'
                else:
                    reward_tag = f'<span class="badge badge-warning reward-pending">待发¥{reward_amount:.0f}</span>'
            
            html += f'''<div class="list-item">
                <div class="list-avatar" style="background:linear-gradient(135deg,#10B981,#059669)">{p["name"][0]}</div>
                <div class="list-info">
                    <div class="list-name">{p["name"]} <span class="badge {badge_class}">{status}</span> {reward_tag}</div>
                    <div class="list-detail">介绍人: {p["ref_name"] or "无"} · {p["treatment"] or "-"}</div>
                    <div class="list-detail">消费: ¥{p["amount"]:.0f}</div>
                    {reward_detail}
                    <div style="margin-top:8px">
                        <a href="/patient/edit/{p["id"]}" class="btn btn-primary btn-sm">编辑</a>
                        <a href="/patient/del/{p["id"]}" class="btn btn-danger btn-sm" onclick="return confirm('确定删除?')">删除</a>
                    </div>
                </div>
            </div>'''
    else:
        html += '<div class="empty">暂无患者</div>'
    html += '</div>'
    return render_page("🧑‍⚕️ 患者管理", html, "patients")

@app.route('/patient/add', methods=['GET', 'POST'])
def add_patient():
    conn = get_db()
    if request.method == 'POST':
        ref_id = request.form.get('referrer_id') or None
        converted = 1 if request.form.get('is_converted') else 0
        amount = float(request.form.get('amount', 0) or 0)
        
        # 自动计算奖励金额
        reward_amount = 0
        if converted and ref_id:
            reward_amount = calculate_reward(amount, int(ref_id))
        
        conn.execute("""INSERT INTO patients (name, phone, referrer_id, treatment, amount, is_converted, reward_amount, reward_status, referral_date) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (request.form['name'], request.form.get('phone', ''), ref_id,
                     request.form.get('treatment', ''), amount, converted, reward_amount,
                     '待发放' if (converted and ref_id) else '',
                     datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        if ref_id:
            update_referrer_stats(int(ref_id))
        conn.close()
        return redirect('/patients')
    
    refs = conn.execute("SELECT id, name, commission_rate FROM referrers ORDER BY name").fetchall()
    conn.close()
    
    options = '<option value="">请选择介绍人</option>' + ''.join([f'<option value="{r["id"]}" data-rate="{r["commission_rate"] or 10}">{r["name"]} ({r["commission_rate"] or 10}%)</option>' for r in refs])
    html = f'''<div class="card">
        <div class="card-title">🧑‍⚕️ 新增患者</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">姓名 *</label><input name="name" class="form-input" required></div>
            <div class="form-group"><label class="form-label">电话</label><input name="phone" class="form-input"></div>
            <div class="form-group"><label class="form-label">介绍人</label><select name="referrer_id" class="form-select" id="referrer_select">{options}</select></div>
            <div class="form-group"><label class="form-label">治疗项目</label><input name="treatment" class="form-input"></div>
            <div class="form-group"><label class="form-label">消费金额</label><input name="amount" type="number" class="form-input" value="0" id="amount_input"></div>
            <div class="form-group"><label><input type="checkbox" name="is_converted" value="1" id="converted_check"> 已成交</label></div>
            <div id="reward_preview" style="display:none;padding:10px;background:#FEF3C7;border-radius:10px;margin-bottom:15px">
                <span>💰 预计奖励: <strong id="reward_amount">¥0</strong></span>
            </div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/patients" class="btn btn-gray">取消</a>
        </form>
    </div>
    <script>
    function updateReward() {{
        var ref = document.getElementById('referrer_select');
        var amount = parseFloat(document.getElementById('amount_input').value) || 0;
        var converted = document.getElementById('converted_check').checked;
        var preview = document.getElementById('reward_preview');
        var rewardEl = document.getElementById('reward_amount');
        
        if (converted && ref.value && amount > 0) {{
            var rate = parseFloat(ref.options[ref.selectedIndex].dataset.rate) || 10;
            var reward = (amount * rate / 100).toFixed(0);
            rewardEl.textContent = '¥' + reward;
            preview.style.display = 'block';
        }} else {{
            preview.style.display = 'none';
        }}
    }}
    document.getElementById('referrer_select').addEventListener('change', updateReward);
    document.getElementById('amount_input').addEventListener('input', updateReward);
    document.getElementById('converted_check').addEventListener('change', updateReward);
    </script>'''
    return render_page("新增患者", html, "patients")

@app.route('/patient/edit/<int:id>', methods=['GET', 'POST'])
def edit_patient(id):
    conn = get_db()
    if request.method == 'POST':
        ref_id = request.form.get('referrer_id') or None
        converted = 1 if request.form.get('is_converted') else 0
        amount = float(request.form.get('amount', 0) or 0)
        
        # 获取原患者信息
        old_p = conn.execute("SELECT * FROM patients WHERE id = ?", (id,)).fetchone()
        old_ref_id = old_p['referrer_id'] if old_p else None
        
        # 自动计算奖励金额
        reward_amount = 0
        reward_status = ''
        if converted and ref_id:
            reward_amount = calculate_reward(amount, int(ref_id))
            # 保持原状态或设为待发放
            old_status = old_p['reward_status'] if old_p and 'reward_status' in old_p.keys() else ''
            reward_status = old_status if old_status else '待发放'
        
        conn.execute("""UPDATE patients SET name=?, phone=?, referrer_id=?, treatment=?, amount=?, is_converted=?, reward_amount=?, reward_status=? 
                       WHERE id=?""",
                    (request.form['name'], request.form.get('phone', ''), ref_id,
                     request.form.get('treatment', ''), amount, converted, reward_amount, reward_status, id))
        conn.commit()
        
        # 更新相关介绍人统计
        if ref_id:
            update_referrer_stats(int(ref_id))
        if old_ref_id and old_ref_id != ref_id:
            update_referrer_stats(int(old_ref_id))
        
        conn.close()
        return redirect('/patients')
    
    p = conn.execute("SELECT * FROM patients WHERE id = ?", (id,)).fetchone()
    refs = conn.execute("SELECT id, name, commission_rate FROM referrers ORDER BY name").fetchall()
    conn.close()
    
    if not p:
        return redirect('/patients')
    
    options = '<option value="">请选择介绍人</option>' + ''.join([
        f'<option value="{r["id"]}" {"selected" if p["referrer_id"] == r["id"] else ""} data-rate="{r["commission_rate"] or 10}">{r["name"]} ({r["commission_rate"] or 10}%)</option>' 
        for r in refs
    ])
    
    html = f'''<div class="card">
        <div class="card-title">🧑‍⚕️ 编辑患者</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">姓名 *</label><input name="name" class="form-input" value="{p["name"]}" required></div>
            <div class="form-group"><label class="form-label">电话</label><input name="phone" class="form-input" value="{p["phone"] or ""}"></div>
            <div class="form-group"><label class="form-label">介绍人</label><select name="referrer_id" class="form-select">{options}</select></div>
            <div class="form-group"><label class="form-label">治疗项目</label><input name="treatment" class="form-input" value="{p["treatment"] or ""}"></div>
            <div class="form-group"><label class="form-label">消费金额</label><input name="amount" type="number" class="form-input" value="{p["amount"]}"></div>
            <div class="form-group"><label><input type="checkbox" name="is_converted" value="1" {"checked" if p["is_converted"] else ""}> 已成交</label></div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/patients" class="btn btn-gray">取消</a>
        </form>
    </div>'''
    return render_page("编辑患者", html, "patients")

@app.route('/patient/del/<int:id>')
def del_patient(id):
    conn = get_db()
    p = conn.execute("SELECT referrer_id FROM patients WHERE id = ?", (id,)).fetchone()
    ref_id = p["referrer_id"] if p else None
    conn.execute("DELETE FROM patients WHERE id = ?", (id,))
    conn.commit()
    if ref_id:
        update_referrer_stats(ref_id)
    conn.close()
    return redirect('/patients')

@app.route('/pending-rewards')
def pending_rewards():
    conn = get_db()
    pats = conn.execute("""SELECT p.*, r.name as ref_name FROM patients p 
                          LEFT JOIN referrers r ON p.referrer_id = r.id 
                          WHERE p.is_converted = 1 AND p.reward_status = '待发放' AND p.referrer_id IS NOT NULL
                          ORDER BY p.created_at DESC""").fetchall()
    conn.close()
    
    html = '''<a href="/" class="btn btn-primary" style="margin-bottom:10px">🏠 返回主页</a>'''
    
    if pats:
        total = sum(p['reward_amount'] for p in pats if 'reward_amount' in p.keys())
        html += f'''<div class="alert alert-warning">
            共 <strong>{len(pats)}</strong> 笔待发奖励，合计 <strong>¥{total:.0f}</strong>
        </div><div class="card">'''
        
        for p in pats:
            reward_amount = p["reward_amount"] if "reward_amount" in p.keys() else 0
            html += f'''<div class="list-item">
                <div class="list-avatar" style="background:linear-gradient(135deg,#F59E0B,#D97706)">💰</div>
                <div class="list-info">
                    <div class="list-name">奖励 {p["ref_name"]} <span class="badge badge-warning">¥{reward_amount:.0f}</span></div>
                    <div class="list-detail">患者: {p["name"]} · 消费: ¥{p["amount"]:.0f}</div>
                    <div class="list-detail">项目: {p["treatment"] or "-"}</div>
                    <div style="margin-top:8px">
                        <a href="/mark-rewarded/{p["id"]}" class="btn btn-success btn-sm">🎁 发放奖励</a>
                    </div>
                </div>
            </div>'''
        html += '</div>'
    else:
        html += '<div class="card"><div class="empty">🎉 暂无待发奖励</div></div>'
    
    return render_page("💰 待发奖励", html, "pending")

@app.route('/mark-rewarded/<int:patient_id>', methods=['GET', 'POST'])
def mark_rewarded(patient_id):
    conn = get_db()
    p = conn.execute("""SELECT p.*, r.name as ref_name FROM patients p 
                       LEFT JOIN referrers r ON p.referrer_id = r.id 
                       WHERE p.id = ?""", (patient_id,)).fetchone()
    
    if not p:
        conn.close()
        return redirect('/pending-rewards')
    
    if request.method == 'POST':
        reward_type = request.form.get('reward_type', '现金')
        reward_amount = float(request.form.get('reward_amount', 0) or 0)
        gift_id = request.form.get('gift_id', '')
        gift_name = request.form.get('gift_name', '')
        notes = request.form.get('notes', '')
        
        # 如果选择了礼品库中的礼品
        if gift_id:
            gift = conn.execute("SELECT * FROM gift_items WHERE id = ?", (gift_id,)).fetchone()
            if gift:
                gift_qty = int(request.form.get('gift_qty', 1) or 1)
                unit_value = gift['value'] if 'value' in gift.keys() and gift['value'] else gift['cost']
                
                # 如果数量大于1，显示数量
                if gift_qty > 1:
                    reward_type = f"{gift['category']}({gift['name']}×{gift_qty})"
                else:
                    reward_type = f"{gift['category']}({gift['name']})"
                
                # 使用赠送价值×数量作为奖励金额
                reward_amount = unit_value * gift_qty
                
                # 减少库存
                if gift['stock'] > 0:
                    new_stock = max(0, gift['stock'] - gift_qty)
                    conn.execute("UPDATE gift_items SET stock = ? WHERE id = ?", (new_stock, gift_id))
        elif reward_type != '现金' and gift_name:
            reward_type = f"{reward_type}({gift_name})"
        
        # 更新状态
        conn.execute("UPDATE patients SET reward_status = '已发放' WHERE id = ?", (patient_id,))
        # 添加奖励记录
        conn.execute("INSERT INTO rewards (referrer_id, patient_id, type, amount, date, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (p["referrer_id"], patient_id, reward_type, reward_amount, datetime.now().strftime('%Y-%m-%d'), notes))
        conn.commit()
        if p["referrer_id"]:
            update_referrer_stats(p["referrer_id"])
        conn.close()
        return redirect('/pending-rewards')
    
    reward_amount = p["reward_amount"] if "reward_amount" in p.keys() else 0
    
    # 获取礼品库
    gifts = conn.execute("SELECT * FROM gift_items WHERE is_active = 1 ORDER BY category, name").fetchall()
    conn.close()
    
    # 生成礼品选项
    gift_options = '<option value="">-- 从礼品库选择 --</option>'
    current_cat = ""
    for g in gifts:
        if g['category'] != current_cat:
            if current_cat:
                gift_options += '</optgroup>'
            gift_options += f'<optgroup label="{g["category"]}">'
            current_cat = g['category']
        stock_info = f" [库存:{g['stock']}]" if g['stock'] > 0 else " [不限]"
        value = g["value"] if "value" in g.keys() and g["value"] else g["cost"]
        # 显示赠送价值，data-cost存成本价，data-value存赠送价，data-stock存库存
        gift_options += f'<option value="{g["id"]}" data-cost="{g["cost"]}" data-value="{value}" data-stock="{g["stock"]}">{g["name"]} ¥{value:.0f}/个{stock_info}</option>'
    if current_cat:
        gift_options += '</optgroup>'
    
    html = f'''<a href="/pending-rewards" class="btn btn-gray" style="margin-bottom:10px">← 返回待发奖励</a>
    <div class="card">
        <div class="card-title">🎁 发放奖励</div>
        <div style="background:#F8FAFC;padding:12px;border-radius:10px;margin-bottom:15px">
            <div><strong>介绍人：</strong>{p["ref_name"]}</div>
            <div><strong>患者：</strong>{p["name"]}</div>
            <div><strong>消费金额：</strong>¥{p["amount"]:.0f}</div>
            <div><strong>建议奖励：</strong>¥{reward_amount:.0f}</div>
        </div>
        <form method="POST">
            <div class="form-group">
                <label class="form-label">奖励方式 *</label>
                <select name="reward_type" class="form-select" id="reward_type" onchange="toggleInputs()">
                    <option value="现金">💵 现金</option>
                    <option value="微信红包">🧧 微信红包</option>
                    <option value="礼品库">🎁 从礼品库选择</option>
                    <option value="自定义礼品">📦 自定义实物</option>
                    <option value="服务赠送">💆 服务赠送</option>
                    <option value="代金券">🎫 代金券</option>
                    <option value="积分">⭐ 积分</option>
                </select>
            </div>
            <div class="form-group" id="gift_select_div" style="display:none">
                <label class="form-label">选择礼品</label>
                <select name="gift_id" class="form-select" id="gift_select" onchange="updateGiftCost()">
                    {gift_options}
                </select>
            </div>
            <div class="form-group" id="gift_qty_div" style="display:none">
                <label class="form-label">数量</label>
                <div style="display:flex;align-items:center;gap:10px">
                    <button type="button" onclick="changeQty(-1)" style="width:40px;height:40px;border:1px solid #D1D5DB;border-radius:10px;font-size:20px;background:white">-</button>
                    <input name="gift_qty" type="number" class="form-input" id="gift_qty" value="1" min="1" style="width:80px;text-align:center" onchange="updateGiftCost()">
                    <button type="button" onclick="changeQty(1)" style="width:40px;height:40px;border:1px solid #D1D5DB;border-radius:10px;font-size:20px;background:white">+</button>
                    <span id="stock_info" style="color:#64748B;font-size:12px"></span>
                </div>
                <div class="form-hint">选择后自动计算总价值，并扣减库存</div>
            </div>
            <div class="form-group" id="gift_input" style="display:none">
                <label class="form-label">礼品/服务名称</label>
                <input name="gift_name" class="form-input" placeholder="如：电动牙刷、洗牙一次等">
            </div>
            <div class="form-group">
                <label class="form-label">奖励金额/价值 (元)</label>
                <input name="reward_amount" class="form-input" type="number" value="{reward_amount:.0f}" id="reward_amount_input">
            </div>
            <div class="form-group">
                <label class="form-label">备注</label>
                <input name="notes" class="form-input" placeholder="可选">
            </div>
            <button type="submit" class="btn btn-success">✅ 确认发放</button>
            <a href="/pending-rewards" class="btn btn-gray">取消</a>
        </form>
    </div>
    <script>
    function toggleInputs() {{
        var type = document.getElementById('reward_type').value;
        var giftSelect = document.getElementById('gift_select_div');
        var giftQty = document.getElementById('gift_qty_div');
        var giftInput = document.getElementById('gift_input');
        
        giftSelect.style.display = 'none';
        giftQty.style.display = 'none';
        giftInput.style.display = 'none';
        
        if (type === '礼品库') {{
            giftSelect.style.display = 'block';
            giftQty.style.display = 'block';
        }} else if (type === '自定义礼品' || type === '服务赠送') {{
            giftInput.style.display = 'block';
        }}
    }}
    
    function changeQty(delta) {{
        var qtyInput = document.getElementById('gift_qty');
        var newQty = parseInt(qtyInput.value) + delta;
        if (newQty >= 1) {{
            qtyInput.value = newQty;
            updateGiftCost();
        }}
    }}
    
    function updateGiftCost() {{
        var select = document.getElementById('gift_select');
        var option = select.options[select.selectedIndex];
        var qty = parseInt(document.getElementById('gift_qty').value) || 1;
        var stockInfo = document.getElementById('stock_info');
        
        if (option && option.dataset.value) {{
            var unitValue = parseFloat(option.dataset.value);
            var stock = parseInt(option.dataset.stock) || 0;
            
            // 计算总价值
            document.getElementById('reward_amount_input').value = (unitValue * qty).toFixed(0);
            
            // 显示库存信息
            if (stock > 0) {{
                if (qty > stock) {{
                    stockInfo.innerHTML = '<span style="color:#EF4444">⚠️ 库存不足！仅剩' + stock + '个</span>';
                }} else {{
                    stockInfo.textContent = '库存: ' + stock + '个';
                }}
            }} else {{
                stockInfo.textContent = '不限库存';
            }}
        }}
    }}
    </script>'''
    return render_page("发放奖励", html, "pending")

@app.route('/rewards')
def rewards():
    conn = get_db()
    rews = conn.execute("""SELECT rw.*, r.name as ref_name, p.name as pat_name FROM rewards rw 
                          LEFT JOIN referrers r ON rw.referrer_id = r.id 
                          LEFT JOIN patients p ON rw.patient_id = p.id
                          ORDER BY rw.created_at DESC""").fetchall()
    
    # 统计
    total_count = len(rews)
    total_amount = sum(r['amount'] for r in rews)
    conn.close()
    
    html = f'''<a href="/" class="btn btn-primary" style="margin-bottom:10px">🏠 返回主页</a>
    <div class="alert alert-success">共发放 <strong>{total_count}</strong> 次奖励，合计 <strong>¥{total_amount:.0f}</strong></div>
    <div class="card">'''
    if rews:
        for r in rews:
            pat_name = r["pat_name"] if "pat_name" in r.keys() and r["pat_name"] else ""
            notes = r["notes"] if "notes" in r.keys() and r["notes"] else ""
            
            # 根据奖励类型选择图标
            reward_type = r["type"]
            if "现金" in reward_type:
                icon = "💵"
            elif "红包" in reward_type:
                icon = "🧧"
            elif "代金券" in reward_type:
                icon = "🎫"
            elif "实物" in reward_type or "礼品" in reward_type:
                icon = "🎁"
            elif "服务" in reward_type:
                icon = "💆"
            elif "积分" in reward_type:
                icon = "⭐"
            else:
                icon = "✅"
            
            notes_html = f'<div class="list-detail">📝 {notes}</div>' if notes else ''
            
            html += f'''<div class="list-item">
                <div class="list-avatar" style="background:linear-gradient(135deg,#10B981,#059669)">{icon}</div>
                <div class="list-info">
                    <div class="list-name">{r["ref_name"] or "未知"} <span class="badge badge-success">¥{r["amount"]:.0f}</span></div>
                    <div class="list-detail">{reward_type} · {r["date"] or "-"}</div>
                    <div class="list-detail">患者: {pat_name or "-"}</div>
                    {notes_html}
                </div>
            </div>'''
    else:
        html += '<div class="empty">暂无奖励记录</div>'
    html += '</div>'
    return render_page("🎁 奖励记录", html, "rewards")

@app.route('/gift-items')
def gift_items():
    conn = get_db()
    items = conn.execute("SELECT * FROM gift_items ORDER BY category, name").fetchall()
    conn.close()
    
    html = '''<a href="/settings" class="btn btn-gray" style="margin-bottom:10px">← 返回设置</a>
    <a href="/gift-item/add" class="btn btn-success">➕ 添加礼品</a>
    <div class="card">
        <div class="card-title">🎁 礼品库管理</div>
        <div style="font-size:12px;color:#64748B;margin-bottom:10px">成本价：实际采购成本 | 赠送价：对外展示价值</div>'''
    
    if items:
        # 按分类分组
        categories = {}
        for item in items:
            cat = item['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        for cat, cat_items in categories.items():
            html += f'<div style="font-weight:600;margin:15px 0 10px;color:#3B82F6">{cat}</div>'
            for item in cat_items:
                stock_badge = f'<span class="badge badge-info">库存:{item["stock"]}</span>' if item["stock"] > 0 else '<span class="badge badge-danger">无库存</span>'
                status = '' if item["is_active"] else '<span class="badge badge-warning">已停用</span>'
                desc = item["description"] if item["description"] else ""
                value = item["value"] if "value" in item.keys() and item["value"] else item["cost"]
                
                html += f'''<div class="list-item">
                    <div class="list-avatar" style="background:linear-gradient(135deg,#F59E0B,#D97706)">🎁</div>
                    <div class="list-info">
                        <div class="list-name">{item["name"]} {stock_badge} {status}</div>
                        <div class="list-detail">💰 成本: ¥{item["cost"]:.0f} | 🎁 赠送价: ¥{value:.0f}</div>
                        <div class="list-detail">{desc}</div>
                        <div style="margin-top:8px">
                            <a href="/gift-item/edit/{item["id"]}" class="btn btn-primary btn-sm">编辑</a>
                            <a href="/gift-item/del/{item["id"]}" class="btn btn-danger btn-sm" onclick="return confirm('确定删除?')">删除</a>
                        </div>
                    </div>
                </div>'''
    else:
        html += '<div class="empty">暂无礼品，点击上方按钮添加</div>'
    
    html += '</div>'
    return render_page("🎁 礼品库管理", html, "settings")

@app.route('/gift-item/add', methods=['GET', 'POST'])
def add_gift_item():
    if request.method == 'POST':
        conn = get_db()
        cost = float(request.form.get('cost', 0) or 0)
        value = float(request.form.get('value', 0) or 0)
        if value == 0:
            value = cost  # 如果没填赠送价，默认等于成本价
        conn.execute("""INSERT INTO gift_items (name, category, cost, value, stock, description) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (request.form['name'], request.form.get('category', '实物礼品'),
                     cost, value,
                     int(request.form.get('stock', 0) or 0),
                     request.form.get('description', '')))
        conn.commit()
        conn.close()
        return redirect('/gift-items')
    
    html = '''<div class="card">
        <div class="card-title">➕ 添加礼品</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">礼品名称 *</label>
                <input name="name" class="form-input" required placeholder="如：电动牙刷、护理套装">
            </div>
            <div class="form-group"><label class="form-label">分类</label>
                <select name="category" class="form-select">
                    <option>实物礼品</option>
                    <option>服务项目</option>
                    <option>代金券</option>
                    <option>护理产品</option>
                    <option>生活用品</option>
                    <option>其他</option>
                </select>
            </div>
            <div class="form-group"><label class="form-label">💰 成本价 (元)</label>
                <input name="cost" class="form-input" type="number" value="0">
                <div class="form-hint">实际采购/进货成本</div>
            </div>
            <div class="form-group"><label class="form-label">🎁 赠送价值 (元)</label>
                <input name="value" class="form-input" type="number" value="0">
                <div class="form-hint">对外展示的价值/市场价，留空则等于成本价</div>
            </div>
            <div class="form-group"><label class="form-label">库存数量</label>
                <input name="stock" class="form-input" type="number" value="0">
                <div class="form-hint">0表示不限库存</div>
            </div>
            <div class="form-group"><label class="form-label">描述</label>
                <textarea name="description" class="form-input" rows="2" placeholder="礼品详细描述"></textarea>
            </div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/gift-items" class="btn btn-gray">取消</a>
        </form>
    </div>'''
    return render_page("添加礼品", html, "settings")

@app.route('/gift-item/edit/<int:id>', methods=['GET', 'POST'])
def edit_gift_item(id):
    conn = get_db()
    if request.method == 'POST':
        cost = float(request.form.get('cost', 0) or 0)
        value = float(request.form.get('value', 0) or 0)
        if value == 0:
            value = cost
        conn.execute("""UPDATE gift_items SET name=?, category=?, cost=?, value=?, stock=?, description=?, is_active=? 
                       WHERE id=?""",
                    (request.form['name'], request.form.get('category', '实物礼品'),
                     cost, value,
                     int(request.form.get('stock', 0) or 0),
                     request.form.get('description', ''),
                     1 if request.form.get('is_active') else 0, id))
        conn.commit()
        conn.close()
        return redirect('/gift-items')
    
    item = conn.execute("SELECT * FROM gift_items WHERE id = ?", (id,)).fetchone()
    conn.close()
    
    if not item:
        return redirect('/gift-items')
    
    value = item["value"] if "value" in item.keys() and item["value"] else item["cost"]
    
    html = f'''<div class="card">
        <div class="card-title">编辑礼品</div>
        <form method="POST">
            <div class="form-group"><label class="form-label">礼品名称 *</label>
                <input name="name" class="form-input" value="{item["name"]}" required>
            </div>
            <div class="form-group"><label class="form-label">分类</label>
                <select name="category" class="form-select">
                    <option {"selected" if item["category"] == "实物礼品" else ""}>实物礼品</option>
                    <option {"selected" if item["category"] == "服务项目" else ""}>服务项目</option>
                    <option {"selected" if item["category"] == "代金券" else ""}>代金券</option>
                    <option {"selected" if item["category"] == "护理产品" else ""}>护理产品</option>
                    <option {"selected" if item["category"] == "生活用品" else ""}>生活用品</option>
                    <option {"selected" if item["category"] == "其他" else ""}>其他</option>
                </select>
            </div>
            <div class="form-group"><label class="form-label">💰 成本价 (元)</label>
                <input name="cost" class="form-input" type="number" value="{item["cost"]}">
                <div class="form-hint">实际采购/进货成本</div>
            </div>
            <div class="form-group"><label class="form-label">🎁 赠送价值 (元)</label>
                <input name="value" class="form-input" type="number" value="{value}">
                <div class="form-hint">对外展示的价值/市场价</div>
            </div>
            <div class="form-group"><label class="form-label">库存数量</label>
                <input name="stock" class="form-input" type="number" value="{item["stock"]}">
            </div>
            <div class="form-group"><label class="form-label">描述</label>
                <textarea name="description" class="form-input" rows="2">{item["description"] or ""}</textarea>
            </div>
            <div class="form-group">
                <label><input type="checkbox" name="is_active" value="1" {"checked" if item["is_active"] else ""}> 启用此礼品</label>
            </div>
            <button type="submit" class="btn btn-success">💾 保存</button>
            <a href="/gift-items" class="btn btn-gray">取消</a>
        </form>
    </div>'''
    return render_page("编辑礼品", html, "settings")

@app.route('/gift-item/del/<int:id>')
def del_gift_item(id):
    conn = get_db()
    conn.execute("DELETE FROM gift_items WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/gift-items')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        rate = request.form.get('commission_rate', DEFAULT_COMMISSION_RATE)
        set_setting('commission_rate', rate)
        return redirect('/settings?saved=1')
    
    current_rate = get_setting('commission_rate', DEFAULT_COMMISSION_RATE)
    saved = request.args.get('saved')
    
    saved_msg = '<div class="alert alert-success">✅ 设置已保存</div>' if saved else ''
    
    # 获取礼品数量
    conn = get_db()
    gift_count = conn.execute("SELECT COUNT(*) FROM gift_items WHERE is_active = 1").fetchone()[0]
    conn.close()
    
    html = f'''<a href="/" class="btn btn-primary" style="margin-bottom:10px">🏠 返回主页</a>
    {saved_msg}
    <div class="card">
        <div class="card-title">⚙️ 提成设置</div>
        <form method="POST">
            <div class="form-group">
                <label class="form-label">默认提成比例 (%)</label>
                <input name="commission_rate" class="form-input" type="number" step="0.1" value="{current_rate}">
                <div class="form-hint">新增介绍人时的默认提成比例，可为每个介绍人单独设置不同比例</div>
            </div>
            <button type="submit" class="btn btn-success">💾 保存设置</button>
        </form>
    </div>
    <div class="card">
        <div class="card-title">🎁 礼品库管理</div>
        <p style="color:#64748B;margin-bottom:15px">预设奖励礼品，发放时可快速选择</p>
        <a href="/gift-items" class="btn btn-warning">🎁 管理礼品库 ({gift_count}个)</a>
    </div>
    <div class="card">
        <div class="card-title">📖 使用说明</div>
        <div style="font-size:14px;color:#64748B;line-height:1.8">
            <p><strong>1. 提成计算</strong>：患者成交后，系统自动按介绍人的提成比例计算奖励金额</p>
            <p><strong>2. 待发奖励</strong>：患者成交后会自动生成待发奖励提醒</p>
            <p><strong>3. 礼品库</strong>：可预先设置奖励礼品的品类、成本和库存</p>
            <p><strong>4. 发放奖励</strong>：可选择现金或从礼品库选择实物奖励</p>
        </div>
    </div>'''
    return render_page("⚙️ 设置", html, "settings")

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
