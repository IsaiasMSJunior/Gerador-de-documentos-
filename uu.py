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

# OBS: adicione 'firebase-admin' em requirements.txt

# --- Inicialização do Firebase ---
service_account_info = json.loads(st.secrets["firebase_key"])
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred, {
    "databaseURL": st.secrets["databaseURL"]
})

st.set_page_config(page_title="Agenda Escolar", layout="wide")

# --- Helpers e Configurações Gerais ---
map_hor = {
    "1ª": "7:00–7:50", "2ª": "7:50–8:40", "3ª": "8:40–9:30",
    "4ª": "9:50–10:40", "5ª": "10:40–11:30", "6ª": "12:20–13:10", "7ª": "13:10–14:00"
}
meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
ano_planej = 2025

def get_db(path, default):
    data = db.reference(path).get()
    return data if data is not None else default


def set_db(path, value):
    db.reference(path).set(value)


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
        ws[f"{col}{row+1}"] = (
            f"Aula {e['num']} – " +
            df_bank.loc[
                (df_bank["DISCIPLINA"]==e["disciplina"]) &
                (df_bank["ANO/SÉRIE"]==extrai_serie(e["turma"])) &
                (df_bank["BIMESTRE"]==bimestre) &
                (df_bank["Nº da aula"]==e["num"]),
            ]["TÍTULO DA AULA"].iloc[0]
            if not df_bank.empty else ""
        )
        ws[f"{col}{row+1}"].fill = fill
    out = BytesIO(); wb.save(out); out.seek(0)
    return out


def gerar_plano_template(entries, df_bank, professor, semana, bimestre, turma,
                         metodologias, recursos, criterios, modelo="modelo_plano.docx"):
    doc = Document(modelo)
    header_disciplinas = ", ".join(sorted({e['disciplina'] for e in entries}))
    total_aulas = str(len(entries))
    # Cabeçalho
    for p in doc.paragraphs:
        p.text = (p.text
                  .replace("ppp", professor)
                  .replace("ttt", turma)
                  .replace("sss", semana)
                  .replace("ddd", header_disciplinas)
                  .replace("nnn", total_aulas))
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.text = (p.text
                              .replace("ppp", professor)
                              .replace("ttt", turma)
                              .replace("sss", semana)
                              .replace("ddd", header_disciplinas)
                              .replace("nnn", total_aulas))
    # Blocos de aula + extras
    for p in doc.paragraphs:
        if p.text.strip() == "ccc":
            p.text = ""; last = p
            b0 = insert_after(last); set_border(b0); last = b0
            last = insert_after(last, "")
            for e in entries:
                sub = df_bank.loc[
                    (df_bank["DISCIPLINA"]==e["disciplina"]) &
                    (df_bank["ANO/SÉRIE"]==extrai_serie(turma)) &
                    (df_bank["BIMESTRE"]==bimestre) &
                    (df_bank["Nº da aula"]==e["num"])
                ]
                titulo = sub["TÍTULO DA AULA"].iloc[0] if not sub.empty else ""
                hab    = sub["HABILIDADE"].iloc[0]        if not sub.empty else ""
                cnt    = sub["CONTEÚDO"].iloc[0]         if not sub.empty else ""
                pa = insert_after(last, f"Aula {e['num']} – {titulo}"); pa.runs[0].bold=True; last=pa
                last = insert_after(last, "")
                ph = insert_after(last); rh=ph.add_run("Habilidade: "); rh.underline=True; ph.add_run(hab); last=ph
                last = insert_after(last, "")
                pc = insert_after(last); rc=pc.add_run("Conteúdo: "); rc.underline=True; pc.add_run(cnt); last=pc
                last = insert_after(last, "")
                b1 = insert_after(last); set_border(b1); last=b1
                last = insert_after(last, "")
            if metodologias:
                pm = insert_after(last); pm.add_run("Metodologia:").bold=True; last=pm
                for m in metodologias: last=insert_after(last, f"• {m}")
                last=insert_after(last, "")
            if recursos:
                pr = insert_after(last); pr.add_run("Recursos:").bold=True; last=pr
                for r in recursos: last=insert_after(last, f"• {r}")
                last=insert_after(last, "")
            if criterios:
                pc2 = insert_after(last); pc2.add_run("Critérios de Avaliação:").bold=True; last=pc2
                for c in criterios: last=insert_after(last, f"• {c}")
            break
    out = BytesIO(); doc.save(out); out.seek(0)
    return out


def gerar_guia_template(professor, turma, disciplina, bimestre, inicio, fim,
                        qtd_bimestre, qtd_semanal, metodologias, criterios,
                        df_bank, modelo="modelo_guia.docx"):
    doc = Document(modelo)
    reps = {
        'ppp': professor,
        'ttt': turma,
        'bbb': bimestre,
        'iii': inicio.strftime('%d/%m/%Y'),
        'fff': fim.strftime('%d/%m/%Y'),
        'qqq': str(qtd_bimestre),
        'sss': str(qtd_semanal),
        'mmm': ", ".join(metodologias),
        'ccc': ", ".join(criterios),
        'ddd': disciplina
    }
    for p in doc.paragraphs:
        for k,v in reps.items():
            if k in p.text: p.text = p.text.replace(k,v)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for k,v in reps.items():
                        if k in p.text: p.text = p.text.replace(k,v)
    mask = (
        (df_bank["DISCIPLINA"]==disciplina)&
        (df_bank["ANO/SÉRIE"]==extrai_serie(turma))&
        (df_bank["BIMESTRE"]==bimestre)
    )
    habs = df_bank.loc[mask, "HABILIDADE"].dropna().astype(str).tolist()
    objs = df_bank.loc[mask, "OBJETO DE CONHECIMENTO"].dropna().astype(str).tolist()
    unique_habs, unique_objs = [], []
    for h in habs:
        if h not in unique_habs: unique_habs.append(h)
    for o in objs:
        if o not in unique_objs: unique_objs.append(o)
    for p in doc.paragraphs:
        if 'hhh' in p.text: p.text = "\n".join(unique_habs)
        if 'ooo' in p.text: p.text = "\n".join(unique_objs)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if 'hhh' in p.text: p.text = "\n".join(unique_habs)
                    if 'ooo' in p.text: p.text = "\n".join(unique_objs)
    out = BytesIO(); doc.save(out); out.seek(0)
    return out


def gerar_planejamento_template(professor, disciplina, turma, bimestre,
                                grupos, df_bank, modelo="modelo_planejamento.docx"):
    doc = Document(modelo)
    hdr = {'ppp':professor,'ddd':disciplina,'ttt':turma,'bbb':bimestre}
    for p in doc.paragraphs:
        for k,v in hdr.items():
            if k in p.text: p.text = p.text.replace(k,v)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row},{"pattern":".*
