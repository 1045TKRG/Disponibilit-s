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

st.title("🚨 SOS Remplacement - Vue Globale des Disponibilités (Par Date)")
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
# 2. ANALYSE FINES DES PLANNINGS PDF (Absences & Jours)
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

# Fonction utilitaire pour faire correspondre les noms (ex: "BUARD PERLE" avec "PERLE BUARD")
def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    # Si tous les mots de l'un sont dans l'autre ou intersection solide
    return e_words.issubset(p_words) or p_words.issubset(e_words) or len(e_words.intersection(p_words)) >= 2

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
                        "dates_absentes": set(),
                        "dates_travail": set(),
                        "toutes_dates": set()
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

                suivi_agents[agent_name]["toutes_dates"].update(valid_dates)

                # Vérification des motifs d'absence (CP, Maladie, etc.)
                est_absent_global = False
                for motif in MOTIFS_ABSENCE:
                    if re.search(motif, text_upper):
                        est_absent_global = True
                        break

                if est_absent_global:
                    suivi_agents[agent_name]["dates_absentes"].update(valid_dates)
                    continue

                # Analyse jour par jour des horaires et des repos
                has_repos_word = "REPOS" in text_upper
                
                for d in valid_dates:
                    short_date = d[:5] # ex: "27/10"
                    parts = text_upper.split(short_date)
                    is_working = False
                    
                    if len(parts) > 1:
                        snippet = parts[1][:120]
                        found_times = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', snippet)
                        if found_times:
                            is_working = True
                    
                    if not is_working and has_repos_word:
                        # C'est un jour de repos explicite
                        pass
                    elif not is_working and not has_repos_word:
                        # Vérification globale de la page
                        all_hours = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text_upper)
                        if not all_hours:
                            is_working = False
                        else:
                            # S'il y a des heures sur la page mais pas sur ce bout, vérifier s'il bosse
                            pass

                    if is_working:
                        suivi_agents[agent_name]["dates_travail"].add(d)

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU GLOBAL (UNE LIGNE PAR DATE DISPONIBLE)
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités (Une ligne par date)")

if not df_agents.empty:
    tous_agents = df_agents[["Site", "Agent"]].drop_duplicates().to_dict(orient="records")
    
    tableau_resultats = []
    
    for item in tous_agents:
        site = item["Site"]
        agent_nom = item["Agent"]
        
        # Trouver les clés PDF correspondantes pour cet agent
        matched_keys = [k for k in suivi_agents.keys() if noms_sont_compatibles(agent_nom, k)]
        
        agent_absentes = set()
        agent_travail = set()
        agent_toutes_dates = set()
        type_c = "Temps plein"
        
        for k in matched_keys:
            agent_absentes.update(suivi_agents[k]["dates_absentes"])
            agent_travail.update(suivi_agents[k]["dates_travail"])
            agent_toutes_dates.update(suivi_agents[k]["toutes_dates"])
            if k in agent_types_contrat:
                type_c = agent_types_contrat[k]
                
        # Pour chaque date enregistrée dans le planning de l'agent
        dates_triees = sorted(list(agent_toutes_dates), key=lambda x: datetime.strptime(x, '%d/%m/%Y'))
        
        for d in dates_triees:
            # Si l'agent est en congé payé, maladie, AT... on l'exclut strictement de la liste des dispo
            if d in agent_absentes:
                continue
            # S'il travaille ce jour-là, il n'est pas disponible
            if d in agent_travail:
                continue
                
            # S'il est libre ce jour-là, on ajoute une ligne dédiée !
            tableau_resultats.append({
                "Site": site,
                "Agent": agent_nom,
                "Type de contrat": type_c,
                "Date disponible": d,
                "Créneau horaire": "Journée complète (00h00 - 24h00)",
                "Dernier recours": "" # Case vide interactive
            })
            
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
        
        st.info("💡 **Règles appliquées :** Les agents en congés payés, arrêts maladie ou autres absences sont automatiquement filtrés et masqués. Chaque jour de repos libre apparaît sur sa propre ligne.")
    else:
        st.warning("⚠️ Aucune disponibilité trouvée avec les fichiers importés (vérifiez que les plannings PDF de la semaine sont bien chargés).")
else:
    st.warning("⚠️ Veuillez importer le fichier référentiel.")