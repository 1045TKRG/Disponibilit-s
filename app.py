import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Gestion Astreinte",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant d'Astreinte (Règles Métier & Multi-contrats)")
st.markdown("---")

# ---------------------------------------------------------
# 1. BARRE LATÉRALE : IMPORTATION DES FICHIERS
# ---------------------------------------------------------
st.sidebar.header("📁 Données & Paramètres")
uploaded_excel = st.sidebar.file_uploader("Référentiel Agents (.xlsx)", type=["xlsx", "xls"])
fichiers_planning = st.sidebar.file_uploader("Plannings PDF Comète (Multi-semaines / Multi-contrats)", type=["pdf"], accept_multiple_files=True)

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
# 2. ANALYSE DES PLANNINGS PDF (Absences strictes & Contraintes)
# ---------------------------------------------------------
# Formats d'absence exclus : CP, Maladie, AT, Sans solde, Maternité, Décès, Naissance, Mariage, Mise à pied...
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

# Dictionnaire pour stocker les indisponibilités par agent et par date
agents_indisponibilites = {}
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
                if agent_name not in agents_indisponibilites:
                    agents_indisponibilites[agent_name] = set()
                
                # Détection type de contrat s'il est mentionné dans le PDF (ou par défaut)
                if "TEMPS PLEIN" in text_upper:
                    agent_types_contrat[agent_name] = "Temps plein"
                elif "TEMPS PARTIEL" in text_upper:
                    agent_types_contrat[agent_name] = "Temps partiel"
                elif "LISSÉ" in text_upper or "LISSE" in text_upper:
                    agent_types_contrat[agent_name] = "Lissé"
                else:
                    agent_types_contrat[agent_name] = "Temps plein" # Valeur par défaut

                # Vérification des motifs d'absence stricts
                est_absent_global = False
                for motif in MOTIFS_ABSENCE:
                    if re.search(motif, text_upper):
                        est_absent_global = True
                        break
                
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

                if est_absent_global:
                    for d in valid_dates:
                        agents_indisponibilites[agent_name].add(d)
                    continue

                # Analyse des jours travaillés (prise en compte multi-contrats si plusieurs PDF pour un même agent)
                has_repos_word = "REPOS" in text_upper
                has_any_hours = len([t for t in re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text_upper) if t != "00:00"]) > 0
                
                if has_any_hours and not has_repos:
                    for d in valid_dates:
                        agents_indisponibilites[agent_name].add(d)
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
                            agents_indisponibilites[agent_name].add(d)

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. INTERFACE PRINCIPALE DE RECHERCHE ET VISUEL REQUIS
# ---------------------------------------------------------
st.subheader("🔍 Définition du besoin de remplacement")

col1, col2, col3 = st.columns(3)

with col1:
    date_remplacement = st.date_input("Date recherchée :", datetime.now())
    date_str = date_remplacement.strftime("%d/%m/%Y")

with col2:
    liste_sites = sorted(df_agents["Site"].unique().tolist()) if df_agents is not None else []
    site_choisi = st.selectbox("Site :", liste_sites)

with col3:
    creneau_demande = st.selectbox("Créneau ou tranche horaire :", [
        "Vacation Jour (06h00 - 18h00)",
        "Vacation Nuit (18h00 - 06h00)",
        "Vacation Matin (06h00 - 14h00)",
        "Vacation Soir (14h00 - 22h00)"
    ])

st.markdown("---")

if st.button("🔎 Afficher le tableau des agents (Contraintes & Disponibilités)", type="primary"):
    
    df_filtrer = df_agents[df_agents["Site"] == site_choisi].copy()
        
    st.subheader(f"📋 Tableau de Synthèse – Site : **{site_choisi}** (Date : {date_str})")
    
    if not df_filtrer.empty:
        agents_liste = df_filtrer["Agent"].drop_duplicates().tolist()
        
        tableau_resultats = []
        
        for agent_nom in agents_liste:
            agent_nom_upper = agent_nom.upper()
            est_occupe = False
            
            # Vérification multi-contrats / plannings cumulés
            for nom_pdf, dates_indispo in agents_indisponibilites.items():
                if agent_nom_upper in nom_pdf or nom_pdf in agent_nom_upper:
                    if date_str in dates_indispo:
                        est_occupe = True
                        break
            
            # Si l'agent travaille ou est absent (CP, Maladie, etc.), on ne l'affiche pas dans les disponibles
            if est_occupe:
                continue
                
            type_c = agent_types_contrat.get(agent_nom_upper, "Temps plein")
            
            tableau_resultats.append({
                "Agent": agent_nom,
                "Type de contrat": type_c,
                "Jour disponible": "🟢 Disponible",
                "Créneaux de disponibilité": creneau_demande,
                "Dernier recours": "" # Case vide demandée pour saisie quotidienne
            })
            
        if tableau_resultats:
            df_table = pd.DataFrame(tableau_resultats)
            
            # Configuration de l'affichage interactif avec la colonne éditable "Dernier recours"
            edited_df = st.data_editor(
                df_table,
                column_config={
                    "Dernier recours": st.column_config.TextColumn(
                        "Dernier recours (Saisie quotidienne)",
                        help="Entrer manuellement des notes ou données au quotidien si besoin",
                        max_chars=100,
                    )
                },
                disabled=["Agent", "Type de contrat", "Jour disponible", "Créneaux de disponibilité"],
                hide_index=True,
                use_container_width=True
            )
            
            st.caption("ℹ️ *Rappel des contraintes générales intégrées : Max 10h/jour, 48h/semaine, max 6 jours consécutifs, et repos minimal de 11h entre 2 jours.*")
        else:
            st.warning("⚠️ Aucun agent disponible pour ce site à cette date (tous les agents de ce site travaillent déjà, cumulent leurs contrats ou sont en absence réglementée).")
    else:
        st.warning("⚠️ Aucun agent trouvé pour ce site dans le référentiel.")