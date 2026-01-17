import streamlit as st
import requests

st.title("Frontend Streamlit")

backend_url = "https://cc2025-api-b2btduguh5cmdxbn.northeurope-01.azurewebsites.net/api/data"

try:
    response = requests.get(backend_url)
    data = response.json()
    st.success(f"Mesaj de la backend: {data['message']}")
    st.info(f"Timpul curent de la server: {data['current_time']}")
except Exception as e:
    st.error(f"Nu s-a putut conecta la backend: {e}")
