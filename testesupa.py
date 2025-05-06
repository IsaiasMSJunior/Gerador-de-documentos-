import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, db
import requests

# Inicialização do Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://<SEU-PROJETO>.firebaseio.com/'
    })

st.title("Sistema de Login com Firebase")

# Função para registrar um novo usuário
def registrar_usuario(email, senha):
    try:
        user = auth.create_user(email=email, password=senha)
        st.success("Usuário registrado com sucesso!")
    except Exception as e:
        st.error(f"Erro ao registrar: {e}")

# Função para autenticar usuário
def autenticar_usuario(email, senha):
    try:
        payload = {
            "email": email,
            "password": senha,
            "returnSecureToken": True
        }
        api_key = "<SUA_API_KEY_DO_FIREBASE>"
        req = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}", data=payload)
        if req.status_code == 200:
            st.success("Login realizado com sucesso!")
            return True
        else:
            st.error("Credenciais inválidas.")
            return False
    except Exception as e:
        st.error(f"Erro ao autenticar: {e}")
        return False

# Interface de Login e Registro
menu = ["Login", "Registrar"]
escolha = st.selectbox("Menu", menu)

if escolha == "Registrar":
    st.subheader("Criar nova conta")
    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")
    if st.button("Registrar"):
        registrar_usuario(email, senha)

elif escolha == "Login":
    st.subheader("Acessar conta")
    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")
    if st.button("Login"):
        if autenticar_usuario(email, senha):
            st.session_state['autenticado'] = True

# Se autenticado, mostrar funcionalidades CRUD
if st.session_state.get('autenticado'):
    st.subheader("Funcionalidades CRUD")
    # Aqui você pode adicionar as funcionalidades de criar, ler, atualizar e deletar dados no Firebase Realtime Database
    # Exemplo: Criar um novo dado
    nome = st.text_input("Nome")
    idade = st.number_input("Idade", min_value=0)
    if st.button("Salvar"):
        try:
            ref = db.reference('/usuarios')
            ref.push({
                'nome': nome,
                'idade': idade
            })
            st.success("Dados salvos com sucesso!")
        except Exception as e:
            st.error(f"Erro ao salvar dados: {e}")
