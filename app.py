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
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 404 or "找不到该页面" in res.text or "not find that page" in res.text:
                return "BANNED", "账号不存在或已被封禁", "未知", "未知"
            if res.status_code != 200:
                return "ACTIVE", "正常存活", "未验证", "未知"

            soup = BeautifulSoup(res.text, 'html.parser')
            pt = soup.get_text()

            # 手机验证检测
            ver = "未验证"
            if "已验证" in pt or "已驗證" in pt or "Verified" in pt or "已认证" in pt:
                ver = "已验证"

            # 增强型加入时间扫描
            joined = "未知"
            for tag in soup.find_all(['div', 'span', 'p']):
                txt = tag.get_text(strip=True)
                if txt in ["已加入", "Joined", "加入于"]:
                    p = tag.parent
                    if p:
                        chs = [c.get_text(strip=True) for c in p.find_all(recursive=False)]
                        for ct in chs:
                            if ct and ct not in ["已加入", "Joined", "加入于"] and len(ct) < 20:
                                joined = ct
                                break
                    if joined != "未知":
                        break

            if joined == "未知":
                for tag in soup.find_all(['div', 'span', 'p']):
                    ts = tag.get_text(strip=True)
                    tl = ts.lower()
                    if ("yesterday" in tl or "ago" in tl or "天前" in ts or "个月前" in ts or "年前" in ts or "小时前" in ts) and len(ts) < 15:
                        if "评价" not in ts and "粉丝" not in ts and "商品" not in ts:
                            joined = ts
                            break

            return "ACTIVE", "正常存活", ver, joined
        except Exception:
            return "ACTIVE", "正常存活", "未验证", "未知"

    if st.button("开始批量检测并存档", type="primary"):
        if not usernames:
            st.warning("请先输入或上传至少一个用户名！")
        else:
            st.info(f"已加载 {len(usernames)} 个账号，正在通过云端执行高效检测...")
            bar = st.progress(0)
            st_text = st.empty()
            
            s_list = []
            f_list = []
            
            for i, u in enumerate(usernames):
                st_text.text(f"正在检测 [{i+1}/{len(usernames)}]: {u}")
                status, desc, ver, joined = check_user_cloud(u)
                
                if status == "ACTIVE":
                    s_list.append({"用户名": u, "状态": desc, "手机验证": ver, "加入时间": joined})
                else:
                    f_list.append({"用户名": u, "状态": desc})
                
                bar.progress((i + 1) / len(usernames))
                if i < len(usernames) - 1:
                    time.sleep(random.uniform(min_delay, max_delay))
                    
            st_text.text("检测完毕，已写入历史数据库！")
            save_batch_history(len(usernames), len(s_list), len(f_list), s_list, f_list)
            
            st.markdown("---")
            st.subheader("本次检测统计结果")
            c1, c2, c3 = st.columns(3)
            c1.metric("总检测数", len(usernames))
            c2.metric("成功存活", len(s_list))
            c3.metric("失败/封禁", len(f_list))
            
            for item in s_list:
                profile_url = f"https://www.carousell.com.hk/u/{item['用户名']}/"
                st.markdown(f"✔ **[{item['用户名']}]({profile_url})** -> 正常存活 | 手机: {item['手机验证']} | 加入时间: {item['加入时间']}")
            for item in f_list:
                st.error(f"{item['用户名']} -> {item['状态']}")

with tab_history:
    st.subheader("历史检测记录")
    rows = get_all_history()
    if not rows:
        st.info("暂无历史记录。")
    else:
        for row in rows:
            hid, timestamp, total, success, fail, data_json = row
            with st.expander(f"检测时间: {timestamp} | 总数: {total}"):
                data = json.loads(data_json)
                for item in data.get("success_list", []):
                    profile_url = f"https://www.carousell.com.hk/u/{item['用户名']}/"
                    st.markdown(f" • **[{item['用户名']}]({profile_url})** -> {item['状态']} | 手机: {item['手机验证']} | 加入时间: {item['加入时间']}")
