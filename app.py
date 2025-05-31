import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# Set page config
st.set_page_config(
    page_title="评标价得分计算工具",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'current_prices' not in st.session_state:
    st.session_state.current_prices = []
if 'need_recalculate' not in st.session_state:
    st.session_state.need_recalculate = False

def store_prices(prices):
    """存储当前输入的价格数据"""
    st.session_state.current_prices = prices
    st.session_state.need_recalculate = False

def trigger_recalculate():
    """触发重新计算"""
    st.session_state.need_recalculate = True

def calculate_first_average(prices, m=0, k=0):
    """计算首次平均价A1"""
    n = len(prices)
    if n <= 3:
        return np.mean(prices), prices, "所有评标价的平均值"
    
    # Sort prices and remove highest m and lowest k prices
    sorted_prices = sorted(prices)
    remaining_prices = sorted_prices[k:n-m]
    
    if len(remaining_prices) == 0:
        return np.mean(prices), prices, "所有评标价的平均值（剔除后有效供应商数为0）"
    elif len(remaining_prices) == 1:
        prices_without_highest = [p for p in prices if p != max(prices)]
        return np.mean(prices_without_highest), prices_without_highest, "去掉最高价后的平均值（剔除后有效供应商数为1）"
    else:
        return np.mean(remaining_prices), remaining_prices, "剩余评标价的平均值"

def calculate_second_average(prices, first_avg, s1=-0.2, s2=0.1):
    """计算再次平均价A2"""
    valid_prices = [p for p in prices if s1 <= (first_avg - p) / first_avg <= s2]
    if not valid_prices:
        return first_avg, prices, "使用首次平均价（无有效价格在偏离范围内）"
    return np.mean(valid_prices), valid_prices, "偏离范围内价格的平均值"

def calculate_price_score(bid_price, base_price, e_higher=1.0, e_lower=0.5):
    """计算价格得分"""
    if bid_price == base_price:
        return 100.0
    elif bid_price > base_price:
        score = 100 - abs(bid_price - base_price) / base_price * 100 * e_higher
    else:
        score = 100 - abs(bid_price - base_price) / base_price * 100 * e_lower
    
    return max(round(score, 2), 0)

# Title
st.title("评标价得分计算工具")

# Sidebar for parameters
with st.sidebar:
    st.header("参数设置")
    
    # K value input
    k_value = st.slider(
        "引导系数 K",
        min_value=0.80,
        max_value=1.00,
        value=0.90,
        step=0.01,
        help="取值范围：[0.8, 1]",
        on_change=trigger_recalculate
    )
    
    # E values input
    e_higher = st.number_input(
        "减分系数 E (D₁ > D)",
        min_value=0.0,
        max_value=2.0,
        value=1.0,
        step=0.1,
        on_change=trigger_recalculate
    )
    
    e_lower = st.number_input(
        "减分系数 E (D₁ < D)",
        min_value=0.0,
        max_value=2.0,
        value=0.5,
        step=0.1,
        on_change=trigger_recalculate
    )
    
    # Elimination rules
    use_elimination = st.checkbox("启用剔除规则", value=False, on_change=trigger_recalculate)
    
    if use_elimination:
        col1, col2 = st.columns(2)
        with col1:
            m_value = st.number_input("剔除最高价个数", min_value=0, value=0, on_change=trigger_recalculate)
        with col2:
            k_value_elim = st.number_input("剔除最低价个数", min_value=0, value=0, on_change=trigger_recalculate)
    
    # Deviation thresholds
    st.subheader("偏离值范围设置")
    col3, col4 = st.columns(2)
    with col3:
        s1_value = st.number_input("偏离下限", value=-0.2, step=0.01, format="%.2f", on_change=trigger_recalculate)
    with col4:
        s2_value = st.number_input("偏离上限", value=0.1, step=0.01, format="%.2f", on_change=trigger_recalculate)
    
    # Add recalculate button
    if st.session_state.need_recalculate and len(st.session_state.current_prices) > 0:
        st.warning("参数已更改，请点击下方按钮重新计算")
        if st.button("重新计算", type="primary"):
            prices = st.session_state.current_prices
            st.session_state.need_recalculate = False
            st.rerun()

# Main content
# Input method selection
input_method = st.radio(
    "选择输入方式",
    ["手动输入", "文件导入"]
)

prices = []

if input_method == "手动输入":
    price_input = st.text_area(
        "请输入评标价格（每行一个数值）",
        help="每行输入一个大于0的数值"
    )
    
    if price_input:
        try:
            prices = [float(p.strip()) for p in price_input.split('\n') if p.strip()]
            if any(p <= 0 for p in prices):
                st.error("评标价格必须大于0")
                prices = []
            else:
                store_prices(prices)
        except ValueError:
            st.error("请输入有效的数值")
            prices = []

else:
    uploaded_file = st.file_uploader("上传Excel或CSV文件", type=['csv', 'xlsx', 'xls'])
    if uploaded_file is not None:
        try:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            if file_extension in ['xlsx', 'xls']:
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            if len(df.columns) >= 1:
                price_column = st.selectbox("选择评标价格列", df.columns)
                prices = df[price_column].tolist()
                if any(pd.isna(p) for p in prices):
                    st.error("数据中包含空值，请检查数据")
                    prices = []
                elif any(p <= 0 for p in prices):
                    st.error("评标价格必须大于0")
                    prices = []
                else:
                    store_prices(prices)
            else:
                st.error("文件格式不正确")
        except Exception as e:
            st.error(f"文件读取错误: {str(e)}")

# Use stored prices if available and no new input
if not prices and st.session_state.current_prices:
    prices = st.session_state.current_prices

if prices:
    # Calculate results
    if use_elimination:
        first_avg, remaining_prices, first_avg_note = calculate_first_average(
            prices,
            m_value,
            k_value_elim
        )
    else:
        first_avg, remaining_prices, first_avg_note = calculate_first_average(prices)
    
    # Calculate second average
    second_avg, final_prices, second_avg_note = calculate_second_average(
        remaining_prices,
        first_avg,
        s1_value,
        s2_value
    )
    
    # Calculate base price
    base_price = second_avg * k_value
    
    # Calculate scores and deviations for each price
    results = []
    for i, price in enumerate(prices, 1):
        # Calculate deviations
        first_deviation = round((first_avg - price) / first_avg, 4)
        final_deviation = round((second_avg - price) / second_avg, 4)
        
        # Calculate score
        score = calculate_price_score(price, base_price, e_higher, e_lower)
        
        results.append({
            "序号": i,
            "评标价格": price,
            "首次平均价": first_avg,
            "首次偏离值": f"{first_deviation:.2%}",
            "再次平均价": second_avg,
            "评标基准价": base_price,
            "最终偏离值": f"{final_deviation:.2%}",
            "价格得分": score
        })
    
    # Display calculation process
    st.subheader("计算过程")
    col5, col6 = st.columns(2)
    with col5:
        st.write("**首次平均价(A1)计算：**", first_avg_note)
        st.write(f"A1 = {first_avg:.2f}")
    with col6:
        st.write("**再次平均价(A2)计算：**", second_avg_note)
        st.write(f"A2 = {second_avg:.2f}")
    
    st.write("**评标基准价(D)计算：**")
    st.write(f"D = A2 × K = {second_avg:.2f} × {k_value} = {base_price:.2f}")
    
    # Display results
    st.subheader("计算结果")
    df_results = pd.DataFrame(results)
    st.dataframe(df_results, use_container_width=True)
    
    # Export results
    buffer = io.BytesIO()
    df_results.to_excel(buffer, index=False, engine='openpyxl')
    st.download_button(
        label="导出结果(Excel)",
        data=buffer,
        file_name=f"评标得分计算结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
