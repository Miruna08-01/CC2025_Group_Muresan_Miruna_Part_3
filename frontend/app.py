import streamlit as st
import requests
import jwt
import pandas as pd
import altair as alt

st.set_page_config(page_title="Streamlit + Cognito Secure App", layout="wide")
st.title("✅ Streamlit Frontend (AWS Cognito)")

import os
import streamlit as st

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

AUTH_URL = (
    f"{COGNITO_DOMAIN}/oauth2/authorize?"
    f"client_id={COGNITO_CLIENT_ID}"
    f"&response_type=code"
    f"&scope=openid+email+profile"
    f"&redirect_uri={REDIRECT_URI}"
)

TOKEN_URL = f"{COGNITO_DOMAIN}/oauth2/token"

LOGOUT_URL = (
    f"{COGNITO_DOMAIN}/logout?"
    f"client_id={COGNITO_CLIENT_ID}"
    f"&logout_uri={REDIRECT_URI}"
)

def decode_jwt_no_verify(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})


# session init
if "id_token" not in st.session_state:
    st.session_state["id_token"] = None


# exchange code -> tokens
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
            timeout=10,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        st.session_state["id_token"] = tokens["id_token"]

        st.query_params.clear()
        st.success("✅ Logged in with Cognito!")
    except Exception as e:
        st.error(f"❌ Token exchange failed: {e}")


# login if needed
if not st.session_state["id_token"]:
    st.info("You are not logged in.")
    st.link_button("🔐 Login with AWS Cognito", AUTH_URL)
    st.stop()


# show claims
claims = decode_jwt_no_verify(st.session_state["id_token"])
groups = claims.get("cognito:groups", [])
role = groups[0] if isinstance(groups, list) and groups else (groups or "user")
device_id = claims.get("custom:device_id")

st.success(f"Logged in as: {claims.get('email')}")
st.write("Role:", role)
st.write("Device claim:", device_id)

col1, col2 = st.columns(2)

with col1:
    if st.button("🚪 Logout"):
        st.session_state["id_token"] = None
        st.link_button("Logout from Cognito", LOGOUT_URL)
        st.stop()

with col2:
    st.caption("Token is sent to backend via Authorization: Bearer <id_token>")


headers = {"Authorization": f"Bearer {st.session_state['id_token']}"}

# call profile
st.subheader("👤 /api/profile")
try:
    r = requests.get(f"{BACKEND_URL}/api/profile", headers=headers, timeout=10)
    st.json(r.json())
except Exception as e:
    st.error(f"Backend /api/profile error: {e}")


# call data
st.subheader("📦 /api/data")
try:
    r = requests.get(f"{BACKEND_URL}/api/data", headers=headers, timeout=10)
    payload = r.json()
    st.write("Status:", r.status_code)
except Exception as e:
    st.error(f"Backend /api/data error: {e}")
    st.stop()

if "items" not in payload:
    st.warning(payload)
    st.stop()

items = payload["items"]
df = pd.DataFrame(items)

# --- FINAL PROJECT VISUALIZATIONS ---
st.markdown("## ✅ Final Project Visualizations")

st.markdown("### 1) Latest dataset table")
st.dataframe(df, use_container_width=True)

st.markdown("### 2) Historical Trend Line chart")
if "timestamp" in df.columns and "value" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df2 = df.dropna(subset=["timestamp", "value"])

    line = alt.Chart(df2).mark_line().encode(
        x="timestamp:T",
        y="value:Q",
        tooltip=["timestamp:T", "value:Q", "device_id:N"]
    )
    st.altair_chart(line, use_container_width=True)
else:
    st.info("Need fields: timestamp + value for line chart")

st.markdown("### 3) Bar chart : total records per device")
if "device_id" in df.columns:
    counts = df.groupby("device_id").size().reset_index(name="count")

    bar = alt.Chart(counts).mark_bar().encode(
        x="device_id:N",
        y="count:Q",
        tooltip=["device_id:N", "count:Q"]
    )
    st.altair_chart(bar, use_container_width=True)
else:
    st.info("Need field: device_id for bar chart")
