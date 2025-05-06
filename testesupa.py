import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import uuid
import json

# --- INICIALIZAR FIREBASE ---
if not firebase_admin._apps:
    firebase_key = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, {
        'databaseURL': st.secrets["DATABASE_URL"]
    })

ref = db.reference('dados')

# --- TÍTULO ---
st.markdown("# 📝 CRUD com Firebase + Streamlit")
st.markdown("Este é um exemplo de CRUD completo com visual mais bonito e organizado.")

st.divider()

# --- INSERIR NOVO DADO ---
st.header("➕ Inserir Novo Texto")

novo_texto = st.text_input("Digite algo novo:")

col1, col2 = st.columns([2, 1])
with col1:
    pass
with col2:
    if st.button("✅ Inserir"):
        if novo_texto.strip() != "":
            id_dado = str(uuid.uuid4())
            ref.child(id_dado).set({
                "texto": novo_texto
            })
            st.success("Texto inserido com sucesso!")
            st.experimental_rerun()
        else:
            st.warning("Digite algo para inserir.")

st.divider()

# --- LISTAR TODOS OS DADOS ---
st.header("📋 Mural de Textos Salvos")

dados = ref.get()

if dados:
    for id_dado, dado in dados.items():
        texto_atual = dado.get("texto", "")

        with st.container():
            st.markdown(f"**ID:** `{id_dado}`")
            st.write(f"📌 **Texto atual:** {texto_atual}")

            col1, col2 = st.columns(2)

            # --- EDITAR ---
            with col1:
                novo_valor = st.text_input("Editar texto:", value=texto_atual, key=f"edit_{id_dado}")
                if st.button("💾 Salvar Alteração", key=f"salvar_{id_dado}"):
                    ref.child(id_dado).update({
                        "texto": novo_valor
                    })
                    st.success("Texto atualizado com sucesso!")
                    st.experimental_rerun()

            # --- DELETAR ---
            with col2:
                if st.button("🗑️ Excluir", key=f"excluir_{id_dado}"):
                    confirm = st.radio("Tem certeza que deseja excluir?", ["Não", "Sim"], key=f"confirma_{id_dado}")
                    if confirm == "Sim":
                        ref.child(id_dado).delete()
                        st.warning("Texto excluído com sucesso.")
                        st.experimental_rerun()

            st.markdown("---")
else:
    st.info("Nenhum dado salvo ainda.")
