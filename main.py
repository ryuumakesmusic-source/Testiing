import asyncio
import json
import websockets
from websockets.exceptions import InvalidStatus


# --- CONFIG ---
# 1. REFRESH YOUR BROWSER
# 2. FIND THE REAL WS REQUEST IN NETWORK TAB
# 3. PASTE JSESSIONID / tableId / cookie BELOW
#
JSESSIONID = "0G6mPNDjUOwVKMhUPiUADP3oNWSs3XEW1Y-xu3El7dpucO1FDyx2!1489444964-46192d8d"
TABLE_ID = "pwnhicogrzeodk79"
WS_HOST = "gs18.pragmaticplaylive.net"
OPTIONAL_COOKIE = ""  # Paste full Cookie header value if browser request includes it.
OPTIONAL_SUBPROTOCOL = None  # Example: "graphql-ws" if your WS request uses one.

RESULT_MAP = {0: "PLAYER 🔵", 1: "BANKER 🔴", 2: "TIE 🟢"}
AUTO_SUBSCRIBE = False  # Keep false for /game endpoint to avoid DOUBLE_SUBSCRIPTION.


def normalize_result(code, result_text):
    if isinstance(code, str) and code.isdigit():
        code = int(code)
    if isinstance(code, int):
        return RESULT_MAP.get(code)

    text = (result_text or "").strip().lower()
    if text == "player":
        return RESULT_MAP[0]
    if text == "banker":
        return RESULT_MAP[1]
    if text == "tie":
        return RESULT_MAP[2]
    return None

async def stream_results():
    # Match the browser WS URL shape from your captured request.
    ws_url = (
        f"wss://{WS_HOST}/game"
        f"?JSESSIONID={JSESSIONID}"
        f"&tableId={TABLE_ID}"
        "&type=json"
        "&pageRefresh=true"
    )

    # Keep headers close to browser traffic.
    headers = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"),
        ("Origin", "https://client.pragmaticplaylive.net"),
        ("Pragma", "no-cache"),
        ("Cache-Control", "no-cache"),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    if OPTIONAL_COOKIE:
        headers.append(("Cookie", OPTIONAL_COOKIE))
    
    print(f"🚀 Attempting connection to Game Server...")
    print(f"🔎 WS URL: {ws_url}")
    print(f"🔎 Cookie attached: {'yes' if OPTIONAL_COOKIE else 'no'}")
    print(f"🔎 Subprotocol: {OPTIONAL_SUBPROTOCOL if OPTIONAL_SUBPROTOCOL else 'none'}")
    
    try:
        seen_game_ids = set()
        connect_kwargs = {
            "additional_headers": headers,
            "proxy": None,
        }
        if OPTIONAL_SUBPROTOCOL:
            connect_kwargs["subprotocols"] = [OPTIONAL_SUBPROTOCOL]

        async with websockets.connect(ws_url, **connect_kwargs) as ws:
            print("✅ Connection Established!")
            if AUTO_SUBSCRIBE:
                try:
                    payload = {"type": "subscribe", "tableId": TABLE_ID}
                    await ws.send(json.dumps(payload))
                    print(f"➡️ Sent: {payload}")
                except Exception as send_error:
                    print(f"⚠️ Subscribe send failed: {send_error}")
            else:
                print("ℹ️ Passive mode: no subscribe packet sent.")

            print("📡 Listening for live data...\n")

            async for message in ws:
                data = json.loads(message)

                # Main target: exact round outcome from server.
                if "gameresult" in data:
                    payload = data.get("gameresult", {})
                    game_id = payload.get("gameId") or payload.get("id")
                    if game_id and game_id in seen_game_ids:
                        continue
                    if game_id:
                        seen_game_ids.add(game_id)

                    pretty = normalize_result(payload.get("code"), payload.get("result"))
                    if pretty:
                        print(f"🏁 FINAL RESULT: {pretty} | gameId={game_id}")
                    else:
                        print(f"🏁 FINAL RESULT: raw={payload.get('result')} code={payload.get('code')} | gameId={game_id}")

                if "closeConnection" in data:
                    print(f"⛔ closeConnection: {data['closeConnection']}")
                if "duplicated_connection" in data:
                    print(f"⛔ duplicated_connection: {data['duplicated_connection']}")

                # Your capture shows frequent betstats packets; print useful round stats.
                if "betstats" in data:
                    stats = data.get("betstats", {})
                    if isinstance(stats, dict):
                        seq = stats.get("seq")
                        banker_pct = stats.get("bankerpercentage")
                        player_pct = stats.get("playerpercentage")
                        tie_pct = stats.get("tiepercentage")
                        print(
                            f"📊 BETSTATS seq={seq} | P%={player_pct} B%={banker_pct} T%={tie_pct}"
                        )

                # Print history when first connecting
                if "tableState" in data:
                    history = data["tableState"].get("history", [])
                    print(f"📜 HISTORY: {history[-10:]}")
                    if history:
                        last = history[-1]
                        print(f"🏁 RESULT (from history): {RESULT_MAP.get(last, '???')}")

                # Print every live result
                if "winType" in str(data):
                    try:
                        winner_code = data.get("data", {}).get("winType")
                        if winner_code is not None:
                            print(f"🏁 RESULT: {RESULT_MAP.get(winner_code, '???')}")
                    except Exception:
                        pass

                # Fallback parser for variants where winner appears under other keys.
                for key in ("winner", "winnerCode", "winnerType", "result"):
                    if key in data:
                        print(f"🏁 RESULT ({key}): {data.get(key)}")

    except InvalidStatus as e:
        status = e.response.status_code
        reason = e.response.reason_phrase
        print(f"❌ Handshake rejected: HTTP {status} {reason}")
        location = e.response.headers.get("Location")
        if location:
            print(f"↪ Redirect Location: {location}")
        set_cookie = e.response.headers.get("Set-Cookie")
        if set_cookie:
            print("↪ Server sent Set-Cookie (session likely required).")
        body = (e.response.body or b"").decode("utf-8", errors="replace").strip()
        if body:
            print(f"↪ Response body preview: {body[:300]}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print(f"❌ Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(stream_results())