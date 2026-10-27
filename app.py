import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Centralistes",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant (Extraction Chirurgicale par Date)")
st.markdown("---")

# ---------------------------------------------------------
# 1. BARRE LATÉRALE : IMPORTATION DES FICHIERS
# ---------------------------------------------------------
st.sidebar.header("📁 Données de la Semaine")
uploaded_excel = st.sidebar.file_uploader("1. Fichier Référentiel Agents (.xlsx)", type=["xlsx", "xls"])
fichiers_planning = st.sidebar.file_uploader("2. Plannings PDF Comète (Multi-contrats)", type=["pdf"], accept_multiple_files=True)

def charger_referentiel(excel_file):
    try:
        df_raw = pd.read_excel(excel_file, header=None)
        df_raw[0] = df_raw[0].ffill()
        
        donnees_traitees = []
        site_actuel = ""
        
        for idx, row in df_raw.iterrows():
            val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            if val_col_a.upper() in ["SITES", "SITE", "NAN", "", "CONTRATS"]:
                continue
            site_actuel = val_col_a
            
            for col_idx in range(1, len(row)):
                agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                if agent_nom and agent_nom.upper() not in ["NAN", "NOM / PRENOM", "AGENT"]:
                    donnees_traitees.append({
                        "Contrats": site_actuel,
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

# ---------------------------------------------------------
# 2. ANALYSE PAR DÉCOUPAGE STRICT DES JOURS (ANTI-CUMUL)
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            texte_complet = ""
            for page in reader.pages:
                try:
                    t = page.extract_text(extraction_mode="layout")
                except Exception:
                    t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
            
            text_upper = texte_complet.upper()
            
            agent_name_pdf = None
            for ex_agent in df_agents["Agent"].unique():
                if ex_agent.upper() in text_upper:
                    agent_name_pdf = ex_agent.upper()
                    break
            
            if not agent_name_pdf:
                logs_debug.append(f"❌ Fichier `{fichier.name}` : Aucun agent du référentiel trouvé.")
                continue
            
            if agent_name_pdf not in planning_agents:
                planning_agents[agent_name_pdf] = {}

            # Déduction des 7 jours de la semaine via le nom du fichier (ex: S43, S44)
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            if match_semaine:
                num_semaine = int(match_semaine.group(1))
                jan4 = datetime(2026, 1, 4)
                start_week1 = jan4 - timedelta(days=jan4.weekday())
                start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                
                # CORRECTION DE LA PARENTHÈSE ICI :
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
                
                semaine_agent = {j: {"statut": "REPOS", "intervalles": []} for j in jours_semaine}
                
                # Découpage du texte par date pour isoler chaque jour de la grille Comète
                positions_dates = []
                for j_str in jours_semaine:
                    dt = datetime.strptime(j_str, '%d/%m/%Y')
                    short_d = dt.strftime('%d/%m')
                    pos = texte_complet.find(j_str)
                    if pos == -1:
                        pos = texte_complet.find(short_d)
                    positions_dates.append((j_str, pos))
                
                valid_blocks = [p[1] for p in positions_dates if p[1] != -1]
                
                if len(valid_blocks) >= 3:
                    for idx, (j_str, pos) in enumerate(positions_dates):
                        if pos == -1:
                            continue
                        next_pos = len(texte_complet)
                        for next_idx in range(idx + 1, len(positions_dates)):
                            if positions_dates[next_idx][1] != -1:
                                next_pos = positions_dates[next_idx][1]
                                break
                        
                        bloc_jour = texte_complet[pos:next_pos]
                        hours_in_block = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', bloc_jour)
                        seen_pairs = set()
                        
                        i = 0
                        while i < len(hours_in_block) - 1:
                            h1 = hours_in_block[i]
                            h2 = hours_in_block[i+1]
                            pair_key = (h1, h2)
                            
                            if pair_key not in seen_pairs:
                                try:
                                    t1 = datetime.strptime(h1, '%H:%M')
                                    t2 = datetime.strptime(h2, '%H:%M')
                                    diff_sec = (t2 - t1).total_seconds()
                                    if diff_sec <= 0:
                                        diff_sec += 24 * 3600
                                    duree = diff_sec / 3600.0
                                    
                                    if 1.0 <= duree <= 14.0:
                                        seen_pairs.add(pair_key)
                                        dt_deb = datetime.strptime(f"{j_str} {h1}", '%d/%m/%Y %H:%M')
                                        dt_fin = datetime.strptime(f"{j_str} {h2}", '%d/%m/%Y %H:%M')
                                        if dt_fin <= dt_deb:
                                            dt_fin += timedelta(days=1)
                                        
                                        semaine_agent[j_str]["statut"] = "TRAVAIL"