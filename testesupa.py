import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import uuid
import ast

# --- CONFIGURAÇÃO DO FIREBASE ---

# Carrega a chave do Firebase do secrets
firebase_key = ast.literal_eval(st.secrets["FIREBASE_KEY"])

# Inicializa o Firebase (somente uma vez)
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, {
        'databaseURL': st.secrets["DATABASE_URL"]  # Pegando também do secrets (URL do Realtime Database)
    })

# --- INTERFACE DO USUÁRIO ---

st.title("Inserir Dados no Firebase")

# Input de texto
texto = st.text_input("Digite algo:")

# Botão de inserir
if st.button("Inserir"):
    if texto.strip() != "":
        # Cria um ID único para o dado
        id_dado = str(uuid.uuid4())

        # Referência ao local no banco de dados
        ref = db.reference('dados')

        # Envia o dado
        ref.child(id_dado).set({
            "texto": texto
        })

        st.success("Texto inserido com sucesso!")
    else:
        st.warning("Por favor, digite algo antes de inserir.")
