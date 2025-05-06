import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json
import uuid

# === INICIALIZAR FIREBASE ===
if not firebase_admin._apps:
    firebase_key = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, {
        'databaseURL': st.secrets["DATABASE_URL"]
    })

usuarios_ref = db.reference('usuarios')

st.set_page_config(page_title="Agenda Escolar", layout="wide")

st.title("🔐 Login + Cadastro de Usuário + CRUD")

# === AUTENTICAÇÃO ===
if "usuario_logado" not in st.session_state:
    menu = st.sidebar.selectbox("Escolha uma opção", ["Login", "Cadastrar"])

    if menu == "Cadastrar":
        st.subheader("📌 Cadastro de Usuário")
        novo_usuario = st.text_input("Novo usuário")
        nova_senha = st.text_input("Nova senha", type="password")
        if st.button("Cadastrar"):
            if novo_usuario.strip() != "" and nova_senha.strip() != "":
                if usuarios_ref.child(novo_usuario).get() is None:
                    usuarios_ref.child(novo_usuario).set({"senha": nova_senha})
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
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    usuario = st.session_state.usuario_logado
    st.sidebar.success(f"Logado como {usuario}")

    if st.sidebar.button("Sair"):
        del st.session_state.usuario_logado
        st.rerun()

    # === DADOS DO USUÁRIO (BANCO) ===
    user_ref = db.reference(f'dados/{usuario}')
    dados = user_ref.get() or {}

    def salvar_dados(chave, valor):
        user_ref.child(chave).set(valor)

    # === INICIALIZAR DADOS PADRÃO ===
    if "extras" not in dados:
        salvar_dados("extras", {"metodologia": [], "recursos": [], "criterios": []})
    if "professores" not in dados:
        salvar_dados("professores", [])
    if "turmas" not in dados:
        salvar_dados("turmas", {})
    if "horarios" not in dados:
        salvar_dados("horarios", [])

    dados = user_ref.get()

    # === MENU ===
    pages = [
        "Cadastro de Professor","Cadastro de Turmas","Cadastro de Horário",
        "Cadastro Extras"
    ]
    pagina = st.sidebar.radio("Menu", pages)

    # === CADASTRO PROFESSORES ===
    if pagina == "Cadastro de Professor":
        st.header("Cadastro de Professor")
        nome = st.text_input("Nome")
        disciplinas = st.multiselect("Disciplinas", ["Português","Matemática","História","Geografia","Ciências","Arte","Inglês","Ed. Física"])
        if st.button("Salvar Professor"):
            dados["professores"].append({"nome": nome, "disciplinas": disciplinas})
            salvar_dados("professores", dados["professores"])
            st.success("Salvo com sucesso!")

        for p in dados["professores"]:
            st.write(f"{p['nome']} — {', '.join(p['disciplinas'])}")

    # === CADASTRO TURMAS ===
    elif pagina == "Cadastro de Turmas":
        st.header("Cadastro de Turmas")
        turmas = dados["turmas"]
        turma = st.text_input("Nome da Turma")
        cor = st.color_picker("Cor")
        if st.button("Salvar Turma"):
            turmas[turma] = cor
            salvar_dados("turmas", turmas)
            st.success("Turma salva!")

        for t, c in turmas.items():
            st.write(f"{t} → {c}")

    # === CADASTRO HORÁRIOS ===
    elif pagina == "Cadastro de Horário":
        st.header("Cadastro de Horário")
        horarios = dados["horarios"]
        if st.button("Adicionar Linha"):
            horarios.append({"turma": None, "disciplina": None, "dia": None, "aula": None})
            salvar_dados("horarios", horarios)

        for i, h in enumerate(horarios):
            cols = st.columns(5)
            turmas = list(dados["turmas"].keys())
            disciplinas = sorted({d for p in dados["professores"] for d in p["disciplinas"]})
            dias = ["Segunda","Terça","Quarta","Quinta","Sexta"]
            aulas = ["1ª","2ª","3ª","4ª","5ª","6ª","7ª"]

            h['turma'] = cols[0].selectbox("Turma", turmas, index=turmas.index(h['turma']) if h['turma'] in turmas else 0, key=f"turma_{i}")
            h['disciplina'] = cols[1].selectbox("Disciplina", disciplinas, index=disciplinas.index(h['disciplina']) if h['disciplina'] in disciplinas else 0, key=f"disc_{i}")
            h['dia'] = cols[2].selectbox("Dia", dias, index=dias.index(h['dia']) if h['dia'] in dias else 0, key=f"dia_{i}")
            h['aula'] = cols[3].selectbox("Aula", aulas, index=aulas.index(h['aula']) if h['aula'] in aulas else 0, key=f"aula_{i}")

            if cols[4].button("X", key=f"del_{i}"):
                horarios.pop(i)
                salvar_dados("horarios", horarios)
                st.experimental_rerun()

        salvar_dados("horarios", horarios)

    # === CADASTRO EXTRAS ===
    elif pagina == "Cadastro Extras":
        st.header("Cadastro Extras")
        extras = dados["extras"]

        tab1, tab2, tab3 = st.tabs(["Metodologia","Recursos","Critérios de Avaliação"])

        with tab1:
            met = st.text_input("Metodologia")
            if st.button("Inserir Metodologia"):
                extras["metodologia"].append(met)
                salvar_dados("extras", extras)
                st.experimental_rerun()
            for i, m in enumerate(extras["metodologia"]):
                st.write(f"- {m}")

        with tab2:
            rec = st.text_input("Recurso")
            if st.button("Inserir Recurso"):
                extras["recursos"].append(rec)
                salvar_dados("extras", extras)
                st.experimental_rerun()
            for i, r in enumerate(extras["recursos"]):
                st.write(f"- {r}")

        with tab3:
            crit = st.text_input("Critério de Avaliação")
            if st.button("Inserir Critério"):
                extras["criterios"].append(crit)
                salvar_dados("extras", extras)
                st.experimental_rerun()
            for i, c in enumerate(extras["criterios"]):
                st.write(f"- {c}")
