import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Centralistes",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant d'Astreinte (Plateforme de Gestion)")
st.markdown("---")

# ---------------------------------------------------------
# 1. BARRE LATÉRALE : IMPORTATION DES FICHIERS
# ---------------------------------------------------------
st.sidebar.header("📁 Données de la Semaine")
uploaded_excel = st.sidebar.file_uploader("1. Fichier Référentiel Agents (.xlsx)", type=["xlsx", "xls"])
fichiers_planning = st.sidebar.file_uploader("2. Plannings PDF Comète (Multi-contrats)", type=["pdf"], accept_multiple_files=True)

# Fonction de lecture du référentiel Excel
def charger_referentiel(excel_file):
    try:
        df_raw = pd.read_excel(excel_file, header=None)
        df_raw[0] = df_raw[0].ffill()
        
        donnees_traitees = []
        site_actuel = ""
        
        for idx, row in df_raw.iterrows():
            val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            if val_col_a.upper() in ["SITES", "SITE", "NAN", ""]:
                continue
            site_actuel = val_col_a
            
            for col_idx in range(1, len(row)):
                agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                if agent_nom and agent_nom.upper() != "NAN":
                    donnees_traitees.append({
                        "Site": site_actuel,
                        "Agent": agent_nom
                    })
        return pd.DataFrame(donnees_traitees), None
    except Exception as e:
        return None, f"Erreur Excel : {e}"

if not uploaded_excel:
    st.warning("⚠️ Veuillez importer le fichier **referentiel_agents.xlsx** dans le menu de gauche.")
    st.stop()

df_agents, erreur = charger_referentiel(uploaded_excel)
if erreur:
    st.error(f"⚠️ {erreur}")
    st.stop()

# ---------------------------------------------------------
# 2. ANALYSE DES PLANNINGS PDF (Absences & Calculs de créneaux)
# ---------------------------------------------------------
MOTIFS_ABSENCE = [
    r'\bCP\b', r'\bCONG[EÉ]S?\b', 
    r'\bMALADIE\b', r'\bMAL\.?\b', 
    r'\bAT\b', r'\bACCIDENT\b', 
    r'\bSANS SOLDE\b', 
    r'\bMATERNIT[EÉ]\b', 
    r'\bD[EÉ]C[EÈ]S\b', 
    r'\bNAISSANCE\b', 
    r'\bMARIAGE\b', 
    r'\bMISE \u00c0 PIED\b', r'\bMISE A PIED\b'
]

suivi_agents = {}
agent_types_contrat = {}

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            for page in reader.pages:
                text = page.extract_text()
                if not text:
                    continue
                text_upper = text.upper()
                
                # Extraction du nom de l'agent
                match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text, re.IGNORECASE)
                if not match_agent:
                    match_agent = re.search(r'Agent\s*:\s*(.*?)(?=\s+du|\s+site|\n)', text, re.IGNORECASE)
                
                if not match_agent:
                    continue
                
                agent_name = match_agent.group(1).strip().upper()
                
                if agent_name not in suivi_agents:
                    suivi_agents[agent_name] = {
                        "jours_occupes": set(),
                        "absent": False
                    }
                
                # Détection type de contrat
                if "TEMPS PLEIN" in text_upper:
                    agent_types_contrat[agent_name] = "Temps plein"
                elif "TEMPS PARTIEL" in text_upper:
                    agent_types_contrat[agent_name] = "Temps partiel"
                elif "LISSÉ" in text_upper or "LISSE" in text_upper:
                    agent_types_contrat[agent_name] = "Lissé"
                else:
                    agent_types_contrat[agent_name] = agent_types_contrat.get(agent_name, "Temps plein")

                # Vérification des motifs d'absence
                for motif in MOTIFS_ABSENCE:
                    if re.search(motif, text_upper):
                        suivi_agents[agent_name]["absent"] = True
                        break

                # Extraction de la période
                period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
                valid_dates = []
                if period_match:
                    try:
                        start_dt = pd.to_datetime(period_match.group(1), format='%d/%m/%Y')
                        end_dt = pd.to_datetime(period_match.group(2), format='%d/%m/%Y')
                        date_range = pd.date_range(start=start_dt, end=end_dt)
                        valid_dates = [d.strftime('%d/%m/%Y') for d in date_range]
                    except:
                        pass

                if not valid_dates:
                    continue

                if suivi_agents[agent_name]["absent"]:
                    for d in valid_dates:
                        suivi_agents[agent_name]["jours_occupes"].add(d)
                    continue

                # Analyse des jours occupés / travaillés
                has_repos_word = "REPOS" in text_upper
                has_any_hours = len([t for t in re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text_upper) if t != "00:00"]) > 0
                
                if has_any_hours and not has_repos:
                    for d in valid_dates:
                        suivi_agents[agent_name]["jours_occupes"].add(d)
                elif has_repos:
                    for d in valid_dates:
                        short_date = d[:5]
                        parts = text_upper.split(short_date)
                        is_working_this_day = True
                        if len(parts) > 1:
                            snippet = parts[1][:100]
                            if not re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', snippet) and "REPOS" in snippet:
                                is_working_this_day = False
                        if is_working_this_day:
                            suivi_agents[agent_name]["jours_occupes"].add(d)

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. INTERFACE DE SÉLECTION ET LISTE DE DISPONIBILITÉ PAR SITE
# ---------------------------------------------------------
st.subheader("🔍 Analyse des Disponibilités et Créneaux par Site")

col1, col2 = st.columns(2)

with col1:
    liste_sites = sorted(df_agents["Site"].unique().tolist()) if df_agents is not None else []
    site_choisi = st.