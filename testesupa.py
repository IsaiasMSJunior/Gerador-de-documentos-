import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from google.oauth2 import id_token
from google.auth.transport import requests
import uuid
import json
import urllib.parse

# --- CONFIGURAR FIREBASE ---
if not firebase_admin._apps:
    firebase_key = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, {
        'databaseURL': st.secrets["DATABASE_URL"]
    })

# --- AUTENTICAÇÃO COM GOOGLE ---
CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]

st.title("🔐 Login com Google + CRUD no Firebase")

# Passo 1 - Botão para iniciar login
login_url = (
    "https://accounts.google.com/o/oauth2/v2/auth"
    "?response_type=token"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(st.secrets['REDIRECT_URI'])}"
    "&scope=email%20profile"
)

if "user" not in st.session_state:
    st.markdown("### 👤 Faça login para continuar")
    st.markdown(f"[Clique aqui para logar com o Google]({login_url})")

    # Capturar token da URL após o login
    token = st.experimental_get_query_params().get("access_token", [None])[0]

    if token:
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
            st.session_state.user = {
                "name": idinfo["name"],
                "email": idinfo["email"],
                "sub": idinfo["sub"]
            }
            st.experimental_rerun()
        except Exception as e:
            st.error("Erro ao autenticar.")
else:
    # Usuário autenticado
    user = st.session_state.user
    st.success(f"✅ Logado como {user['name']} ({user['email']})")
    
    # Botão de logout
    if st.button("Sair"):
        del st.session_state.user
        st.experimental_rerun()

    # --- CRUD ---
    st.header("➕ Inserir novo texto")

    novo_texto = st.text_input("Digite algo novo:")

    if st.button("Inserir"):
        if novo_texto.strip() != "":
            id_dado = str(uuid.uuid4())
            user_ref = db.reference(f'dados/{user["sub"]}')
            user_ref.child(id_dado).set({
                "texto": novo_texto
            })
            st.success("Texto inserido com sucesso!")
            st.experimental_rerun()
        else:
            st.warning("Digite algo para inserir.")

    st.divider()
    st.header("📋 Seus textos salvos:")

    user_ref = db.reference(f'dados/{user["sub"]}')
    dados = user_ref.get()

    if dados:
        for id_dado, dado in dados.items():
            with st.container():
                st.write(f"ID: `{id_dado}`")
                st.write(f"📌 **Texto atual:** {dado.get('texto', '')}")

                col1, col2 = st.columns(2)

                with col1:
                    novo_valor = st.text_input("Editar texto:", value=dado.get('texto', ''), key=f"edit_{id_dado}")
                    if st.button("💾 Salvar Alteração", key=f"salvar_{id_dado}"):
                        user_ref.child(id_dado).update({
                            "texto": novo_valor
                        })
                        st.success("Texto atualizado com sucesso!")
                        st.experimental_rerun()

                with col2:
                    if st.button("🗑️ Excluir", key=f"excluir_{id_dado}"):
                        user_ref.child(id_dado).delete()
                        st.warning("Texto excluído.")
                        st.experimental_rerun()
    else:
        st.info("Nenhum texto salvo ainda.")
