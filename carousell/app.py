import time
import random
import requests
from bs4 import BeautifulSoup
import streamlit as st

# 页面配置
st.set_page_config(page_title="Carousell 账号检测工具", page_icon="🔍", layout="centered")

st.title("🔍 Carousell 账号存活状态批量检测工具（智能代理版）")
st.markdown("支持自动补全代理协议头，实现代理有效性测速、IP 归属地显示与分类统计。")

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
    # 如果用户没有写协议头，默认自动补全为最高效的 socks5h://
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

# 核心检测逻辑（使用 Session 保持连接并应用自动格式化代理）
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
            return "BANNED_OR_NOT_EXIST", "账号不存在 (404)"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        og_url = soup.find('meta', property='og:url')
        if og_url and 'content' in og_url.attrs:
            content_url = og_url['content'].lower()
            if username.lower() in content_url:
                return "ACTIVE", "正常存活"
                
        return "BANNED_OR_NOT_EXIST", "账号不存在或已被封禁"
        
    except Exception as e:
        return "ERROR", f"请求异常或代理中断: {e}"

# 开始检测按钮
if st.button("🚀 开始批量检测", type="primary"):
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
            
            status, desc = check_user_meta(username, raw_proxy_input)
            
            if status == "ACTIVE":
                success_list.append({"用户名": username, "状态": desc})
            else:
                fail_list.append({"用户名": username, "状态": desc})
            
            progress_bar.progress((i + 1) / len(usernames))
            
            if i < len(usernames) - 1:
                time.sleep(random.uniform(min_delay, max_delay))
                
        status_text.text("🎉 所有账号检测完毕！")
        
        # --- 数据展示区 ---
        st.markdown("---")
        st.subheader("📊 检测统计结果")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("总检测数", len(usernames))
        col2.metric("✅ 成功存活", len(success_list))
        col3.metric("❌ 失败/封禁", len(fail_list))
        
        tab1, tab2 = st.tabs([f"✅ 成功存活 ({len(success_list)})", f"❌ 失败/异常 ({len(fail_list)})"])
        
        with tab1:
            if success_list:
                for item in success_list:
                    st.success(f"**{item['用户名']}** -> {item['状态']}")
            else:
                st.info("没有检测到存活的账号。")
                
        with tab2:
            if fail_list:
                for item in fail_list:
                    st.error(f"**{item['用户名']}** -> {item['状态']}")
            else:
                st.info("没有检测到失败或封禁的账号。")
                
        # 下载按钮
        st.markdown("---")
        all_results_text = "=== 成功存活账号 ===\n" + \
                           "\n".join([f"{i['用户名']} -> {i['状态']}" for i in success_list]) + \
                           "\n\n=== 失败/异常账号 ===\n" + \
                           "\n".join([f"{i['用户名']} -> {i['状态']}" for i in fail_list])
                           
        st.download_button(
            label="📥 下载分类检测结果文件",
            data=result_text if 'result_text' in locals() else all_results_text,
            file_name="carousell_categorized_results.txt",
            mime="text/plain"
        )