import streamlit as st
import json
import requests
import firebase_admin
from firebase_admin import credentials, auth, db
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

# Configuração inicial da página
st.set_page_config(page_title="Agenda Escolar", layout="wide")

# --- Carregando configurações do Firebase ---
if "firebase" in st.secrets:
    service_account_info = json.loads(st.secrets["firebase"]["serviceAccount"])
    database_url = st.secrets["firebase"]["databaseURL"]
    api_key = st.secrets["firebase"]["apiKey"]
else:
    with open("serviceAccountKey.json", encoding="utf-8") as f:
        service_account_info = json.load(f)
    database_url = "https://gerador-de-documentos-ce501-default-rtdb.firebaseio.com/"
    api_key = "AIzaSyB56d5ExrV7i4cwqnguqmf-VJykiBNqbD4"

# --- Inicialização do Firebase Admin SDK ---
if not firebase_admin._apps:
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred, {"databaseURL": database_url})

# --- Sistema de Autenticação (Email/Senha) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login_tab, register_tab = st.tabs(["Login", "Registrar"])
    with login_tab:
        st.header("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")
        if st.button("Entrar"):
            payload = {"email": email, "password": password, "returnSecureToken": True}
            res = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
                json=payload
            )
            if res.status_code == 200:
                st.session_state.authenticated = True
                st.session_state.user = email
                st.success("Login bem-sucedido!")
                st.experimental_rerun()
            else:
                err = res.json().get("error", {}).get("message", "Falha no login")
                st.error(f"Login falhou: {err}")
    with register_tab:
        st.header("Registrar")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Senha", type="password", key="reg_password")
        if st.button("Registrar"):
            try:
                auth.create_user(email=reg_email, password=reg_password)
                st.success("Usuário registrado! Faça login.")
            except Exception as e:
                st.error(f"Erro ao registrar: {e}")
    st.stop()

# --- Funções para CRUD no Realtime Database ---
def carregar_json(nome):
    key = nome.replace(".json", "")
    data = db.reference(key).get()
    if data is None:
        return [] if nome in ["professores.json", "horarios.json"] else {}
    if isinstance(data, dict) and all(k.isdigit() for k in data.keys()):
        return [data[k] for k in sorted(data.keys(), key=int)]
    return data

def salvar_json(nome, conteudo):
    key = nome.replace(".json", "")
    db.reference(key).set(conteudo)

# --- Helpers e Configurações Gerais ---
map_hor = {"1ª":"7:00–7:50","2ª":"7:50–8:40","3ª":"8:40–9:30",
           "4ª":"9:50–10:40","5ª":"10:40–11:30","6ª":"12:20–13:10","7ª":"13:10–14:00"}
meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
ano_planej = 2025

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
        cell1 = ws[f"{col}{row}"]
        cell1.value = f"{e['turma']} – {e['disciplina']}"
        color = cores_turmas.get(e['turma'], '#FFFFFF').lstrip('#')
        fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        cell1.fill = fill
        title = ""
        if not df_bank.empty:
            sub = df_bank.loc[
                (df_bank["DISCIPLINA"]==e["disciplina"]) &
                (df_bank["ANO/SÉRIE"]==extrai_serie(e["turma"])) &
                (df_bank["BIMESTRE"]==bimestre) &
                (df_bank["Nº da aula"]==e["num"]),
                "TÍTULO DA AULA"
            ]
            if not sub.empty:
                title = sub.iloc[0]
        cell2 = ws[f"{col}{row+1}"]
        cell2.value = f"Aula {e['num']} – {title}"
        cell2.fill = fill
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def gerar_plano_template(entries, df_bank, professor, semana, bimestre, turma,
                         metodologias, recursos, criterios, modelo="modelo_plano.docx"):
    doc = Document(modelo)
    header_disc = ", ".join(sorted({e['disciplina'] for e in entries}))
    total = str(len(entries))
    for p in doc.paragraphs:
        p.text = p.text.replace("ppp", professor).replace("ttt", turma)
        p.text = p.text.replace("sss", semana).replace("ddd", header_disc).replace("nnn", total)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.text = p.text.replace("ppp", professor).replace("ttt", turma)
                    p.text = p.text.replace("sss", semana).replace("ddd", header_disc).replace("nnn", total)
    for p in doc.paragraphs:
        if p.text.strip() == "ccc":
            p.text = ""
            last = p
            for e in entries:
                sub = df_bank.loc[
                    (df_bank["DISCIPLINA"]==e['disciplina']) &
                    (df_bank["ANO/SÉRIE"]==extrai_serie(turma)) &
                    (df_bank["BIMESTRE"]==bimestre) &
                    (df_bank["Nº da aula"]==e['num'])
                ]
                titulo = sub["TÍTULO DA AULA"].iloc[0] if not sub.empty else ""
                hab = sub["HABILIDADE"].iloc[0] if not sub.empty else ""
                cnt = sub["CONTEÚDO"].iloc[0] if not sub.empty else ""
                pa = insert_after(last, f"Aula {e['num']} – {titulo}")
                pa.runs[0].bold = True
                last = pa
                insert_after(last, f"Habilidade: {hab}")
                insert_after(last, f"Conteúdo: {cnt}")
            if metodologias:
                insert_after(last, "Metodologia:")
                for m in metodologias:
                    insert_after(last, f"• {m}")
            if recursos:
                insert_after(last, "Recursos:")
                for r in recursos:
                    insert_after(last, f"• {r}")
            if criterios:
                insert_after(last, "Critérios de Avaliação:")
                for c in criterios:
                    insert_after(last, f"• {c}")
            break
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out


def gerar_guia_template(professor, turma, disciplina, bimestre, inicio, fim,
                        qtd_bim, qtd_sem, metodologias, criterios, df_bank,
                        modelo="modelo_guia.docx"):
    doc = Document(modelo)
    reps = {
        'ppp': professor,
        'ttt': turma,
        'bbb': bimestre,
        'iii': inicio.strftime('%d/%m/%Y'),
        'fff': fim.strftime('%d/%m/%Y'),
        'qqq': str(qtd_bim),
        'sss': str(qtd_sem)
    }
    for k, v in reps.items():
        for p in doc.paragraphs:
            if k in p.text:
                p.text = p.text.replace(k, v)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if k in p.text:
                            p.text = p.text.replace(k, v)
    mask = (
        (df_bank["DISCIPLINA"]==disciplina) &
        (df_bank["ANO/SÉRIE"]==extrai_serie(turma)) &
        (df_bank["BIMESTRE"]==bimestre)
    )
    habs = list(dict.fromkeys(df_bank.loc[mask, "HABILIDADE"].dropna().astype(str).tolist()))
    objs = list(dict.fromkeys(df_bank.loc[mask, "OBJETO DE CONHECIMENTO"].dropna().astype(str).tolist()))
    for p in doc.paragraphs:
        if 'hhh' in p.text:
            p.text = "\n".join(habs)
        if 'ooo' in p.text:
            p.text = "\n".join(objs)
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out


def gerar_planejamento_template(professor, disciplina, turma, bimestre,
                                grupos, df_bank, modelo="modelo_planejamento.docx"):
    doc = Document(modelo)
    hdr = {'ppp':professor,'ddd':disciplina,'ttt':turma,'bbb':bimestre}
    for k, v in hdr.items():
        for p in doc.paragraphs:
            if k in p.text:
                p.text = p.text.replace(k, v)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if k in p.text:
                            p.text = p.text.replace(k, v)
    for grp in grupos:
        doc.add_paragraph(f"Semana: {grp['semana']}")
        doc.add_paragraph(f"Aulas previstas: {grp['prev']}")
        for n in grp['nums']:
            titles = df_bank.loc[
                (df_bank["DISCIPLINA"]==disciplina) &
                (df_bank["ANO/SÉRIE"]==extrai_serie(turma)) &
                (df_bank["BIMESTRE"]==bimestre) &
                (df_bank["Nº da aula"]==n),
                "TÍTULO DA AULA"
            ].dropna().tolist()
            title = titles[0] if titles else ""
            doc.add_paragraph(f"Aula {n} – {title}")
        doc.add_paragraph(f"Metodologia: {', '.join(grp['met'])}")
        doc.add_paragraph(f"Critérios: {', '.join(grp['crit'])}")
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# --- Inicialização de estado ---
if "extras" not in st.session_state:
    extras = carregar_json("extras.json") or {}
    extras.setdefault("metodologia", [])
    extras.setdefault("recursos", [])
    extras.setdefault("criterios", [])
    st.session_state.extras = extras

if "pagina" not in st.session_state:
    st.session_state.pagina = "Cadastro de Professor"
if "professores" not in st.session_state:
    st.session_state.professores = carregar_json("professores.json") or []
if "turmas" not in st.session_state:
    st.session_state.turmas = carregar_json("turmas.json") or {}
if "horarios" not in st.session_state:
    st.session_state.horarios = carregar_json("horarios.json") or []

# --- Sidebar e páginas ---
pages = [
    "Cadastro de Professor","Cadastro de Turmas","Cadastro de Horário",
    "Gerar Agenda e Plano","Cadastro Extras","Gerar Guia",
    "Gerar Planejamento Bimestral"
]
for p in pages:
    if st.sidebar.button(p, use_container_width=True):
        st.session_state.pagina = p
    st.sidebar.markdown("\n")

# 1. Cadastro de Professor
if st.session...
