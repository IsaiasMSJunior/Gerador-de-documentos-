import streamlit as st
import json
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import calendar
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from datetime import datetime
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

# Adicione 'firebase-admin' em requirements.txt

# --- Inicialização do Firebase ---
# Carrega a chave de serviço do secrets.toml
secret_key_raw = None
if "firebase_key" in st.secrets:
    secret_key_raw = st.secrets["firebase_key"]
elif "firebase" in st.secrets and "firebase_key" in st.secrets["firebase"]:
    secret_key_raw = st.secrets["firebase"]["firebase_key"]
else:
    st.error("Chave de serviço do Firebase não encontrada em secrets do Streamlit Cloud.")
    st.stop()

# Converte JSON em dict, ou usa diretamente se já for dict
if isinstance(secret_key_raw, dict):
    service_account_info = secret_key_raw
else:
    try:
        service_account_info = json.loads(secret_key_raw)
    except Exception as e:
        st.error(f"Erro ao decodificar JSON da chave do Firebase: {e}")
        st.text(secret_key_raw)
        st.stop()

cred = credentials.Certificate(service_account_info)

# Carrega o databaseURL
if "databaseURL" in st.secrets:
    database_url = st.secrets["databaseURL"]
elif "firebase" in st.secrets and "databaseURL" in st.secrets["firebase"]:
    database_url = st.secrets["firebase"]["databaseURL"]
else:
    st.error("databaseURL não encontrada em secrets do Streamlit Cloud.")
    st.stop()

firebase_admin.initialize_app(cred, {"databaseURL": database_url})

# Configuração da página
st.set_page_config(page_title="Agenda Escolar", layout="wide")

# --- Helpers e Configurações Gerais ---
map_hor = {
    "1ª": "7:00–7:50", "2ª": "7:50–8:40", "3ª": "8:40–9:30",
    "4ª": "9:50–10:40", "5ª": "10:40–11:30", "6ª": "12:20–13:10", "7ª": "13:10–14:00"
}
meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
ano_planej = 2025

# Funções para interação com Realtime Database

def get_db(path, default):
    data = db.reference(path).get()
    return data if data is not None else default


def set_db(path, value):
    db.reference(path).set(value)

# Funções auxiliares

def extrai_serie(turma: str) -> str:
    return turma[:-1]


def set_border(par: Paragraph):
    p = par._p
    pPr = p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bd = OxmlElement('w:bottom')
    bd.set(qn('w:val'),'single'); bd.set(qn('w:sz'),'4')
    bd.set(qn('w:space'),'1'); bd.set(qn('w:color'),'auto')
    pBdr.append(bd); pPr.append(pBdr)


def insert_after(par: Paragraph, text='') -> Paragraph:
    new_p = OxmlElement('w:p'); par._p.addnext(new_p)
    para = Paragraph(new_p, par._parent)
    if text: para.add_run(text)
    return para

# --- Funções de geração de documentos ---

def gerar_agenda_template(entries, df_bank, professor, semana, bimestre, cores_turmas):
    wb = load_workbook("agenda_modelo.xlsx")
    ws = wb.active
    ws["B1"] = professor
    ws["E1"] = semana
    row_map = {"1ª":4, "2ª":6, "3ª":8, "4ª":12, "5ª":14, "6ª":18, "7ª":20}
    col_map = {"Segunda":"C", "Terça":"D", "Quarta":"E", "Quinta":"F", "Sexta":"G"}
    for e in entries:
        col, row = col_map[e["dia"]], row_map[e["aula"]]
        ws[f"{col}{row}"] = f"{e['turma']} – {e['disciplina']}"
        fill = PatternFill(
            start_color=cores_turmas.get(e["turma"], "#FFFFFF").lstrip("#"),
            end_color=cores_turmas.get(e["turma"], "#FFFFFF").lstrip("#"),
            fill_type="solid"
        )
        ws[f"{col}{row}"].fill = fill
        titulo = ""
        if not df_bank.empty:
            sel = df_bank[
                (df_bank["DISCIPLINA"]==e["disciplina"]) &
                (df_bank["ANO/SÉRIE"]==extrai_serie(e["turma"])) &
                (df_bank["BIMESTRE"]==bimestre) &
                (df_bank["Nº da aula"]==e["num"])
            ]
            if not sel.empty:
                titulo = sel["TÍTULO DA AULA"].iloc[0]
        ws[f"{col}{row+1}"] = f"Aula {e['num']} – {titulo}"
        ws[f"{col}{row+1}"].fill = fill
    out = BytesIO(); wb.save(out); out.seek(0)
    return out

# --- Páginas ---
if st.session_state.get('page') == "Cadastro de Professor":
    st.header("Cadastro de Professor")
    nome = st.text_input("Nome")
    disciplinas = st.multiselect("Disciplina(s)", [...])  # defina opções completas
    if st.button("Salvar Professor"):
        st.session_state.professores.append({"nome":nome,"disciplinas":disciplinas})
        set_db("professores", st.session_state.professores)
        st.success("Professor salvo!")
    st.write(st.session_state.professores)

elif st.session_state.get('page') == "Cadastro de Turmas":
    st.header("Cadastro de Turmas")
    # similar ao cadastro original, use set_db para salvar

elif st.session_state.get('page') == "Cadastro de Horário":
    st.header("Cadastro de Horário")
    # estrutura de horários, on button save: set_db("horarios", st.session_state.horarios)

elif st.session_state.get('page') == "Gerar Agenda e Plano":
    st.header("Gerar Agenda e Plano")
    # lógica igual, usa gerar_agenda_template e gerar_plano_template

elif st.session_state.get('page') == "Cadastro Extras":
    st.header("Cadastro Extras")
    # use set_db para atualizar extras

elif st.session_state.get('page') == "Gerar Guia":
    st.header("Gerar Guia")
    # lógica gerar_guia_template

elif st.session_state.get('page') == "Planejamento Bimestral":
    st.header("Planejamento Bimestral")
    # lógica gerar_planejamento_template
