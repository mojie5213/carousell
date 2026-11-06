import time
import random
import sqlite3
import json
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
import streamlit as st

# 页面配置
st.set_page_config(page_title="小老弟 - Carousell 账号检测工具", page_icon="🔍", layout="centered")

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

st.title("🔍 小老弟专属 - Carousell 账号存活状态批量检测工具")
st.markdown("支持**完整浏览器指纹模拟**、北京时间存档、延时控制、手机验证状态与本地历史记录持久化。")

# 侧边栏配置参数
st.sidebar.header("⚙️ 参数设置")
min_delay = st.sidebar.slider("最小延时 (秒)", 1.0, 3.0, 1.5)
max_delay = st.sidebar.slider("最大延时 (秒)", 2.5, 5.0, 3.0)

# --- 主界面顶部多标签页切换 ---
tab_detect, tab_history = st.tabs(["🚀 批量检测工具", "📜 历史检测记录查询"])

with tab_detect:
    # 输入方式：文本框直接输入 或 文件上传
    st.markdown("---")
    input_method = st.radio("选择账号输入方式", ["文本框输入", "上传 txt 文件"])

    usernames = []
    if input_method == "文本框输入":
        raw_text = st.text_area("请输入用户名（每行一个）", placeholder="mialuxury_\nfreesa2b3\nmoon.f5402e")
        if raw_text:
            usernames = [line.strip() for line in raw_text.split("\n") if line.strip()]
    else:
        uploaded_file = st.file_uploader("上传包含用户名的文本文件", type=["txt"])
        if uploaded_file:
            content = uploaded_file.getvalue().decode("utf-8")
            usernames = [line.strip() for line in content.split("\n") if line.strip()]

    # 核心检测逻辑（使用 Session 保持 Cookie，完美绕过 403）
    def check_user_meta(username):
        url = f"https://www.carousell.com.hk/u/{username}/"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-HK,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.carousell.com.hk/",
            "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive"
        }
        
        session = requests.Session()
            
        try:
            # 1. 模拟先访问首页，获取合法的 Cloudflare / Carousell Cookie
            session.get("https://www.carousell.com.hk/", headers=headers, timeout=10)
            time.sleep(random.uniform(0.4, 0.8))
            
            # 2. 带着 Cookie 访问真实用户主页
            response = session.get(url, headers=headers, timeout=12, allow_redirects=True)
            
            if response.status_code == 404 or response.status_code == 410:
                return "BANNED_OR_NOT_EXIST", "账号不存在或已被封禁 (404)", "未知", "未知"
                
            if response.status_code != 200:
                return "BANNED_OR_NOT_EXIST", f"账号不存在或已被封禁 (状态码: {response.status_code})", "未知", "未知"
                
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            # 检查页面是否包含明确的封禁或不存在提示
            if "很抱歉，找不到该页面" in page_text or "Sorry, we couldn't find that page" in page_text:
                return "BANNED_OR_NOT_EXIST", "账号不存在或已被封禁", "未知", "未知"

            # 3. 手机验证状态解析
            if any(k in page_text for k in ["未验证", "未驗證", "Unverified"]):
                verification_status = "未验证"
            else:
                verification_status = "已验证"

            # 4. 加入时间解析
            joined_time = "未知"
            joined_element = soup.find(string=lambda t: t and ("已加入" in t or "Joined" in t))
            if joined_element and joined_element.parent:
                parent = joined_element.parent
                full_text = parent.get_text(strip=True)
                val = full_text.replace("已加入", "").replace("Joined", "").strip()
                if val:
                    joined_time = val
                else:
                    prev_sibling = parent.find_previous_sibling()
                    if prev_sibling:
                        joined_time = prev_sibling.get_text(strip=True)

            return "ACTIVE", "正常存活", verification_status, joined_time
                
        except Exception as e:
            return "ERROR", f"请求异常: {e}", "未知", "未知"

    # 开始检测按钮
    if st.button("🚀 开始批量检测并存档", type="primary"):
        if not usernames:
            st.warning("⚠️ 请先输入或上传至少一个用户名！")
        else:
            st.info(f"已加载 {len(usernames)} 个账号，开始检测...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            success_list = []
            fail_list = []
            
            for i, username in enumerate(usernames):
                status_text.text(f"正在检测 [{i+1}/{len(usernames)}]: {username} ...")
                
                status, desc, verification, joined = check_user_meta(username)
                
                if status == "ACTIVE":
                    success_list.append({
                        "用户名": username, 
                        "状态": desc, 
                        "手机验证": verification, 
                        "加入时间": joined
                    })
                else:
                    fail_list.append({
                        "用户名": username, 
                        "状态": desc
                    })
                
                progress_bar.progress((i + 1) / len(usernames))
                
                if i < len(usernames) - 1:
                    time.sleep(random.uniform(min_delay, max_delay))
                    
            status_text.text("🎉 所有账号检测完毕，已自动按北京时间写入历史数据库！")
            
            save_batch_history(len(usernames), len(success_list), len(fail_list), success_list, fail_list)
            
            # --- 数据展示区 ---
            st.markdown("---")
            st.subheader("📊 本次检测统计结果")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("总检测数", len(usernames))
            col2.metric("✅ 成功存活", len(success_list))
            col3.metric("❌ 失败/封禁", len(fail_list))
            
            sub_tab1, sub_tab2 = st.tabs([f"✅ 成功存活 ({len(success_list)})", f"❌ 失败/异常 ({len(fail_list)})"])
            
            with sub_tab1:
                if success_list:
                    for item in success_list:
                        st.success(f"**{item['用户名']}** -> {item['状态']}  |  📱 手机: `{item['手机验证']}`  |  ⏳ 加入时间: `{item['加入时间']}`")
                else:
                    st.info("没有检测到存活的账号。")
                    
            with sub_tab2:
                if fail_list:
                    for item in fail_list:
                        st.error(f"**{item['用户名']}** -> {item['状态']}")
                else:
                    st.info("没有检测到失败或封禁的账号。")
                    
            # 格式化下载文本
            success_lines = [f"{i['用户名']} -> {i['状态']} | 手机: {i['手机验证']} | 加入时间: {i['加入时间']}" for i in success_list]
            fail_lines = [f"{i['用户名']} -> {i['状态']}" for i in fail_list]
            all_results_text = "=== 成功存活账号 ===\n" + "\n".join(success_lines) + "\n\n=== 失败/异常账号 ===\n" + "\n".join(fail_lines)
                                
            st.download_button(
                label="📥 下载本次分类检测结果文件",
                data=all_results_text,
                file_name="carousell_categorized_results.txt",
                mime="text/plain"
            )

with tab_history:
    st.subheader("📜 历史检测记录（北京时间存档）")
    st.markdown("这里保存了你历次检测的所有详细报告。时间已自动校准为北京时间（UTC+8）。")
    
    rows = get_all_history()
    
    if not rows:
        st.info("📭 暂无历史检测记录。请先在左侧的“批量检测工具”标签页中运行一次检测。")
    else:
        for row in rows:
            hid, timestamp, total, success, fail, data_json = row
            with st.expander(f"🕒 检测时间 (北京时间): {timestamp}  |  总数: {total}  |  ✅ 存活: {success}  |  ❌ 异常: {fail}"):
                try:
                    data = json.loads(data_json)
                    s_list = data.get("success_list", [])
                    f_list = data.get("fail_list", [])
                    
                    st.markdown("**✅ 成功存活账号列表:**")
                    if s_list:
                        for item in s_list:
                            st.text(f" • {item['用户名']} -> {item['状态']} | 手机: {item['手机验证']} | 加入时间: {item['加入时间']}")
                    else:
                        st.text("无")
                        
                    st.markdown("**❌ 失败/异常账号列表:**")
                    if f_list:
                        for item in f_list:
                            st.text(f" • {item['用户名']} -> {item['状态']}")
                    else:
                        st.text("无")
                        
                    s_lines = [f"{i['用户名']} -> {i['状态']} | 手机: {i['手机验证']} | 加入时间: {i['加入时间']}" for i in s_list]
                    f_lines = [f"{i['用户名']} -> {i['状态']}" for i in f_list]
                    single_text = f"=== 历史检测报告 (北京时间: {timestamp}) ===\n" + "\n".join(s_lines) + "\n\n=== 失败/异常账号 ===\n" + "\n".join(f_lines)
                                  
                    st.download_button(
                        label=f"📥 重新下载该批次报告 ({timestamp})",
                        data=single_text,
                        file_name=f"carousell_history_{timestamp.replace(':', '_').replace(' ', '_')}.txt",
                        mime="text/plain",
                        key=f"download_history_{hid}"
                    )
                except Exception as e:
                    st.error(f"解析该条历史记录出错: {e}")
