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

st.title("🚨 SOS Remplacement - Suivi et Calcul des Créneaux (Repos 11h)")
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
                        "Contrats": site_actuel, # Renommé Site -> Contrats
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
# 2. ANALYSE FINES DES PLANNINGS PDF & HORAIRES (Repos 11h)
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

# Structure : { "NOM_AGENT": { "JJ/MM/YYYY": {"statut": "REPOS"/"TRAVAIL"/"ABSENT", "fin_travail": datetime } } }
planning_agents = {}

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

def parse_date_safe(date_str):
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d/%m'):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == '%d/%m':
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    return None

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
                
                if not agent_name_pdf:
                    for ex_agent in df_agents["Agent"].unique():
                        if ex_agent.upper() in text_upper:
                            agent_name_pdf = ex_agent.upper()
                            break
                
                if not agent_name_pdf:
                    continue
                
                if agent_name_pdf not in planning_agents:
                    planning_agents[agent_name_pdf] = {}

                current_date = None
                for line in lines:
                    line_up = line.upper()
                    
                    date_match = re.search(r'\b([0-9]{2}/[0-9]{2}(?:/[0-9]{2,4})?)\b', line)
                    if date_match:
                        d_raw = date_match.group(1)
                        parsed_dt = parse_date_safe(d_raw)
                        if parsed_dt:
                            current_date = parsed_dt.strftime('%d/%m/%Y')
                    
                    if current_date:
                        is_absent = any(re.search(motif, line_up) for motif in MOTIFS_ABSENCE)
                        has_repos = "REPOS" in line_up
                        
                        # Extraction des heures de travail (ex: 06:00 - 18:00)
                        hours_found = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', line)
                        
                        fin_dt = None
                        if len(hours_found) >= 2:
                            # On prend la dernière heure comme heure de fin de service
                            try:
                                h_fin_str = hours_found[-1].replace('H', ':')
                                fin_dt = datetime.strptime(f"{current_date} {h_fin_str}", '%d/%m/%Y %H:%M')
                            except:
                                pass

                        if is_absent:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "ABSENT", "fin": None}
                        elif hours_found and not has_repos:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "TRAVAIL", "fin": fin_dt}
                        elif has_repos:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "REPOS", "fin": None}

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU GLOBAL (AVEC CALCUL REPOS 11H)
# ---------------------------------------------------------
st.subheader("📋 Liste de tous les agents disponibles et créneaux sécurisés (Repos 11h)")

if not df_agents.empty:
    tous_agents = df_agents[["Contrats", "Agent"]].drop_duplicates().to_dict(orient="records")
    
    tableau_resultats = []
    
    for item in tous_agents:
        contrat_nom = item["Contrats"]
        agent_nom = item["Agent"]
        
        matched_schedule = {}
        for pdf_name, schedule_dict in planning_agents.items():
            if noms_sont_compatibles(agent_nom, pdf_name):
                matched_schedule.update(schedule_dict)
                break
        
        if matched_schedule:
            dates_triees = sorted(
                [d for d in matched_schedule.keys() if parse_date_safe(d) is not None], 
                key=lambda x: parse_date_safe(x)
            )
            
            for i, d in enumerate(dates_triees):
                info_jour = matched_schedule[d]
                statut = info_jour["statut"]
                
                if statut == "REPOS":
                    # Vérification du repos de 11h par rapport à la veille
                    creneau_texte = "Journée complète (00h00 - 24h00)"
                    
                    if i > 0:
                        veille_d = dates_triees[i-1]
                        info_veille = matched_schedule.get(veille_d, {})
                        
                        # Si l'agent a travaillé la veille et qu'on connaît son heure de fin
                        if info_veille.get("statut") == "TRAVAIL" and info_veille.get("fin"):
                            fin_veille = info_veille["fin"]
                            # Heure de fin de la veille + 11h de repos obligatoire
                            debut_autorise = fin_veille + timedelta(hours=11)
                            
                            dt_jour = parse_date_safe(d)
                            # Si le repos obligatoire mord sur le jour J
                            if debut_autorise.date() == dt_jour.date():
                                heure_min_str = debut_autorise.strftime('%H:%M')
                                creneau_texte = f"Disponible à partir de {heure_min_str} (Repos 11h respecté)"
                            elif debut_autorise > dt_jour:
                                # S'il ne peut pas travailler du tout de la journée à cause des 11h
                                continue
                    
                    tableau_resultats.append({
                        "Contrats": contrat_nom,
                        "Agent": agent_nom,
                        "Date disponible": d,
                        "Créneau horaire (Repos 11h)": creneau_texte,
                        "Dernier recours": ""
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
            disabled=["Contrats", "Agent", "Date disponible", "Créneau horaire (Repos 11h)"],
            hide_index=True,
            use_container_width=True
        )
        
        st.info("💡 **Règles appliquées :** La colonne de gauche s'appelle désormais **Contrats**, la colonne inutile du type de contrat a été supprimée, et les **créneaux horaires** intègrent automatiquement le calcul strict des 11h de repos minimum par rapport à l'heure de fin du service de la veille.")
    else:
        st.warning("⚠️ Aucune disponibilité trouvée. Vérifiez que les plannings PDF de la semaine sont bien importés.")
else:
    st.warning("⚠️ Veuillez importer le fichier référentiel.")