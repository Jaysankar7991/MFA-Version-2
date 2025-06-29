"""
MFA-Version-2: Kite MCP Client for VS Code Integration
Enhanced client that resolves authentication and connection issues
"""

import asyncio
import aiohttp
import json
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class MCPResponse:
    success: bool
    data: Optional[Dict[Any, Any]] = None
    error: Optional[str] = None
    login_url: Optional[str] = None

class KiteMCPClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.mcp_url = "https://mcp.kite.trade/sse"
        self.session_id = None
        self.authenticated = False
        self.retry_count = 3
        self.timeout = 30

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def initialize_connection(self) -> MCPResponse:
        """Initialize SSE connection with MCP server"""
        try:
            self.logger.info(f"Connecting to Kite MCP server: {self.mcp_url}")

            # Send initialization message
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "resources": {"listChanged": True}
                    },
                    "clientInfo": {
                        "name": "MFA-Version-2",
                        "version": "1.0.0"
                    }
                }
            }

            for attempt in range(self.retry_count):
                try:
                    async with self.session.post(
                        self.mcp_url,
                        json=init_payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            self.logger.info("✅ MCP connection initialized successfully")
                            return MCPResponse(success=True, data=result)
                        else:
                            self.logger.warning(f"Attempt {attempt + 1} failed with status {response.status}")

                except Exception as e:
                    self.logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

            return MCPResponse(success=False, error="Failed to initialize MCP connection after all retries")

        except Exception as e:
            self.logger.error(f"Initialize connection error: {str(e)}")
            return MCPResponse(success=False, error=str(e))

    async def request_login(self) -> MCPResponse:
        """Request login URL from Kite MCP server"""
        try:
            login_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "login",
                    "arguments": {}
                }
            }

            self.logger.info("🔐 Requesting login URL from Kite MCP...")

            async with self.session.post(
                self.mcp_url,
                json=login_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()

                    # Extract login URL from response
                    if "result" in result and "content" in result["result"]:
                        content = result["result"]["content"]
                        if isinstance(content, list) and len(content) > 0:
                            login_info = content[0].get("text", "")

                            # Parse login URL
                            if "https://kite.zerodha.com/connect/login" in login_info:
                                login_url = login_info.split("URL: ")[1].split("\n")[0] if "URL: " in login_info else login_info
                                self.logger.info("✅ Login URL received successfully")
                                return MCPResponse(success=True, login_url=login_url.strip())

                    self.logger.error("❌ Could not extract login URL from response")
                    return MCPResponse(success=False, error="Invalid response format")
                else:
                    error_msg = f"Login request failed with status {response.status}"
                    self.logger.error(f"❌ {error_msg}")
                    return MCPResponse(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Login request error: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return MCPResponse(success=False, error=error_msg)

    async def get_portfolio_recommendation(self, age: int, amount: float, plan_type: str, risk_level: str) -> MCPResponse:
        """Get portfolio recommendation from Kite MCP with real-time data"""
        try:
            # Create comprehensive query for portfolio advice
            query_text = f"""
            I am {age} years old and want to invest ₹{amount:,.0f} through {plan_type}.
            My risk tolerance is {risk_level}.

            Please provide:
            1. Optimal asset allocation (equity/debt/gold percentages)
            2. Specific mutual fund recommendations 
            3. Expected returns over 5, 10, and 15 years
            4. Current market conditions analysis
            5. Tax-efficient investment strategy

            Consider current market data, interest rates, and inflation while making recommendations.
            """

            recommendation_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call", 
                "params": {
                    "name": "get_investment_advice",
                    "arguments": {
                        "query": query_text,
                        "age": age,
                        "amount": amount,
                        "investment_type": plan_type,
                        "risk_profile": risk_level
                    }
                }
            }

            self.logger.info("📊 Requesting portfolio recommendation...")

            async with self.session.post(
                self.mcp_url,
                json=recommendation_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info("✅ Portfolio recommendation received")
                    return MCPResponse(success=True, data=result)
                else:
                    error_msg = f"Portfolio request failed with status {response.status}"
                    self.logger.error(f"❌ {error_msg}")
                    return MCPResponse(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Portfolio recommendation error: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return MCPResponse(success=False, error=error_msg)

    def extract_session_id_from_callback(self, callback_url: str) -> Optional[str]:
        """Extract session ID from Zerodha callback URL"""
        try:
            if "session_id=" in callback_url:
                session_id = callback_url.split("session_id=")[1].split("&")[0]
                self.session_id = session_id
                self.authenticated = True
                self.logger.info("✅ Session ID extracted successfully")
                return session_id
            return None
        except Exception as e:
            self.logger.error(f"❌ Error extracting session ID: {str(e)}")
            return None
