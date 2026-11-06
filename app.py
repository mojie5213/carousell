import time
import random
import sqlite3
import json
from datetime import datetime, timezone, timedelta
import requests
import streamlit as st

# 页面配置
st.set_page_config(page_title="Carousell 账号检测工具", page_icon="🔍", layout="centered")

# 获取北京时间（UTC+8）
def get_beijing_time():
    utc_now = datetime.now(timezone.utc)
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d %H:%M:%S")

# --- 数据库初始化（本地历史持久化） ---
def init_db():
    conn = sqlite3.connect("carousell_history.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            total INTEGER,
            success INTEGER,
            fail INTEGER,
            data_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# 保存批次历史到数据库
def save_batch_history(total, success, fail, success_list, fail_list):
    conn = sqlite3.connect("carousell_history.db", check_same_thread=False)
    c = conn.cursor()
    timestamp = get_beijing_time()
    payload = {
        "success_list": success_list,
        "fail_list": fail_list
    }
    c.execute("INSERT INTO history (timestamp, total, success, fail, data_json) VALUES (?, ?, ?, ?, ?)",
              (timestamp, total, success, fail, json.dumps(payload, ensure_ascii=False)))
    conn.commit()
    conn.close()

# 获取所有历史记录
def get_all_history():
    conn = sqlite3.connect("carousell_history.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, total, success, fail, data_json FROM history ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

st.title("🔍 Carousell 账号存活状态批量检测工具")
st.markdown("支持**API 接口直连**、北京时间存档、延时控制、手机验证状态与本地历史记录持久化。")

# 侧边栏配置参数
st.sidebar.header("⚙️ 参数设置")
min_delay = st.sidebar.slider("最小延时 (秒)", 0.5, 2.0, 1.0)
max_delay = st.sidebar.slider("最大延时 (秒)", 1.5, 3.0, 2.0)

# --- 主界面顶部多标签页切换 ---
tab_detect, tab_history = st.tabs(["🚀 批量检测工具", "📜 历史检测记录查询"])

with tab_detect:
    # 输入方式：文本框直接输入 或 文件上传
    st.markdown("---")
    input_method = st.radio("选择账号输入方式", ["文本框输入", "上传 txt 文件"])

    usernames = []
    if input_method == "文本框输入":
        raw_text = st.text_area("请输入用户名（每行一个）", placeholder="freesa2b3\nbra0bc9c\nmoon.f5402e")
        if raw_text:
            usernames = [line.strip() for line in raw_text.split("\n") if line.strip()]
    else:
        uploaded_file = st.file_uploader("上传包含用户名的文本文件", type=["txt"])
        if uploaded_file:
            content = uploaded_file.getvalue().decode("utf-8")
            usernames = [line.strip() for line in content.split("\n") if line.strip()]

    # 核心检测逻辑（使用 Carousell 官方 API 接口）
    def check_user_meta(username):
        api_url = f"https://www.carousell.com.hk/api/profiles/v1/users/by-username/{username}/"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Referer": f"https://www.carousell.com.hk/u/{username}/",
            "Accept": "application/json",
            "Accept-Language": "zh-HK,zh;q=0.9"
        }
        
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 404 or response.status_code == 410:
                return "BANNED_OR_NOT_EXIST", "账号不存在或已被封禁", "未知", "未知"
                
            if response.status_code != 200:
