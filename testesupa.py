import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import uuid

# --- INICIALIZAR FIREBASE ---
if not firebase_admin._apps:
    firebase_key = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, {
        'databaseURL': st.secrets["DATABASE_URL"]
    })

usuarios_ref = db.reference('usuarios')

st.title("🔐 Sistema de Login Simples + CRUD")

# --- AUTENTICAÇÃO ---

if "usuario_logado" not in st.session_state:
    menu = st.sidebar.selectbox("Escolha uma opção", ["Login", "Cadastrar"])

    if menu == "Cadastrar":
        st.subheader("📌 Cadastro de Usuário")
        novo_usuario = st.text_input("Novo usuário")
        nova_senha = st.text_input("Nova senha", type="password")
        if st.button("Cadastrar"):
            if novo_usuario.strip() != "" and nova_senha.strip() != "":
                # Verifica se já existe
                if usuarios_ref.child(novo_usuario).get() is None:
                    usuarios_ref.child(novo_usuario).set({
                        "senha": nova_senha
                    })
                    st.success("Usuário cadastrado com sucesso!")
                else:
                    st.warning("Usuário já existe.")
            else:
                st.warning("Preencha usuário e senha.")

    elif menu == "Login":
        st.subheader("🔑 Login")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            dados_usuario = usuarios_ref.child(usuario).get()
            if dados_usuario and dados_usuario.get("senha") == senha:
                st.session_state.usuario_logado = usuario
                st.success("Login realizado com sucesso!")
                st.experimental_rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    # --- USUÁRIO AUTENTICADO ---
    usuario = st.session_state.usuario_logado
    st.sidebar.success(f"Logado como {usuario}")

    if st.sidebar.button("Sair"):
        del st.session_state.usuario_logado
        st.experimental_rerun()

    # --- CRUD ---
    st.header("➕ Inserir novo texto")
    novo_texto = st.text_input("Digite algo novo:")

    user_ref = db.reference(f'dados/{usuario}')

    if st.button("Inserir"):
        if novo_texto.strip() != "":
            id_dado = str(uuid.uuid4())
            user_ref.child(id_dado).set({
                "texto": novo_texto
            })
            st.success("Texto inserido com sucesso!")
            st.experimental_rerun()
        else:
            st.warning("Digite algo para inserir.")

    st.divider()
    st.header("📋 Seus textos salvos:")

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
