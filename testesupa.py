import streamlit as st
from supabase import create_client, Client

# ------------------------------
# CONFIGURAÇÃO DO SUPABASE
# ------------------------------

# Carrega as informações secretas do arquivo .streamlit/secrets.toml (local)
# ou do painel de Secrets do Streamlit Cloud (produção)
supabase_url: str = st.secrets["SUPABASE_URL"]
supabase_key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

# ------------------------------
# LAYOUT DO STREAMLIT
# ------------------------------

# Título da página
st.title("📥 Inserir dados no Supabase")

# Caixa de entrada centralizada
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    texto = st.text_input("Digite o texto que deseja salvar:")

    # Botão para inserir o texto
    if st.button("Inserir"):
        if texto.strip() == "":
            st.warning("⚠️ O campo de texto não pode estar vazio.")
        else:
            # Insere o texto na tabela "entries"
            resultado = supabase.table("entries").insert({"text": texto}).execute()

            # Verifica o resultado
            if resultado.error:
                st.error(f"❌ Erro ao inserir: {resultado.error.message}")
            else:
                st.success("✅ Texto inserido com sucesso no Supabase!")

# ------------------------------
# EXIBIR OS TEXTOS JÁ INSERIDOS
# ------------------------------

st.write("---")
st.header("📄 Textos já inseridos:")

# Busca todos os registros da tabela "entries"
dados = supabase.table("entries").select("*").order("id", desc=True).execute()

if dados.data:
    for item in dados.data:
        st.write(f"➡️ {item['text']}")
else:
    st.info("Ainda não há registros na tabela.")
