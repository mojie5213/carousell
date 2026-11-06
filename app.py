import time
import random
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import requests
import streamlit as st

st.set_page_config(page_title="Carousell 账号精准检测工具", page_icon="🔍", layout="centered")

def get_beijing_time():
    utc_now = datetime.now(timezone.utc)
    return (utc_now + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

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

def save_batch_history(total, success, fail, success_list, fail_list):
    conn = sqlite3.connect("carousell_history.db", check_same_thread=False)
    c = conn.cursor()
    timestamp = get_beijing_time()
    payload = {"success_list": success_list, "fail_list": fail_list}
    c.execute("INSERT INTO history (timestamp, total, success, fail, data_json) VALUES (?, ?, ?, ?, ?)",
              (timestamp, total, success, fail, json.dumps(payload, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_all_history():
    conn = sqlite3.connect("carousell_history.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, total, success, fail, data_json FROM history ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

st.title("🔍 Carousell 账号精准检测工具")
st.markdown("支持**云端 GitHub 部署**、北京时间存档与历史持久化。")

st.sidebar.header("参数设置")
min_delay = st.sidebar.slider("最小延时 (秒)", 0.5, 2.0, 1.0)
max_delay = st.sidebar.slider("最大延时 (秒)", 1.5, 3.0, 2.0)

tab_detect, tab_history = st.tabs(["批量检测工具", "历史检测记录查询"])

with tab_detect:
    st.markdown("---")
    input_method = st.radio("选择账号输入方式", ["文本框输入", "上传 txt 文件"])

    usernames = []
    if input_method == "文本框输入":
        raw_text = st.text_area("请输入用户名（每行一个）", placeholder="odddog.22182\nfreed2b3")
        if raw_text:
            for line in raw_text.split("\n"):
                c_line = line.strip()
                if c_line:
                    usernames.append(c_line)
    else:
        uploaded_file = st.file_uploader("上传包含用户名的文本文件", type=["txt"])
        if uploaded_file:
            content = uploaded_file.getvalue().decode("utf-8")
            for line in content.split("\n"):
                c_line = line.strip()
                if c_line:
                    usernames.append(c_line)

    def check_user_cloud(username):
        url = f"https://www.carousell.com.hk/u/{username}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "zh-HK,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 404 or "找不到该页面" in res.text or "not find that page" in res.text:
                return "BANNED", "账号不存在或已被封禁", "未知", "未知"
            if res.status_code != 200:
                return "ACTIVE", "正常存活", "未验证", "未知"

            soup = BeautifulSoup(res.text, 'html.parser')
            pt = soup.get_text()

            ver = "已验证" if ("已验证" in
