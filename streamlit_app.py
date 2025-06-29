"""
MFA-Version-2: Plan 1 - Kite MCP Streamlit App
Portfolio Investment Advisor with Real-time Zerodha Data
"""

import streamlit as st
import asyncio
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from kite_mcp_client import KiteMCPClient, MCPResponse
from portfolio_calculator import PortfolioCalculator, PortfolioAllocation
import json

# Page configuration
st.set_page_config(
    page_title="MFA-Version-2: Portfolio Advisor (Kite MCP)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "login_url" not in st.session_state:
    st.session_state.login_url = None
if "portfolio_result" not in st.session_state:
    st.session_state.portfolio_result = None

# Initialize calculator
@st.cache_resource
def get_calculator():
    return PortfolioCalculator()

calculator = get_calculator()

def create_allocation_chart(allocation: PortfolioAllocation):
    """Create portfolio allocation pie chart"""
    labels = []
    values = []
    colors = []

    if allocation.equity_percent > 0:
        labels.append(f"Equity ({allocation.equity_percent}%)")
        values.append(allocation.equity_percent)
        colors.append("#1f77b4")

    if allocation.debt_percent > 0:
        labels.append(f"Debt ({allocation.debt_percent}%)")
        values.append(allocation.debt_percent)
        colors.append("#ff7f0e")

    if allocation.gold_percent > 0:
        labels.append(f"Gold ({allocation.gold_percent}%)")
        values.append(allocation.gold_percent)
        colors.append("#ffd700")

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker_colors=colors,
        textinfo='label+percent',
        textfont_size=12
    )])

    fig.update_layout(
        title="📊 Recommended Portfolio Allocation",
        font=dict(size=14),
        showlegend=True,
        height=400
    )

    return fig

def create_projection_chart(projections, plan_type, investment_amount):
    """Create investment growth projection chart"""
    years = [5, 10, 15, 20]
    values = [projections.year_5, projections.year_10, projections.year_15, projections.year_20]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=years,
        y=values,
        mode='lines+markers',
        name='Portfolio Value',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))

    # Add investment amount reference line for lumpsum
    if plan_type.upper() != "SIP":
        fig.add_hline(
            y=investment_amount,
            line_dash="dash",
            line_color="red",
            annotation_text="Initial Investment"
        )

    fig.update_layout(
        title=f"📈 Investment Growth Projection - {plan_type}",
        xaxis_title="Years",
        yaxis_title="Portfolio Value (₹)",
        font=dict(size=12),
        height=400,
        showlegend=True
    )

    fig.update_yaxis(tickformat="₹,.0f")

    return fig

async def initialize_kite_mcp():
    """Initialize Kite MCP connection"""
    try:
        async with KiteMCPClient() as client:
            # Initialize connection
            init_response = await client.initialize_connection()
            if not init_response.success:
                return False, f"Connection failed: {init_response.error}"

            # Request login URL
            login_response = await client.request_login()
            if login_response.success and login_response.login_url:
                st.session_state.login_url = login_response.login_url
                return True, "Connection successful"
            else:
                return False, f"Login request failed: {login_response.error}"

    except Exception as e:
        return False, f"Error: {str(e)}"

async def get_mcp_recommendation(age, amount, plan_type, risk_level):
    """Get portfolio recommendation from Kite MCP"""
    try:
        async with KiteMCPClient() as client:
            response = await client.get_portfolio_recommendation(age, amount, plan_type, risk_level)
            if response.success:
                return True, response.data
            else:
                return False, response.error
    except Exception as e:
        return False, str(e)

# Sidebar - Authentication
st.sidebar.header("🔐 Kite MCP Authentication")

if not st.session_state.authenticated:
    if st.sidebar.button("🚀 Connect to Kite MCP", type="primary"):
        with st.sidebar:
            with st.spinner("Connecting to Kite MCP..."):
                success, message = asyncio.run(initialize_kite_mcp())
                if success:
                    st.success("✅ Connected to Kite MCP!")
                    if st.session_state.login_url:
                        st.info("📱 Please complete authentication:")
                        st.markdown(f"[🔗 Click here to login]({st.session_state.login_url})")
                        st.text_area(
                            "📋 Paste callback URL after login:",
                            placeholder="https://kite.zerodha.com/connect/login?status=success&session_id=...",
                            key="callback_url",
                            height=100
                        )

                        if st.button("✅ Verify Authentication"):
                            callback_url = st.session_state.get("callback_url", "")
                            if callback_url and "session_id=" in callback_url:
                                st.session_state.authenticated = True
                                st.success("🎉 Authentication successful!")
                                st.rerun()
                            else:
                                st.error("❌ Invalid callback URL")
                else:
                    st.error(f"❌ {message}")
else:
    st.sidebar.success("✅ Authenticated with Kite MCP")
    if st.sidebar.button("🔓 Logout"):
        st.session_state.authenticated = False
        st.session_state.login_url = None
        st.rerun()

# Main content
st.title("📈 MFA-Version-2: Portfolio Investment Advisor")
st.subheader("🎯 Plan 1: Kite MCP with Real-time Data")

if not st.session_state.authenticated:
    st.warning("⚠️ Please authenticate with Kite MCP to access real-time portfolio recommendations.")
    st.info("👈 Use the sidebar to connect to your Zerodha account.")

    # Show offline calculator as preview
    st.markdown("---")
    st.subheader("📊 Portfolio Calculator Preview (Offline Mode)")

# Input form
with st.form("portfolio_inputs"):
    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input(
            "👤 Your Age",
            min_value=18,
            max_value=80,
            value=30,
            step=1,
            help="Age determines the base equity allocation using 110-minus-age rule"
        )

        plan_type = st.selectbox(
            "📋 Investment Plan Type",
            ["SIP", "Lumpsum", "SWP"],
            help="SIP: Systematic Investment Plan, SWP: Systematic Withdrawal Plan"
        )

    with col2:
        if plan_type == "SIP":
            amount = st.number_input(
                "💰 Monthly SIP Amount (₹)",
                min_value=500,
                max_value=500000,
                value=10000,
                step=500
            )
        else:
            amount = st.number_input(
                "💰 Investment Amount (₹)",
                min_value=1000,
                max_value=50000000,
                value=100000,
                step=1000
            )

        risk_level = st.selectbox(
            "⚖️ Risk Tolerance",
            ["Low", "Medium", "High"],
            index=1,
            help="Risk tolerance affects equity allocation multiplier"
        )

    submitted = st.form_submit_button("🧮 Calculate Portfolio", type="primary", use_container_width=True)

if submitted:
    # Calculate portfolio using local calculator
    allocation = calculator.calculate_portfolio(age, amount, plan_type, risk_level)
    projections = calculator.calculate_projections(amount, allocation.expected_return, plan_type)
    recommendations = calculator.get_mutual_fund_recommendations(allocation, plan_type)

    st.session_state.portfolio_result = {
        "allocation": allocation,
        "projections": projections,
        "recommendations": recommendations
    }

    # Get MCP recommendation if authenticated
    if st.session_state.authenticated:
        with st.spinner("🔄 Getting real-time recommendations from Kite MCP..."):
            success, mcp_data = asyncio.run(get_mcp_recommendation(age, amount, plan_type, risk_level))
            if success:
                st.success("✅ Real-time recommendation received from Kite MCP!")
                # Store MCP data for display
                st.session_state.mcp_recommendation = mcp_data
            else:
                st.warning(f"⚠️ Could not get MCP recommendation: {mcp_data}")

# Display results
if st.session_state.portfolio_result:
    result = st.session_state.portfolio_result
    allocation = result["allocation"]
    projections = result["projections"]
    recommendations = result["recommendations"]

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 Expected Return", f"{allocation.expected_return}%", f"{allocation.real_return}% (real)")
    with col2:
        st.metric("📈 Equity Allocation", f"{allocation.equity_percent}%")
    with col3:
        st.metric("🔒 Debt Allocation", f"{allocation.debt_percent}%")
    with col4:
        if allocation.gold_percent > 0:
            st.metric("🥇 Gold Allocation", f"{allocation.gold_percent}%")
        else:
            st.metric("⚖️ Risk Level", allocation.risk_score.split(",")[0])

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_allocation_chart(allocation), use_container_width=True)
    with col2:
        st.plotly_chart(create_projection_chart(projections, plan_type, amount), use_container_width=True)

    # Investment projections table
    st.subheader("📊 Investment Growth Projections")
    projection_data = {
        "Time Period": ["5 Years", "10 Years", "15 Years", "20 Years"],
        "Portfolio Value": [
            f"₹{projections.year_5:,.0f}",
            f"₹{projections.year_10:,.0f}",
            f"₹{projections.year_15:,.0f}",
            f"₹{projections.year_20:,.0f}"
        ]
    }
    st.table(pd.DataFrame(projection_data))

    # Mutual fund recommendations
    st.subheader("🏛️ Mutual Fund Recommendations")

    tab1, tab2, tab3 = st.tabs(["📈 Equity Funds", "🔒 Debt Funds", "🥇 Gold Funds"])

    with tab1:
        if recommendations["equity_funds"]:
            for fund in recommendations["equity_funds"]:
                st.write(f"• {fund}")
        else:
            st.write("No equity allocation recommended")

    with tab2:
        if recommendations["debt_funds"]:
            for fund in recommendations["debt_funds"]:
                st.write(f"• {fund}")
        else:
            st.write("No debt allocation recommended")

    with tab3:
        if recommendations["gold_funds"]:
            for fund in recommendations["gold_funds"]:
                st.write(f"• {fund}")
        else:
            st.write("No gold allocation recommended")

    # MCP recommendation display
    if st.session_state.authenticated and "mcp_recommendation" in st.session_state:
        st.markdown("---")
        st.subheader("🔄 Real-time Insights from Kite MCP")

        try:
            mcp_data = st.session_state.mcp_recommendation
            if "result" in mcp_data and "content" in mcp_data["result"]:
                content = mcp_data["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    mcp_text = content[0].get("text", "")
                    st.markdown(mcp_text)
                else:
                    st.json(mcp_data)
            else:
                st.json(mcp_data)
        except Exception as e:
            st.error(f"Error displaying MCP data: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    **MFA-Version-2 Portfolio Advisor** | Plan 1: Kite MCP Integration

    ⚠️ **Disclaimer**: This is for educational purposes. Past performance doesn't guarantee future results.
    Always consult a financial advisor before making investment decisions.
    """
)
