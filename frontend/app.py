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
            timeout=15,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        st.session_state["id_token"] = tokens.get("id_token")

        # curat query params (scapă de ?code=...)
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
    st.link_button("🔐 Login with AWS Cognito", AUTH_URL)
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
        st.info("Logout link (optional):")
        st.write(LOGOUT_URL)
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
# /api/profile (JSON)
# ----------------------------
st.subheader("👤 /api/profile")
try:
    r = requests.get(f"{BACKEND_URL}/api/profile", headers=headers, timeout=15)
    st.write("Status:", r.status_code)
    profile_payload = r.json()
    st.json(profile_payload)
except Exception as e:
    st.error(f"Backend /api/profile error: {e}")
    st.stop()

# ----------------------------
# /api/data (JSON)
# ----------------------------
st.subheader("📦 /api/data")
try:
    r = requests.get(f"{BACKEND_URL}/api/data", headers=headers, timeout=30)
    st.write("Status:", r.status_code)
    data_payload = r.json()
    st.json(data_payload)
except Exception as e:
    st.error(f"Backend /api/data error: {e}")
    st.stop()

# ----------------------------
# /api/history (JSON)
# ----------------------------
st.subheader("📈 /api/history")
try:
    r = requests.get(f"{BACKEND_URL}/api/history?folders_limit=7", headers=headers, timeout=60)
    st.write("Status:", r.status_code)
    hist_payload = r.json()
    st.json(hist_payload)
except Exception as e:
    st.error(f"Backend /api/history error: {e}")
    st.stop()

# ------------------------------------------------------------
# ✅ DOAR ADMIN VEDE VIZUALIZARILE
# ------------------------------------------------------------
if role != "admin":
    st.info("ℹ️ Visualizations are available only for admin users.")
    st.stop()

# ----------------------------
# Parse /api/data items (admin latest totals)
# ----------------------------
items_latest = (data_payload or {}).get("items")
if items_latest is None:
    # fallback daca backend a trimis "data"
    items_latest = (data_payload or {}).get("data", [])

if not isinstance(items_latest, list) or len(items_latest) == 0:
    st.error("No device totals received from backend in /api/data. Check JSON above.")
    st.stop()

df_latest = pd.DataFrame(items_latest)

# ----------------------------
# Parse /api/history items (admin historical totals)
# ----------------------------
hist_items = (hist_payload or {}).get("items", [])
if not isinstance(hist_items, list) or len(hist_items) == 0:
    st.error("No historical items received from /api/history. Check JSON above.")
    st.stop()

df_hist = pd.DataFrame(hist_items)

# ✅ timestamp corect in history = generation_timestamp
df_hist["generation_timestamp"] = pd.to_datetime(df_hist["generation_timestamp"], errors="coerce")
df_hist = df_hist.dropna(subset=["generation_timestamp"])

# ------------------------------------------------------------
# Admin visualizations
# ------------------------------------------------------------
st.markdown("## ✅ Final Project Visualizations (Admin only)")

# 1) Latest dataset table
st.markdown("### 1) Latest dataset table (from /api/data)")
st.dataframe(df_latest, use_container_width=True)

# 2) Historical trend line chart
st.markdown("### 2) Historical trend line chart (total_kwh over time, from /api/history)")
if {"generation_timestamp", "total_kwh", "device_id"}.issubset(df_hist.columns):
    line = alt.Chart(df_hist).mark_line().encode(
        x="generation_timestamp:T",
        y="total_kwh:Q",
        color="device_id:N",
        tooltip=["device_id:N", "generation_timestamp:T", "total_kwh:Q", "folder:N"]
    )
    st.altair_chart(line, use_container_width=True)
else:
    st.info("Need fields in history: generation_timestamp + total_kwh + device_id")

# 3) Additional chart: bar chart
st.markdown("### 3) Additional chart: number of historical snapshots per device")
if "device_id" in df_hist.columns:
    counts = df_hist.groupby("device_id").size().reset_index(name="count")
    bar = alt.Chart(counts).mark_bar().encode(
        x="device_id:N",
        y="count:Q",
        tooltip=["device_id:N", "count:Q"]
    )
    st.altair_chart(bar, use_container_width=True)
else:
    st.info("Need field: device_id in history for bar chart")
