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

def js_redirect(url: str):
    st.markdown(
        f"""
        <script>
            window.location.href = "{url}";
        </script>
        """,
        unsafe_allow_html=True
    )

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
profile_payload = None
try:
    r = requests.get(f"{BACKEND_URL}/api/profile", headers=headers, timeout=15)
    st.write("Status:", r.status_code)
    profile_payload = r.json()
    st.json(profile_payload)
except Exception as e:
    st.error(f"Backend /api/profile error: {e}")

# ----------------------------
# /api/data (JSON)
# ----------------------------
st.subheader("📦 /api/data")
data_payload = None
try:
    r = requests.get(f"{BACKEND_URL}/api/data", headers=headers, timeout=30)
    st.write("Status:", r.status_code)
    data_payload = r.json()
    st.json(data_payload)
except Exception as e:
    st.error(f"Backend /api/data error: {e}")
    st.stop()

# ------------------------------------------------------------
# ✅ DOAR ADMIN VEDE VIZUALIZARILE
# ------------------------------------------------------------
if role != "admin":
    st.info("ℹ️ Visualizations are available only for admin users.")
    st.stop()

# ----------------------------
# Admin visualizations
# ----------------------------
st.markdown("## ✅ Final Project Visualizations (Admin only)")

items = (data_payload or {}).get("items", [])
if not items:
    st.warning("No devices found in /api/data items.")
    st.stop()

df = pd.DataFrame(items)

st.markdown("### 1) Device totals table")
st.dataframe(df, use_container_width=True)

st.markdown("### 2) Bar chart: total_kwh per device")
if "device_id" in df.columns and "total_kwh" in df.columns:
    bar = alt.Chart(df).mark_bar().encode(
        x="device_id:N",
        y="total_kwh:Q",
        tooltip=["device_id:N", "total_kwh:Q"]
    )
    st.altair_chart(bar, use_container_width=True)
else:
    st.info("Need fields: device_id + total_kwh for bar chart")
