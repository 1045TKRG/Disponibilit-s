import streamlit as st
import pandas as pd
import os
import pypdf
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Gestion Sécurisée",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant d'Astreinte Centralistes")
st.markdown("---")

# ---------------------------------------------------------
# 1. DOSSIER ET RÉFÉRENTIEL EXCEL (Dossier du conjoint)
# ---------------------------------------------------------
# Vous pouvez modifier ce chemin si le dossier se trouve ailleurs sur sa session
DOSSIER_PLANNING = r"D:\Utilisateurs\Conjoint\Documents\planning"
EXCEL_PATH = os.path.join(DOSSIER_PLANNING, "referentiel_agents.xlsx")

@st.cache_data(ttl=10)
def charger_referentiel():
    chemin_effectif = EXCEL_PATH
    if not os.path.exists(chemin_effectif):
        chemin_double = os.path.join(DOSSIER_PLANNING, "referentiel_agents.xlsx.xlsx")
        if os.path.exists(chemin_double):
            chemin_effectif = chemin_double
        else:
            return None, f"Fichier introuvable : `{EXCEL_PATH}`"

    try:
        df_raw = pd.read_excel(chemin_effectif, header=None)
        df_raw[0] = df_raw[0].ffill()
        
        donnees_traitees = []
        site_actuel = ""
        
        for idx, row in df_raw.iterrows():
            val_col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
            if val_col_a.upper() in ["SITES", "SITE", "NAN", ""]:
                continue
                
            site_actuel = val_col_a
            premiere_cellule = str(row[1]).strip() if pd.notna(row[1]) else ""
            is_ssiap2_line = "SSIAP2" in premiere_cellule.upper() or "SSIAP 2" in premiere_cellule.upper()
            
            start_col = 2 if is_ssiap2_line else 1
            
            for col_idx in range(start_col, len(row)):
                agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                if agent_nom and agent_nom.upper() != "NAN":
                    donnees_traitees.append({
                        "Site": site_actuel,
                        "Agent": agent_nom,
                        "SSIAP2": "OUI" if is_ssiap2_line else "NON"
                    })
                    
        return pd.DataFrame(donnees_traitees), None
    except Exception as e:
        return None, f"Erreur de lecture du fichier Excel : {e}"

df_agents, erreur = charger_referentiel()

if erreur:
    st.error(f"⚠️ {erreur}")
    st.stop()

# ---------------------------------------------------------
# 2. BARRE LATÉRALE : DÉPÔT DES PLAANINGS COMÈTE (PDF)
# ---------------------------------------------------------
st.sidebar.header("📁 Plannings PDF Comète")
st.sidebar.markdown("Déposez les plannings PDF de la semaine pour analyser précisément les horaires et les repos de chaque agent.")
fichiers_planning = st.sidebar.file_uploader("Importer les plannings PDF", type=["pdf"], accept_multiple_files=True)

# Dictionnaire pour stocker les indisponibilités par agent et par date
agents_indisponibilites = {}

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            for page in reader.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                text_upper = text.upper()
                
                # Extraction du nom de l'agent sur le PDF Comète
                match_agent = re.search(r'Planning\s+(.*?)\s+par SITES', text, re.IGNORECASE)
                if not match_agent:
                    match_agent = re.search(r'Agent\s*:\s*(.*?)(?=\s+du|\s+site|\n)', text, re.IGNORECASE)
                
                if not match_agent:
                    continue
                
                agent_name = match_agent.group(1).strip().upper()
                if agent_name not in agents_indisponibilites:
                    agents_indisponibilites[agent_name] = set()
                
                # Exclusions globales page entière : Maladie ou CP global
                if bool(re.search(r'\b(MALADIE|MAL\.?)\b', text_upper)) or bool(re.search(r'\b(CP|CONG[EÉ]S?)\b', text_upper)):
                    period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
                    if period_match:
                        start_dt = pd.to_datetime(period_match.group(1), format='%d/%m/%Y')
                        end_dt = pd.to_datetime(period_match.group(2), format='%d/%m/%Y')
                        for d in pd.date_range(start=start_dt, end=end_dt):
                            agents_indisponibilites[agent_name].add(d.strftime('%d/%m/%Y'))
                    continue

                # Extraction de la période officielle du planning
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

                has_repos_word = "REPOS" in text_upper
                has_any_hours = len([t for t in re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', text_upper) if t != "00:00"]) > 0
                
                if has_any_hours and not has_repos:
                    # L'agent travaille toute la période sans repos
                    for d in valid_dates:
                        agents_indisponibilites[agent_name].add(d)
                elif has_repos:
                    # Jours spécifiques de repos
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
# 3. INTERFACE DE SELECTION DU BESOIN DE REMPLACEMENT
# ---------------------------------------------------------
st.subheader("🔍 Définir la vacation à remplacer")

col1, col2, col3, col4 = st.columns(4)

with col1:
    date_remplacement = st.date_input("Date :", datetime.now())
    date_str = date_remplacement.strftime("%d/%m/%Y")

with col2:
    liste_sites = sorted(df_agents["Site"].unique().tolist()) if df_agents is not None else []
    site_choisi = st.selectbox("Site :", liste_sites)

with col3:
    creneau_demande = st.selectbox("Tranche horaire à couvrir :", [
        "Vacation Jour (06h00 - 18h00)",
        "Vacation Nuit (18h00 - 06h00)",
        "Vacation Matin (06h00 - 14h00)",
        "Vacation Soir (14h00 - 22h00)"
    ])

with col4:
    filtre_ssiap = st.radio("Qualification :", ["Tous les agents", "Uniquement SSIAP 2"], horizontal=True)

st.markdown("---")

# ---------------------------------------------------------
# 4. RECHERCHE ET MASQUAGE STRICT DES OCCUPÉS / ABSENTS
# ---------------------------------------------------------
if st.button("🔎 Afficher uniquement les agents disponibles", type="primary"):
    
    df_filtrer = df_agents[df_agents["Site"] == site_choisi].copy()
    
    if filtre_ssiap == "Uniquement SSIAP 2":
        df_filtrer = df_filtrer[df_filtrer["SSIAP2"] == "OUI"]
        
    st.subheader(f"📋 Agents disponibles pour **{site_choisi}** ({creneau_demande}) le {date_str} :")
    
    if not df_filtrer.empty:
        agents_liste = df_filtrer[["Agent", "SSIAP2"]].drop_duplicates().to_dict(orient="records")
        
        compteur_disponible = 0
        
        for item in agents_liste:
            agent_nom = item["Agent"]
            is_ssiap2 = item["SSIAP2"] == "OUI"
            badge_ssiap = " ⭐ **[SSIAP 2]**" if is_ssiap2 else ""
            
            agent_nom_upper = agent_nom.upper()
            est_occupe = False
            
            for nom_pdf, dates_indispo in agents_indisponibilites.items():
                if agent_nom_upper in nom_pdf or nom_pdf in agent_nom_upper:
                    if date_str in dates_indispo:
                        est_occupe = True
                        break
            
            if est_occupe:
                continue
                
            compteur_disponible += 1
            
            st.markdown(f"### {compteur_disponible}. ✅ **{agent_nom}** {badge_ssiap}")
            
            if "06h00 - 18h00" in creneau_demande or "18h00 - 06h00" in creneau_demande:
                st.markdown("⏱️ **Créneau autorisé :** Plafond strict de **12h00 max**")
            else:
                st.markdown("⏱️ **Créneau autorisé :** Plafond strict de **08h00 max**")
                
            st.caption(f"Rappel : Vérifier le repos légal de 11h avant toute affectation sur {site_choisi}.")
            st.divider()
            
        if compteur_disponible == 0:
            st.warning("⚠️ Aucun agent n'est disponible (tous les agents habilités de ce site travaillent déjà sur cette date, ou aucun planning PDF n'a été importé).")
    else:
        st.warning("⚠️ Aucun agent trouvé pour ce site avec les critères choisis.")