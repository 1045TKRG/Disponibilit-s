import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta
from io import BytesIO

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Portails RH",
    page_icon="🔒",
    layout="wide"
)

# ---------------------------------------------------------
# SÉCURITÉ : SYSTÈME DE MOT DE PASSE
# ---------------------------------------------------------
MOT_DE_PASSE_CORRECT = "SOS2026"  # <--- Changez ce mot de passe ici

if "authentifie" not in st.session_state:
    st.session_state["authentifie"] = False

if not st.session_state["authentifie"]:
    st.title("🔒 Accès Sécurisé — Portail RH & Plannings")
    st.write("Ce portail contient des données confidentielles. Veuillez saisir le mot de passe d'accès.")
    
    mdp_saisi = st.text_input("Mot de passe :", type="password")
    
    if st.button("Se connecter"):
        if mdp_saisi == MOT_DE_PASSE_CORRECT:
            st.session_state["authentifie"] = True
            st.success("Accès autorisé.")
            st.rerun()
        else:
            st.error("Mot de passe incorrect. Accès refusé.")
            
    st.stop()

# ---------------------------------------------------------
# INTERFACE PRINCIPALE
# ---------------------------------------------------------
col_titre, col_deco = st.columns([4, 1])
with col_titre:
    st.title("🚨 SOS Remplacement — Portail de Gestion")
with col_deco:
    if st.button("🔒 Déconnexion"):
        st.session_state["authentifie"] = False
        st.rerun()

st.markdown("---")

# Création des onglets
tab_dispo, tab_cp, tab_maladies, tab_cp_fin, tab_maladies_fin = st.tabs([
    "📋 Disponibilités & Remplacements", 
    "🏖️ Congés Payés & Analyses", 
    "🏥 Maladies & Analyses",
    "🎄 CP Fêtes de Fin d'Année (5 ans)",
    "🎄 Maladies Fêtes de Fin d'Année (5 ans)"
])

# ---------------------------------------------------------
# ONGLET 1 : DISPONIBILITÉS
# ---------------------------------------------------------
with tab_dispo:
    st.sidebar.header("📁 Données de la Semaine (Dispo)")
    uploaded_excel = st.sidebar.file_uploader(
        "1. Fichier Référentiel Agents (.xlsx)", 
        type=["xlsx", "xls"],
        key="excel_dispo"
    )
    fichiers_planning = st.sidebar.file_uploader(
        "2. Plannings PDF Comète (Multi-contrats)", 
        type=["pdf"], 
        accept_multiple_files=True,
        key="pdf_dispo"
    )

    def charger_referentiel(excel_file):
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            df_raw[0] = df_raw[0].ffill()
            
            donnees_traitees = []
            site_actuel = ""
            
            for idx, row in df_raw.iterrows():
                val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
                if val_col_a.upper() in ["SITES", "SITE", "NAN", "", "CONTRATS", "CONTRAT"]:
                    continue
                site_actuel = val_col_a
                
                for col_idx in range(1, len(row)):
                    agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                    if agent_nom and agent_nom.upper() not in ["NAN", "NOM / PRENOM", "AGENT"]:
                        donnees_traitees.append({
                            "Contrat": site_actuel,
                            "Agent": agent_nom
                        })
            return pd.DataFrame(donnees_traitees), None
        except Exception as e:
            return None, f"Erreur Excel : {e}"

    if not uploaded_excel:
        st.warning("⚠️ Veuillez importer le fichier **referentiel_agents.xlsx** dans le menu de gauche pour démarrer.")
        st.stop()

    df_agents, erreur = charger_referentiel(uploaded_excel)
    if erreur:
        st.error(f"⚠️ {erreur}")
        st.stop()

    semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"], key="semaine_dispo")

    def decimal_to_hm(heures_dec):
        h = int(heures_dec)
        m = int(round((heures_dec - h) * 60))
        if m == 60:
            h += 1
            m = 0
        return f"{h}h{m:02d}"

    planning_agents = {}
    logs_debug = []

    def noms_sont_compatibles(excel_name, pdf_text):
        mots_excel = [w.upper() for w in re.findall(r'\w+', excel_name) if len(w) > 1]
        p_upper = pdf_text.upper()
        if not mots_excel:
            return False
        matches = sum(1 for mot in mots_excel if mot in p_upper)
        return matches >= 1

    if fichiers_planning:
        for fichier in fichiers_planning:
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            
            semaines_a_traiter = []
            if match_semaine:
                semaines_a_traiter.append(int(match_semaine.group(1)))
            else:
                if semaine_selectionnee != "Les deux":
                    semaines_a_traiter.append(int(semaine_selectionnee.replace('S', '')))
                else:
                    semaines_a_traiter = [43, 44]

            try:
                reader = pypdf.PdfReader(fichier)
                lignes_texte = []
                for page in reader.pages:
                    t = page.extract_text(extraction_mode="layout") or page.extract_text()
                    if t:
                        for l in t.split('\n'):
                            l_clean = l.strip()
                            if l_clean:
                                lignes_texte.append(l_clean)
                
                texte_global = "\n".join(lignes_texte)
                
                agents_trouves_dans_pdf = []
                for ex_agent in df_agents["Agent"].unique():
                    if noms_sont_compatibles(ex_agent, texte_global):
                        agents_trouves_dans_pdf.append(ex_agent)
                
                logs_debug.append(f"📁 Fichier `{fichier.name}` : {len(agents_trouves_dans_pdf)} agent(s) détecté(s).")

                for num_semaine in semaines_a_traiter:
                    if semaine_selectionnee != "Les deux" and f"S{num_semaine}" != semaine_selectionnee:
                        continue

                    annee_ref = 2026
                    try:
                        start_target = datetime.fromisocalendar(annee_ref, num_semaine, 1)
                    except Exception:
                        jan4 = datetime(annee_ref, 1, 4)
                        start_week1 = jan4 - timedelta(days=jan4.weekday())
                        start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                    
                    jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
                    
                    services_tries = []
                    for line in lignes_texte:
                        hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', line)
                        if len(hours) >= 2:
                            h1, h2 = hours[0], hours[1]
                            try:
                                t1 = datetime.strptime(h1, '%H:%M')
                                t2 = datetime.strptime(h2, '%H:%M')
                                diff = (t2 - t1).total_seconds()
                                if diff <= 0: diff += 24 * 3600
                                duree = diff / 3600.0
                                if 0.5 <= duree <= 15.0:
                                    services_tries.append((t1, h1, h2, duree))
                            except Exception:
                                pass

                    services_tries.sort(key=lambda x: x[0])
                    services_uniques = []
                    seen_intervalles = set()
                    for s in services_tries:
                        sig = f"{s[1]}-{s[2]}"
                        if sig not in seen_intervalles:
                            seen_intervalles.add(sig)
                            services_uniques.
