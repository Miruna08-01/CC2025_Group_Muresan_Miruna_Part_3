import os
import urllib.parse

import streamlit as st
import requests
import jwt
import pandas as pd
import altair as alt

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(page_title="Streamlit + Cognito Secure App", layout="wide")
st.title("✅ Streamlit Frontend (AWS Cognito)")

# ----------------------------
# Env
# ----------------------------
COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
BACKEND_URL = os.getenv("BACKEND_URL")

missing = [k for k, v in {
    "COGNITO_DOMAIN": COGNITO_DOMAIN,
    "COGNITO_CLIENT_ID": COGNITO_CLIENT_ID,
    "REDIRECT_URI": REDIRECT_URI,
    "BACKEND_URL": BACKEND_URL,
}.items() if not v]

if missing:
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

REDIRECT_URI = REDIRECT_URI.rstrip("/")
redirect_enc = urllib.parse.quote(REDIRECT_URI, safe="")

AUTH_URL = (
    f"{COGNITO_DOMAIN}/oauth2/authorize"
    f"?client_id={COGNITO_CLIENT_ID}"
    f"&response_type=code"
    f"&scope=openid+email+profile"
    f"&redirect_uri={redirect_enc}"
)

TOKEN_URL = f"{COGNITO_DOMAIN}/oauth2/token"

LOGOUT_URL = (
    f"{COGNITO_DOMAIN}/logout?"
    f"client_id={COGNITO_CLIENT_ID}"
    f"&logout_uri={REDIRECT_URI}"
)

# ----------------------------
# Helpers
# ----------------------------
def decode_jwt_no_verify(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})

def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"error": "Response is not JSON", "text": resp.text}

# ----------------------------
# Session init
# ----------------------------
if "id_token" not in st.session_state:
    st.session_state["id_token"] = None

# ----------------------------
# Exchange code -> token
# ----------------------------
params = st.query_params
code = params.get("code")

if code and not st.session_state["id_token"]:
    try:
        token_resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": COGNITO_CLIENT_ID,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=20,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        st.session_state["id_token"] = tokens.get("id_token")

        # curățăm ?code=...
        st.query_params.clear()
        st.success("✅ Logged in with Cognito!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Token exchange failed: {e}")
        st.stop()

# ----------------------------
# Login screen
# ----------------------------
if not st.session_state["id_token"]:
    st.info("You are not logged in.")
    # în mod normal link_button deschide în același tab
    if st.button("🔐 Login with AWS Cognito"):
        st.markdown(f'<meta http-equiv="refresh" content="0; url={AUTH_URL}">', unsafe_allow_html=True)
        st.stop()

# ----------------------------
# Claims (client-side decode)
# ----------------------------
claims = decode_jwt_no_verify(st.session_state["id_token"])
groups = claims.get("cognito:groups", [])
role = groups[0] if isinstance(groups, list) and groups else (groups or "user")
device_claim = claims.get("custom:device_id")

st.success(f"Logged in as: {claims.get('email')}")
st.write("Role:", role)
st.write("Device claim:", device_claim)

# ----------------------------
# Logout + Token details
# ----------------------------
col1, col2 = st.columns(2)

with col1:
    if st.button("🚪 Logout"):
        st.session_state["id_token"] = None
        st.link_button("Logout from Cognito", LOGOUT_URL)
        st.stop()

with col2:
    st.caption("Token is sent to backend via Authorization: Bearer <id_token>")

with st.expander("🔑 Token details"):
    st.write("Token ID (sub):", claims.get("sub"))
    st.write("Role:", role)
    st.write("Device claim:", device_claim)
    st.code(st.session_state["id_token"], language="text")

headers = {"Authorization": f"Bearer {st.session_state['id_token']}"}

# ----------------------------
# /api/profile (pretty JSON)
# ----------------------------
st.subheader("👤 /api/profile")
profile_payload = None
try:
    r = requests.get(f"{BACKEND_URL}/api/profile", headers=headers, timeout=20)
    st.write("Status:", r.status_code)
    profile_payload = safe_json(r)
    st.json(profile_payload)
except Exception as e:
    st.error(f"Backend /api/profile error: {e}")

# ----------------------------
# /api/data (latest totals)
# ----------------------------
st.subheader("📦 /api/data (latest totals)")
data_payload = None
try:
    r = requests.get(f"{BACKEND_URL}/api/data", headers=headers, timeout=30)
    st.write("Status:", r.status_code)
    data_payload = safe_json(r)
except Exception as e:
    st.error(f"Backend /api/data error: {e}")
    st.stop()

with st.expander("🔎 /api/data raw JSON (debug)"):
    st.json(data_payload)

# ----------------------------
# /api/history (historical totals)
# ----------------------------
st.subheader("📈 /api/history (historical totals)")
hist_payload = None
try:
    r = requests.get(f"{BACKEND_URL}/api/history?folders_limit=5", headers=headers, timeout=60)
    st.write("Status:", r.status_code)
    hist_payload = safe_json(r)
except Exception as e:
    st.error(f"Backend /api/history error: {e}")
    st.stop()

with st.expander("🔎 /api/history raw JSON (debug)"):
    st.json(hist_payload)

# ------------------------------------------------------------
# ✅ DOAR ADMIN VEDE VIZUALIZARILE
# ------------------------------------------------------------
if role != "admin":
    st.info("ℹ️ Visualizations are available only for admin users.")
    st.stop()

st.markdown("## ✅ Final Project Visualizations (Admin only)")

# ============================================================
# 1) Latest dataset table (from /api/data)
# ============================================================
st.markdown("### 1) Latest dataset table (from /api/data)")

latest_items = (data_payload or {}).get("items")
if latest_items is None:
    # fallback dacă backend-ul returnează "data"
    latest_items = (data_payload or {}).get("data", [])

# dacă e listă de dict -> OK
# dacă cumva e listă cu un singur element care e tot o listă -> o “dezîmpachetăm”
if isinstance(latest_items, list) and len(latest_items) == 1 and isinstance(latest_items[0], list):
    latest_items = latest_items[0]

if not isinstance(latest_items, list) or len(latest_items) == 0:
    st.error("No latest items found in /api/data. Check the debug JSON above.")
    st.stop()

df_latest = pd.json_normalize(latest_items)
# păstrăm doar ce te interesează
cols = [c for c in ["device_id", "total_kwh"] if c in df_latest.columns]
df_latest = df_latest[cols].copy()

if "total_kwh" in df_latest.columns:
    df_latest["total_kwh"] = pd.to_numeric(df_latest["total_kwh"], errors="coerce")

st.dataframe(df_latest, use_container_width=True)

# ============================================================
# 2) Historical trend line chart (from /api/history)
#    total_kwh over time per device
# ============================================================
st.markdown("### 2) Historical trend line chart (total_kwh over time, from /api/history)")

hist_items = (hist_payload or {}).get("items", [])
if not isinstance(hist_items, list) or len(hist_items) == 0:
    st.error("No historical items found in /api/history. Check the debug JSON above.")
    st.stop()

df_hist = pd.json_normalize(hist_items)

# IMPORTANT: la tine timpul e "generation_timestamp", nu "timestamp"
if "generation_timestamp" not in df_hist.columns:
    st.error("Missing generation_timestamp in /api/history items.")
    st.stop()

df_hist["generation_timestamp"] = pd.to_datetime(df_hist["generation_timestamp"], errors="coerce")
df_hist["total_kwh"] = pd.to_numeric(df_hist.get("total_kwh"), errors="coerce")

df_hist = df_hist.dropna(subset=["generation_timestamp", "total_kwh", "device_id"])

line = alt.Chart(df_hist).mark_line().encode(
    x=alt.X("generation_timestamp:T", title="generation_timestamp"),
    y=alt.Y("total_kwh:Q", title="total_kwh"),
    color=alt.Color("device_id:N", title="device_id"),
    tooltip=["device_id:N", "generation_timestamp:T", "total_kwh:Q"]
).interactive()

st.altair_chart(line, use_container_width=True)

# ============================================================
# 3) Additional chart: total records per device (from /api/history)
# ============================================================
st.markdown("### 3) Bar chart: total records per device (from /api/history)")

counts = df_hist.groupby("device_id").size().reset_index(name="count")

bar = alt.Chart(counts).mark_bar().encode(
    x=alt.X("device_id:N", title="device_id"),
    y=alt.Y("count:Q", title="records"),
    tooltip=["device_id:N", "count:Q"]
).interactive()

st.altair_chart(bar, use_container_width=True)
