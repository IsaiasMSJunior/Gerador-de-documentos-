import streamlit as st
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

# ------------------------------
# Configuração inicial da página
# ------------------------------
st.set_page_config(page_title="Agenda Escolar", layout="wide")

# ------------------------------
# Carregando configurações do Firebase
# ------------------------------
conf = st.secrets["firebase"]
service_account_info = conf["serviceAccount"]
api_key              = conf["apiKey"]
database_url         = conf["databaseURL"]

# Inicializa o Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred, {"databaseURL": database_url})

# ------------------------------
# Sistema de Autenticação (Email/Senha)
# ------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login_tab, register_tab = st.tabs(["Login", "Registrar"])
    with login_tab:
        st.header("Login")
        email    = st.text_input("Email", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")
        if st.button("Entrar"):
            payload = {"email": email, "password": password, "returnSecureToken": True}
            res = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
                json=payload
            )
            if res.status_code == 200:
                st.session_state.authenticated = True
                st.session_state.user          = email
                st.success("Login bem-sucedido!")
                st.experimental_rerun()
            else:
                err = res.json().get("error", {}).get("message", "Falha no login")
                st.error(f"Login falhou: {err}")
    with register_tab:
        st.header("Registrar")
        reg_email    = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Senha", type="password", key="reg_password")
        if st.button("Registrar"):
            try:
                auth.create_user(email=reg_email, password=reg_password)
                st.success("Usuário registrado! Agora faça login.")
            except Exception as e:
                st.error(f"Erro ao registrar: {e}")
    st.stop()

# ------------------------------
# Funções CRUD no Realtime Database
# ------------------------------
def carregar_json(nome):
    ref = db.reference(nome.replace(".json", ""))
    data = ref.get()
    if data is None:
        return [] if nome in ["professores.json", "horarios.json"] else {}
    if isinstance(data, dict) and all(k.isdigit() for k in data):
        return [data[k] for k in sorted(data.keys(), key=int)]
    return data

def salvar_json(nome, conteudo):
    db.reference(nome.replace(".json", "")).set(conteudo)

# ------------------------------
# Helpers e Configurações Gerais
# ------------------------------
map_hor = {
    "1ª":"7:00–7:50","2ª":"7:50–8:40","3ª":"8:40–9:30",
    "4ª":"9:50–10:40","5ª":"10:40–11:30","6ª":"12:20–13:10","7ª":"13:10–14:00"
}
meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
ano_planej = 2025

def extrai_serie(turma: str) -> str:
    return turma[:-1]

def set_border(par: Paragraph):
    p = par._p; pPr = p.get_or_add_pPr(); pBdr = OxmlElement("w:pBdr")
    bd = OxmlElement("w:bottom")
    bd.set(qn("w:val"),"single"); bd.set(qn("w:sz"),"4")
    bd.set(qn("w:space"),"1"); bd.set(qn("w:color"),"auto")
    pBdr.append(bd); pPr.append(pBdr)

def insert_after(par: Paragraph, text="") -> Paragraph:
    new_p = OxmlElement("w:p"); par._p.addnext(new_p)
    para = Paragraph(new_p, par._parent)
    if text: para.add_run(text)
    return para

# ------------------------------
# Funções de geração de documentos
# ------------------------------
def gerar_agenda_template(entries, df_bank, professor, semana, bimestre, cores_turmas):
    wb = load_workbook("agenda_modelo.xlsx"); ws = wb.active
    ws["B1"], ws["E1"] = professor, semana
    row_map = {"1ª":4,"2ª":6,"3ª":8,"4ª":12,"5ª":14,"6ª":18,"7ª":20}
    col_map = {"Segunda":"C","Terça":"D","Quarta":"E","Quinta":"F","Sexta":"G"}
    for e in entries:
        col,row = col_map[e["dia"]], row_map[e["aula"]]
        c1 = ws[f"{col}{row}"]; c1.value = f"{e['turma']} – {e['disciplina']}"
        color = cores_turmas.get(e["turma"],"#FFFFFF").lstrip("#")
        fill = PatternFill(start_color=color,end_color=color,fill_type="solid")
        c1.fill = fill
        title = ""
        if not df_bank.empty:
            sub = df_bank.loc[
                (df_bank["DISCIPLINA"]==e["disciplina"]) &
                (df_bank["ANO/SÉRIE"]==extrai_serie(e["turma"])) &
                (df_bank["BIMESTRE"]==bimestre) &
                (df_bank["Nº da aula"]==e["num"]),
                "TÍTULO DA AULA"
            ]
            if not sub.empty: title = sub.iloc[0]
        c2 = ws[f"{col}{row+1}"]; c2.value = f"Aula {e['num']} – {title}"; c2.fill = fill
    out = BytesIO(); wb.save(out); out.seek(0)
    return out

def gerar_plano_template(entries, df_bank, professor, semana, bimestre, turma,
                         metodologias, recursos, criterios, modelo="modelo_plano.docx"):
    doc = Document(modelo)
    header_disc = ", ".join(sorted({e["disciplina"] for e in entries}))
    total = str(len(entries))
    for p in doc.paragraphs:
        p.text = (p.text.replace("ppp",professor)
                       .replace("ttt",turma)
                       .replace("sss",semana)
                       .replace("ddd",header_disc)
                       .replace("nnn",total))
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.text = (p.text.replace("ppp",professor)
                                  .replace("ttt",turma)
                                  .replace("sss",semana)
                                  .replace("ddd",header_disc)
                                  .replace("nnn",total))
    for p in doc.paragraphs:
        if p.text.strip()=="ccc":
            p.text=""; last=p
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
                pa = insert_after(last,f"Aula {e['num']} – {titulo}"); pa.runs[0].bold=True; last=pa
                insert_after(last,f"Habilidade: {hab}")
                insert_after(last,f"Conteúdo: {cnt}")
            if metodologias:
                insert_after(last,"Metodologia:")
                for m in metodologias: insert_after(last,f"• {m}")
            if recursos:
                insert_after(last,"Recursos:")
                for r in recursos: insert_after(last,f"• {r}")
            if criterios:
                insert_after(last,"Critérios de Avaliação:")
                for c in criterios: insert_after(last,f"• {c}")
            break
    out = BytesIO(); doc.save(out); out.seek(0)
    return out

def gerar_guia_template(professor, turma, disciplina, bimestre, inicio, fim,
                        qtd_bim, qtd_sem, metodologias, criterios, df_bank,
                        modelo="modelo_guia.docx"):
    doc = Document(modelo)
    reps = {
        'ppp': professor, 'ttt': turma, 'bbb': bimestre,
        'iii': inicio.strftime('%d/%m/%Y'), 'fff': fim.strftime('%d/%m/%Y'),
        'qqq': str(qtd_bim), 'sss': str(qtd_sem)
    }
    for k,v in reps.items():
        for p in doc.paragraphs:
            if k in p.text: p.text = p.text.replace(k, v)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if k in p.text: p.text = p.text.replace(k, v)
    mask = (
        (df_bank["DISCIPLINA"]==disciplina) &
        (df_bank["ANO/SÉRIE"]==extrai_serie(turma)) &
        (df_bank["BIMESTRE"]==bimestre)
    )
    habs = df_bank.loc[mask, "HABILIDADE"].dropna().astype(str).tolist()
    objs = df_bank.loc[mask, "OBJETO DE CONHECIMENTO"].dropna().astype(str).tolist()
    for p in doc.paragraphs:
        if 'hhh' in p.text: p.text = "\n".join(habs)
        if 'ooo' in p.text: p.text = "\n".join(objs)
    out = BytesIO(); doc.save(out); out.seek(0)
    return out

def gerar_planejamento_template(professor, disciplina, turma, bimestre,
                                grupos, df_bank, modelo="modelo_planejamento.docx"):
    doc = Document(modelo)
    # Cabeçalho
    hdr = {'ppp': professor, 'ddd': disciplina, 'ttt': turma, 'bbb': bimestre}
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

    # Corpo por grupo
    for grp in grupos:
        doc.add_paragraph(f"Semana: {grp['semana']}")
        doc.add_paragraph(f"Aulas previstas: {grp['prev']}")
        for n in grp['nums']:
            titles = df_bank.loc[
                (df_bank["DISCIPLINA"] == disciplina) &
                (df_bank["ANO/SÉRIE"]  == extrai_serie(turma)) &
                (df_bank["BIMESTRE"]    == bimestre) &
                (df_bank["Nº da aula"]  == n),
                "TÍTULO DA AULA"
            ].dropna().astype(str).tolist()
            title = titles[0] if titles else ""
            doc.add_paragraph(f"Aula {n} – {title}")
        doc.add_paragraph(f"Metodologia: {', '.join(grp['met'])}")
        doc.add_paragraph(f"Critérios de avaliação: {', '.join(grp['crit'])}")
        doc.add_paragraph()

    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out

# ------------------------------
# Inicialização de estado
# ------------------------------
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

# ------------------------------
# Sidebar e navegação
# ------------------------------
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
if st.session_state.pagina == "Cadastro de Professor":
    st.header("Cadastro de Professor")
    nome = st.text_input("Nome")
    disciplinas = st.multiselect(
        "Disciplina(s)",
        ["Arte","Ciências","Ed. Física","Ed. Financeira","Geografia","História",
         "Português","Inglês","Matemática","PV","Redação","Tecnologia","OE Port","OE Mat"]
    )
    if st.button("Salvar Professor"):
        st.session_state.professores.append({"nome":nome,"disciplinas":disciplinas})
        salvar_json("professores.json", st.session_state.professores)
        st.success("Professor salvo!")
    for prof in st.session_state.professores:
        st.write(f"{prof['nome']} — {', '.join(prof['disciplinas'])}")

# 2. Cadastro de Turmas
elif st.session_state.pagina == "Cadastro de Turmas":
    st.header("Cadastro de Turmas")
    saved = st.session_state.turmas
    default_s = sorted({t[:-1] for t in saved.keys()})
    segmento = st.multiselect("Segmento(s)", ["Ensino Fundamental","Ensino Médio"], default=None)
    anos = []
    if "Ensino Fundamental" in segmento: anos += ["6º","7º","8º","9º"]
    if "Ensino Médio" in segmento: anos += ["1º","2º","3º"]
    series = st.multiselect("Ano/Série", anos, default=default_s)
    turma_map = {
        "6º":["6ºA","6ºB","6ºC","6ºD"],"7º":["7ºA","7ºB","7ºC"],"8º":["8ºA","8ºB","8ºC","8ºD"],
        "9º":["9ºA","9ºB","9ºC","9ºD"],"1º":["1ºA","1ºB","1ºC","1ºD","1ºE"],
        "2º":["2ºA ADM","2ºB ADM","2ºC"],"3º":["3ºA","3ºA ADM","3ºB ADM","3ºB LOG"]
    }
    op = sum((turma_map.get(s,[]) for s in series), [])
    sel = st.multiselect("Turma(s)", op, default=list(saved.keys()), key="sel_turmas")
    cores = {}
    for t in sel:
        cores[t] = st.color_picker(f"Cor {t}", value=saved.get(t,"#FFFFFF"), key=f"cor_{t}")
    if st.button("Salvar Turmas"):
        st.session_state.turmas = cores
        salvar_json("turmas.json", st.session_state.turmas)
        st.success("Turmas salvas!")

# 3. Cadastro de Horário
elif st.session_state.pagina == "Cadastro de Horário":
    st.header("Cadastro de Horário")
    if st.button("Adicionar Linha"):
        st.session_state.horarios.append({'turma':None,'disciplina':None,'dia':None,'aula':None})
    for i, itm in enumerate(st.session_state.horarios):
        cols = st.columns(6)
        turmas = list(st.session_state.turmas.keys())
        discs  = sorted({d for p in st.session_state.professores for d in p["disciplinas"]})
        dias   = ["Segunda","Terça","Quarta","Quinta","Sexta"]
        aulas  = list(map_hor.keys())
        itm['turma']      = cols[0].selectbox("Turma", turmas, index=turmas.index(itm.get('turma')) if itm.get('turma') in turmas else 0, key=f"turma_{i}")
        itm['disciplina'] = cols[1].selectbox("Disciplina", discs, index=discs.index(itm.get('disciplina')) if itm.get('disciplina') in discs else 0, key=f"disc_{i}")
        itm['dia']        = cols[2].selectbox("Dia", dias, index=dias.index(itm.get('dia')) if itm.get('dia') in dias else 0, key=f"dia_{i}")
        itm['aula']       = cols[3].selectbox("Aula", aulas, index=aulas.index(itm.get('aula')) if itm.get('aula') in aulas else 0, key=f"aula_{i}")
        cols[4].text_input("Horário", map_hor.get(itm['aula'],""), disabled=True, key=f"hor_{i}")
        if cols[5].button("X", key=f"rm_{i}"):
            st.session_state.horarios.pop(i)
            break
    if st.button("Salvar Horários"):
        salvar_json("horarios.json", st.session_state.horarios)
        st.success("Horários salvos!")
    if st.session_state.horarios:
        st.dataframe(pd.DataFrame(st.session_state.horarios).sort_values("dia"))

# 4. Gerar Agenda e Plano
elif st.session_state.pagina == "Gerar Agenda e Plano":
    st.header("Gerar Agenda e Plano")
    if not st.session_state.horarios:
        st.warning("Cadastre horários primeiro.")
    else:
        df_bank = pd.read_excel("ES_banco.xlsx", header=0)
        prof     = st.selectbox("Professor(a)", [p["nome"] for p in st.session_state.professores])
        bim      = st.selectbox("Bimestre", ["1º","2º","3º","4º"])
        mes_nome = st.selectbox("Mês", meses)
        semanas  = [
            f"{w[0].strftime('%d/%m')} – {w[-1].strftime('%d/%m')}"
            for w in calendar.Calendar().monthdatescalendar(datetime.now().year, meses.index(mes_nome)+1)
            if w[0].month == meses.index(mes_nome)+1
        ]
        sem_sel  = st.selectbox("Semana", semanas)
        turma_idx = {}
        for idx, itm in enumerate(st.session_state.horarios):
            turma_idx.setdefault(itm['turma'], []).append(idx)
        entries = []
        tabs = st.tabs(list(turma_idx.keys()))
        for tab, turma in zip(tabs, turma_idx.keys()):
            with tab:
                st.subheader(f"Turma {turma}")
                met_sel  = st.multiselect("Metodologia", st.session_state.extras["metodologia"], key=f"met_sel_{turma}")
                rec_sel  = st.multiselect("Recursos",      st.session_state.extras["recursos"],     key=f"rec_sel_{turma}")
                crit_sel = st.multiselect("Critérios",     st.session_state.extras["criterios"],    key=f"crit_sel_{turma}")
                for idx in turma_idx[turma]:
                    h = st.session_state.horarios[idx]
                    st.markdown(f"**{turma} | {h['disciplina']} | {h['dia']} | {h['aula']}**")
                    opts = sorted(pd.Series(
                        df_bank.loc[
                            (df_bank["DISCIPLINA"]==h['disciplina']) &
                            (df_bank["ANO/SÉRIE"]==extrai_serie(turma)) &
                            (df_bank["BIMESTRE"]==bim),
                            "Nº da aula"
                        ].dropna().astype(int)
                    ).unique().tolist())
                    num = st.selectbox("Nº da aula", opts, key=f"num_{turma}_{idx}")
                    entries.append({**h, "num": num})
                if st.button("Gerar Plano", key=f"gera_plano_{turma}"):
                    arq = gerar_plano_template(
                        [e for e in entries if e["turma"]==turma],
                        df_bank, prof, sem_sel, bim, turma,
                        met_sel, rec_sel, crit_sel
                    )
                    st.download_button(
                        f"Download Plano {turma}", data=arq,
                        file_name=f"plano_{turma}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
        if st.button("Gerar Agenda"):
            ag = gerar_agenda_template(entries, df_bank, prof, sem_sel, bim, st.session_state.turmas)
            st.download_button(
                "Download Agenda", data=ag,
                file_name="agenda_preenchida.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# 5. Cadastro Extras
elif st.session_state.pagina == "Cadastro Extras":
    st.header("Cadastro Extras")
    tab1, tab2, tab3 = st.tabs(["Metodologia","Recursos","Critérios"])
    with tab1:
        st.text_input("Metodologia", key="input_met")
        st.button("Inserir Metodologia",
                  on_click=lambda: st.session_state.extras["metodologia"].append(st.session_state.input_met)
                               or salvar_json("extras.json", st.session_state.extras)
                               or st.session_state.update(input_met=""))
        for i, item in enumerate(st.session_state.extras["metodologia"]):
            c1, c2 = st.columns([0.9, 0.1])
            c1.write(f"- {item}")
            c2.button("X", key=f"del_met_{i}",
                      on_click=lambda i=i: st.session_state.extras["metodologia"].pop(i)
                                          or salvar_json("extras.json", st.session_state.extras))
    with tab2:
        st.text_input("Recursos", key="input_rec")
        st.button("Inserir Recursos",
                  on_click=lambda: st.session_state.extras["recursos"].append(st.session_state.input_rec)
                               or salvar_json("extras.json", st.session_state.extras)
                               or st.session_state.update(input_rec=""))
        for i, item in enumerate(st.session_state.extras["recursos"]):
            c1, c2 = st.columns([0.9, 0.1])
            c1.write(f"- {item}")
            c2.button("X", key=f"del_rec_{i}",
                      on_click=lambda i=i: st.session_state.extras["recursos"].pop(i)
                                          or salvar_json("extras.json", st.session_state.extras))
    with tab3:
        st.text_input("Critério", key="input_crit")
        st.button("Inserir Critério",
                  on_click=lambda: st.session_state.extras["criterios"].append(st.session_state.input_crit)
                               or salvar_json("extras.json", st.session_state.extras)
                               or st.session_state.update(input_crit=""))
        for i, item in enumerate(st.session_state.extras["criterios"]):
            c1, c2 = st.columns([0.9, 0.1])
            c1.write(f"- {item}")
            c2.button("X", key=f"del_crit_{i}",
                      on_click=lambda i=i: st.session_state.extras["criterios"].pop(i)
                                          or salvar_json("extras.json", st.session_state.extras))

# 6. Gerar Guia
elif st.session_state.pagina == "Gerar Guia":
    st.header("Gerar Guia")
    if not st.session_state.horarios:
        st.warning("Cadastre horários primeiro.")
    else:
        df_bank = pd.read_excel("ES_banco.xlsx", header=0)
        prof = st.selectbox("Professor(a)", [p["nome"] for p in st.session_state.professores])
        bim  = st.selectbox("Bimestre", ["1º","2º","3º","4º"])
        inicio = st.date_input("Início"); fim = st.date_input("Fim")
        turmas = sorted({h["turma"] for h in st.session_state.horarios})
        tabs   = st.tabs(turmas)
        for tab, turma in zip(tabs, turmas):
            with tab:
                disc_opts = sorted({h["disciplina"] for h in st.session_state.horarios if h["turma"]==turma})
                disciplina = st.selectbox("Disciplina", disc_opts, key=f"disc_g_{turma}")
                q_bim = st.number_input("Qtd. de aulas no Bimestre", min_value=1, key=f"q_bim_{turma}")
                q_sem = st.number_input("Qtd. de aulas semanais", min_value=1, key=f"q_sem_{turma}")
                met_sel  = st.multiselect("Metodologia de Ensino", st.session_state.extras["metodologia"], key=f"met_g_{turma}")
                crit_sel = st.multiselect("Como serei Avaliado", st.session_state.extras["criterios"], key=f"crit_g_{turma}")
                if st.button("Gerar Guia", key=f"gera_guia_{turma}"):
                    arq = gerar_guia_template(prof, turma, disciplina, bim, inicio, fim, q_bim, q_sem, met_sel, crit_sel, df_bank)
                    st.download_button(f"Download Guia {turma}", data=arq, file_name=f"guia_{turma}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# 7. Gerar Planejamento Bimestral
elif st.session_state.pagina == "Gerar Planejamento Bimestral":
    st.header("Gerar Planejamento Bimestral")
    if not st.session_state.horarios:
        st.warning("Cadastre horários primeiro.")
    else:
        df_bank = pd.read_excel("ES_banco.xlsx", header=0)
        prof  = st.selectbox("Professor(a)", [p["nome"] for p in st.session_state.professores])
        bim   = st.selectbox("Bimestre", ["1º","2º","3º","4º"])
        turmas= sorted({h["turma"] for h in st.session_state.horarios})
        tabs  = st.tabs(turmas)
        for tab, turma in zip(tabs, turmas):
            with tab:
                cnt_key = f"count_{turma}"
                if cnt_key not in st.session_state: st.session_state[cnt_key] = 1
                grupos = []
                for i in range(st.session_state[cnt_key]):
                    with st.expander(f"Planejamento {i+1}", expanded=True):
                        mes     = st.selectbox("Mês", meses, key=f"plan_mes_{turma}_{i}")
                        semanas = [
                            f"{w[0].strftime('%d/%m')} – {w[4].strftime('%d/%m')}"
                            for w in calendar.Calendar().monthdatescalendar(ano_planej, meses.index(mes)+1)
                            if all(d.month==meses.index(mes)+1 for d in w[:5])
                        ]
                        semana   = st.selectbox("Semana", semanas, key=f"plan_sem_{turma}_{i}")
                        prev     = st.number_input("Aulas previstas", min_value=1, key=f"plan_prev_{turma}_{i}")
                        nums_opts= sorted(int(a.replace("ª","")) for a in map_hor.keys())
                        nums     = st.multiselect("Nº das aulas", nums_opts, key=f"plan_nums_{turma}_{i}")
                        met      = st.multiselect("Metodologias", st.session_state.extras["metodologia"], key=f"plan_met_{turma}_{i}")
                        crit     = st.multiselect("Critérios",    st.session_state.extras["criterios"],    key=f"plan_crit_{turma}_{i}")
                        grupos.append({"semana":semana,"prev":prev,"nums":nums,"met":met,"crit":crit})
                if st.button("Adicionar", key=f"add_plan_{turma}"):
                    st.session_state[cnt_key] += 1
                if st.button("Gerar Planejamento", key=f"gera_plan_{turma}"):
                    disc_set   = sorted({h["disciplina"] for h in st.session_state.horarios if h["turma"]==turma})
                    disciplina = ", ".join(disc_set)
                    arq = gerar_planejamento_template(prof, disciplina, turma, bim, grupos, df_bank)
                    st.download_button(f"Download Planejamento {turma}", data=arq, file_name=f"planejamento_{turma}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
