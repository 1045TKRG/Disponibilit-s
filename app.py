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

st.title("🚨 SOS Remplacement - Vue Globale des Disponibilités (Sécurisé)")
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
    st.warning("⚠️ Veuillez importer le fichier **referentiel_agents.xlsx** dans le menu de gauche pour démarrer.")
    st.stop()

df_agents, erreur = charger_referentiel(uploaded_excel)
if erreur:
    st.error(f"⚠️ {erreur}")
    st.stop()

# ---------------------------------------------------------
# 2. ANALYSE FINES DES PLANNINGS PDF (Ligne par Ligne)
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

# Dictionnaire global des plannings par agent : { "NOM_AGENT": { "JJ/MM/YYYY": "REPOS" / "TRAVAIL" / "ABSENT" } }
planning_agents = {}
agent_types_contrat = {}

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    # Si les mots principaux se croisent (ex: BUARD et PERLE)
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            for page in reader.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                text_upper = text.upper()
                
                # Recherche du nom de l'agent sur la page
                agent_name_pdf = None
                for line in lines:
                    line_up = line.upper()
                    if "PLANNING" in line_up and "SITES" in line_up:
                        match = re.search(r'PLANNING\s+(.*?)\s+PAR SITES', line_up)
                        if match:
                            agent_name_pdf = match.group(1).strip()
                            break
                    elif "AGENT" in line_up:
                        match = re.search(r'AGENT\s*:\s*(.*?)(?=\s+DU|\s+SITE|\n|$)', line_up)
                        if match:
                            agent_name_pdf = match.group(1).strip()
                            break
                
                # Fallback : Si aucun en-tête standard, on regarde si un agent du référentiel est mentionné sur la page
                if not agent_name_pdf:
                    for ex_agent in df_agents["Agent"].unique():
                        if ex_agent.upper() in text_upper:
                            agent_name_pdf = ex_agent.upper()
                            break
                
                if not agent_name_pdf:
                    continue
                
                if agent_name_pdf not in planning_agents:
                    planning_agents[agent_name_pdf] = {}
                
                # Détection type de contrat
                if "TEMPS PLEIN" in text_upper:
                    agent_types_contrat[agent_name_pdf] = "Temps plein"
                elif "TEMPS PARTIEL" in text_upper:
                    agent_types_contrat[agent_name_pdf] = "Temps partiel"
                elif "LISSÉ" in text_upper or "LISSE" in text_upper:
                    agent_types_contrat[agent_name_pdf] = "Lissé"
                else:
                    agent_types_contrat[agent_name_pdf] = agent_types_contrat.get(agent_name_pdf, "Temps plein")

                # Analyse ligne par ligne pour associer chaque date à son statut réel
                current_date = None
                for line in lines:
                    line_up = line.upper()
                    
                    # Détection d'une date (format DD/MM/YYYY ou DD/MM)
                    date_match = re.search(r'\b([0-9]{2}/[0-9]{2}(?:/[0-9]{4})?)\b', line)
                    if date_match:
                        d_raw = date_match.group(1)
                        if len(d_raw) == 5:
                            # Ajout de l'année par défaut si absente
                            current_date = f"{d_raw}/2026"
                        else:
                            current_date = d_raw
                    
                    if current_date:
                        # Vérification des motifs d'absence sur la ligne ou la page
                        is_absent = any(re.search(motif, line_up) for motif in MOTIFS_ABSENCE)
                        has_repos = "REPOS" in line_up
                        has_hours = bool(re.search(r'([0-2]?[0-9][:H][0-5][0-9])', line_up))
                        
                        if is_absent:
                            planning_agents[agent_name_pdf][current_date] = "ABSENT"
                        elif has_hours and not has_repos:
                            planning_agents[agent_name_pdf][current_date] = "TRAVAIL"
                        elif has_repos:
                            planning_agents[agent_name_pdf][current_date] = "REPOS"

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU GLOBAL DES DISPONIBILITÉS RÉELLES
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités Réelles (Vérifiées par agent)")

if not df_agents.empty:
    tous_agents = df_agents[["Site", "Agent"]].drop_duplicates().to_dict(orient="records")
    
    tableau_resultats = []
    
    for item in tous_agents:
        site = item["Site"]
        agent_nom = item["Agent"]
        
        # Trouver le planning PDF correspondant via la correspondance intelligente des noms
        matched_schedule = {}
        type_c = "Temps plein"
        
        for pdf_name, schedule_dict in planning_agents.items():
            if noms_sont_compatibles(agent_nom, pdf_name):
                matched_schedule.update(schedule_dict)
                if pdf_name in agent_types_contrat:
                    type_c = agent_types_contrat[pdf_name]
                break
        
        # Si un planning a été trouvé pour cet agent, on extrait ses jours de repos (disponibles)
        if matched_schedule:
            dates_triees = sorted(list(matched_schedule.keys()), key=lambda x: datetime.strptime(x, '%d/%m/%Y'))
            for d in dates_triees:
                statut = matched_schedule[d]
                # L'agent est disponible UNIQUEMENT s'il est en REPOS (ni travail, ni absence CP/maladie)
                if statut == "REPOS":
                    tableau_resultats.append({
                        "Site": site,
                        "Agent": agent_nom,
                        "Type de contrat": type_c,
                        "Date disponible": d,
                        "Créneau horaire": "Journée complète (Libre / Repos)",
                        "Dernier recours": "" # Case vide interactive
                    })
        else:
            # Optionnel : si l'agent n'a pas de PDF importé, on ne l'affiche pas en faux disponible pour sécuriser l'astreinte
            pass
            
    if tableau_resultats:
        df_table = pd.DataFrame(tableau_resultats)
        
        edited_df = st.data_editor(
            df_table,
            column_config={
                "Dernier recours": st.column_config.TextColumn(
                    "Dernier recours (Saisie quotidienne)",
                    help="Saisir manuellement des notes ou affectations au quotidien",
                    max_chars=150,
                )
            },
            disabled=["Site", "Agent", "Type de contrat", "Date disponible", "Créneau horaire"],
            hide_index=True,
            use_container_width=True
        )
        
        st.info("💡 **Sécurité active :** Seuls les agents dont les plannings PDF ont été analysés et qui ont un **REPOS** officiel validé le jour J apparaissent dans cette liste. Ceux qui travaillent ou sont en congés/maladie sont filtrés.")
    else:
        st.warning("⚠️ Aucune disponibilité en 'REPOS' trouvée. Vérifiez que les plannings PDF de la bonne semaine ont bien été importés.")
else:
    st.warning("⚠️ Veuillez importer le fichier référentiel.")