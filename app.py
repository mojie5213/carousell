import time
import random
import sqlite3
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import streamlit as st

# 页面配置
st.set_page_config(page_title="老弟 账号检测工具", page_icon="🔍", layout="centered")

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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

st.title("🔍 老弟账号存活状态批量检测工具（历史存档版）")
st.markdown("支持自动补全代理协议头、手机验证状态、加入时间抓取与**本地历史记录永久持久化**。")

# 侧边栏配置参数
st.sidebar.header("⚙️ 参数设置")
min_delay = st.sidebar.slider("最小延时 (秒)", 1.0, 3.0, 1.5)
max_delay = st.sidebar.slider("最大延时 (秒)", 2.5, 5.0, 3.0)

st.sidebar.markdown("---")
st.sidebar.header("🌐 代理设置")
raw_proxy_input = st.sidebar.text_input(
    "SOCKS5 代理地址", 
    placeholder="直接粘贴原始代理字符串或带 socks5://",
    value=""
)

# 核心函数：自动处理并格式化代理地址
def format_proxy(proxy_str):
    if not proxy_str:
        return None
    proxy_str = proxy_str.strip()
    if not proxy_str.startswith("http://") and not proxy_str.startswith("https://") and not proxy_str.startswith("socks"):
        return f"socks5h://{proxy_str}"
    return proxy_str

# 代理测速与归属地查询
def test_socks5_proxy(proxy_url):
    formatted_proxy = format_proxy(proxy_url)
    if not formatted_proxy:
        return False, "⚠️ 请先输入代理地址！"
    
    proxies = {
        "http": formatted_proxy,
        "https": formatted_proxy,
    }
    try:
        test_url = "http://ip-api.com/json/?lang=zh-CN"
        response = requests.get(test_url, proxies=proxies, timeout=6)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                ip = data.get("query", "未知")
                country = data.get("country", "未知")
                region = data.get("regionName", "未知")
                city = data.get("city", "未知")
                isp = data.get("isp", "未知")
                
                location_info = f"代理有效！\n- 出口 IP: {ip}\n- 归属地: {country} {region} {city}\n- 运营商: {isp}"
                return True, location_info
            else:
                return False, "代理请求成功，但解析 IP 归属地失败。"
        else:
            return False, f"代理响应异常，状态码: {response.status_code}"
            
    except Exception as e:
        return False, f"代理连接失败或超时: {e}"

# 侧边栏代理测试按钮
if st.sidebar.button("🔗 测试当前代理有效性"):
    with st.sidebar.spinner("正在验证 SOCKS5 代理及归属地..."):
        is_valid, msg = test_socks5_proxy(raw_proxy_input)
        if is_valid:
            st.sidebar.success(msg)
        else:
            st.sidebar.error(msg)

# --- 主界面顶部多标签页切换 ---
tab_detect, tab_history = st.tabs(["🚀 批量检测工具", "📜 历史检测记录查询"])

with tab_detect:
    # 输入方式：文本框直接输入 或 文件上传
    st.markdown("---")
    input_method = st.radio("选择账号输入方式", ["文本框输入", "上传 txt 文件"])

    usernames = []
    if input_method == "文本框输入":
        raw_text = st.text_area("请输入用户名（每行一个）", placeholder="my410871\nroya33c101\n145b3f")
        if raw_text:
            usernames = [line.strip() for line in raw_text.split("\n") if line.strip()]
    else:
        uploaded_file = st.file_uploader("上传包含用户名的文本文件", type=["txt"])
        if uploaded_file:
            content = uploaded_file.getvalue().decode("utf-8")
            usernames = [line.strip() for line in content.split("\n") if line.strip()]

    # 核心检测逻辑
    def check_user_meta(username, proxy_url):
        url = f"https://www.carousell.com.hk/u/{username}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        }
        
        formatted_proxy = format_proxy(proxy_url)
        proxies = None
        if formatted_proxy:
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy,
            }
            
        session = requests.Session()
        if proxies:
            session.proxies.update(proxies)
            
        try:
            response = session.get(url, headers=headers, timeout=12, allow_redirects=True)
            
            if response.status_code == 404:
                return "BANNED_OR_NOT_EXIST", "账号不存在 (404)", "未知", "未知"
                
            soup = BeautifulSoup(response.text, 'html.parser')
            og_url = soup.find('meta', property='og:url')
            if og_url and 'content' in og_url.attrs:
                content_url = og_url['content'].lower()
                if username.lower() in content_url:
                    # 1. 手机验证状态解析
                    page_text = soup.get_text()
                    if any(k in page_text for k in ["未验证", "未驗證", "Unverified"]):
                        verification_status = "未验证"
                    else:
                        verification_status = "已验证"

                    # 2. 加入时间解析
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
                    
            return "BANNED_OR_NOT_EXIST", "账号不存在或已被封禁", "未知", "未知"
            
        except Exception as e:
            return "ERROR", f"请求异常或代理中断: {e}", "未知", "未知"

    # 开始检测按钮
    if st.button("🚀 开始批量检测并存档", type="primary"):
        if not usernames:
            st.warning("⚠️ 请先输入或上传至少一个用户名！")
        else:
            if raw_proxy_input:
                is_valid, _ = test_socks5_proxy(raw_proxy_input)
                if not is_valid:
                    st.error("❌ 检测到您填写的 SOCKS5 代理无效或无法连通，请先在侧边栏测试通过后再开始检测！")
                    st.stop()

            st.info(f"已加载 {len(usernames)} 个账号，开始检测...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            success_list = []
            fail_list = []
            
            for i, username in enumerate(usernames):
                status_text.text(f"正在检测 [{i+1}/{len(usernames)}]: {username} ...")
                
                status, desc, verification, joined = check_user_meta(username, raw_proxy_input)
                
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
                    
            status_text.text("🎉 所有账号检测完毕，已自动写入历史数据库！")
            
            # 自动保存到本地数据库
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
                    
            # 下载按钮
            st.markdown("---")
            all_results_text = "=== 成功存活账号 ===\n" + \
                                "\n".join([f"{i['用户名']} -> {i['状态']} | 手机: {i['手机验证']} | 加入时间: {i['加入时间']}" for i in success_list]) + \
                                "\n\n=== 失败/异常账号 ===\n" + \
                                "\n".join([f"{i['用户名']} -> {i['状态']}" for i in fail_list])
                                
            st.download_button(
                label="📥 下载本次分类检测结果文件",
                data=all_results_text,
                file_name="carousell_categorized_results.txt",
                mime="text/plain"
            )

with tab_history:
    st.subheader("📜 历史检测记录（本地持久化存档）")
    st.markdown("这里保存了你历次检测的所有详细报告。即使关闭页面、刷新或重启服务，数据也不会丢失。")
    
    rows = get_all_history()
    
    if not rows:
        st.info("📭 暂无历史检测记录。请先在左侧的“批量检测工具”标签页中运行一次检测。")
    else:
        for row in rows:
            hid, timestamp, total, success, fail, data_json = row
            with st.expander(f"🕒 检测时间: {timestamp}  |  总数: {total}  |  ✅ 存活: {success}  |  ❌ 异常: {fail}"):
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
                        
                    # 每一条历史记录单独支持重新下载
                    single_text = f"=== 历史检测报告 (时间: {timestamp}) ===\n" + \
                                  "\n".join([f"{i['用户名']} -> {i['状态']} | 手机: {i['手机验证']} | 加入时间: {i['加入时间']}" for i in s_list]) + \
                                  "\n\n=== 失败/异常账号 ===\n" + \
                                  "\n".join([f"{i['用户名']} -> {i['状态']}" for i in f_list])
                                  
                    st.download_button(
                        label=f"📥 重新下载该批次报告 ({timestamp})",
                        data=single_text,
                        file_name=f"carousell_history_{timestamp.replace(':', '_').replace(' ', '_')}.txt",
                        mime="text/plain",
                        key=f"download_history_{hid}"
                    )
                except Exception as e:
                    st.error(f"解析该条历史记录出错: {e}")
