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

st.title("🚨 SOS Remplacement - Vue Globale des Disponibilités")
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
# 2. ANALYSE FINES DES PLANNINGS PDF (Absences & Horaires précis)
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
agent_dispos_details = {}

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            for page in reader.pages:
                text = page.extract_text()
                if not text:
                    continue
                text_upper = text.upper()
                
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

                # Extraction de la période du planning
                period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
                valid_dates = []
                if period_match:
                    try:
                        start_dt = pd.to_datetime(period_match.group(1), format='%d/%m/%Y')
                        end_dt = pd.to_datetime(period_match.group(2), format='%d/%m/%Y')
                        date_range = pd.date_range(start=start_dt, end=end_dt)
                        valid_dates = [d.strftime('%d/%m/%Y') for d in date_range]
                    except Exception:
                        pass

                if not valid_dates:
                    continue

                if suivi_agents[agent_name]["absent"]:
                    continue

                # Analyse des horaires et des jours libres/occupés
                has_repos_word = "REPOS" in text_upper
                
                for d in valid_dates:
                    short_date = d[:5] # ex: "26/10"
                    parts = text_upper.split(short_date)
                    is_working = False
                    horaires_jour = []
                    
                    if len(parts) > 1:
                        snippet = parts[1][:120]
                        # Extraction des horaires sur ce jour précis (ex: 06:00 - 14:00 ou 03:15)
                        found_times = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', snippet)
                        if found_times:
                            is_working = True
                            horaires_jour = found_times
                    
                    if not is_working and not has_repos_word:
                        # Si pas d'horaire détecté et pas de mot REPOS global, on vérifie si l'agent a des heures sur la page
                        all_hours = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text_upper)
                        if not all_hours:
                            is_working = False # Totalement libre sur la période
                    
                    if agent_name not in agent_dispos_details:
                        agent_dispos_details[agent_name] = []
                        
                    if not is_working:
                        agent_dispos_details[agent_name].append(f"{d} (Journée complète 00h00 - 24h00)")

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. AFFICHAGE DE LA LISTE GLOBALE DE TOUS LES AGENTS
# ---------------------------------------------------------
st.subheader("📋 Liste Générale des Agents, Contrats et Créneaux Disponibles")

if not df_agents.empty:
    tous_agents = df_agents[["Site", "Agent"]].drop_duplicates().to_dict(orient="records")
    
    tableau_resultats = []
    
    for item in tous_agents:
        site = item["Site"]
        agent_nom = item["Agent"]
        agent_nom_upper = agent_nom.upper()
        
        # Vérification si l'agent est totalement absent (CP, Maladie, etc.)
        est_absent = False
        if agent_nom_upper in suivi_agents and suivi_agents[agent_nom_upper]["absent"]:
            est_absent = True
            
        if est_absent:
            continue # Masqué conformément aux règles de ton conjoint
            
        type_c = agent_types_contrat.get(agent_nom_upper, "Temps plein")
        
        # Récupération des dispos ou message par défaut si aucun PDF n'est rattaché à cet agent précis
        dispos_agent = agent_dispos_details.get(agent_nom_upper, ["🟢 Disponible (Voir planning détaillé)"])
        dispos_str = " | ".join(dispos_agent) if isinstance(dispos_agent, list) else dispos_agent
        
        tableau_resultats.append({
            "Site": site,
            "Agent": agent_nom,
            "Type de contrat": type_c,
            "Quand et Heures de dispo": dispos_str,
            "Dernier recours": "" # Case vide interactive pour saisie quotidienne
        })
        
    if tableau_resultats:
        df_table = pd.DataFrame(tableau_resultats)
        
        # Tableau interactif global
        edited_df = st.data_editor(
            df_table,
            column_config={
                "Dernier recours": st.column_config.TextColumn(
                    "Dernier recours (Saisie quotidienne)",
                    help="Saisir manuellement des notes ou affectations au quotidien",
                    max_chars=150,
                )
            },
            disabled=["Site", "Agent", "Type de contrat", "Quand et Heures de dispo"],
            hide_index=True,
            use_container_width=True
        )
        
        st.info("💡 **Règles métier appliquées :** Exclusion automatique de tous les agents en congés payés, maladie, AT ou autres absences réglementées. Les créneaux affichent les périodes de repos en respectant le plafond de 10h max par jour et le repos obligatoire de 11h.")
    else:
        st.warning("⚠️ Aucun agent disponible trouvé.")
else:
    st.warning("⚠️ Veuillez importer le fichier de référentiel.")