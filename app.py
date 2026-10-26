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

st.title("🚨 SOS Remplacement - Assistant d'Astreinte (Sécurisé & Filtré)")
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
            if val_col_a.upper() in ["SITES", "SITE", "NAN", ""]:
                continue
            site_actuel = val_col_a
            
            for col_idx in range(1, len(row)):
                agent_nom = str(row[col_idx]).strip() if pd.notna(row[col_idx]) else ""
                if agent_nom and agent_nom.upper() != "NAN":
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
# 2. ANALYSE FINE DES PLANNINGS PDF (Avec période stricte)
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
                
                period_match = re.search(r'DU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+AU\s+([0-9]{2}/[0-9]{2}/[0-9]{4})', text_upper)
                pdf_start_dt, pdf_end_dt = None, None
                if period_match:
                    pdf_start_dt = parse_date_safe(period_match.group(1))
                    pdf_end_dt = parse_date_safe(period_match.group(2))
                
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
                            if pdf_start_dt and pdf_end_dt:
                                if not (pdf_start_dt <= parsed_dt <= pdf_end_dt):
                                    current_date = None
                                    continue
                            current_date = parsed_dt.strftime('%d/%m/%Y')
                    
                    if current_date:
                        is_absent = any(re.search(motif, line_up) for motif in MOTIFS_ABSENCE)
                        has_repos = "REPOS" in line_up
                        
                        hours_found = re.findall(r'([0-2]?[0-9][:H][0-5][0-9])', line)
                        
                        intervalles = []
                        if len(hours_found) >= 2 and not has_repos:
                            for i in range(0, len(hours_found) - 1, 2):
                                try:
                                    h1 = hours_found[i].replace('H', ':')
                                    h2 = hours_found[i+1].replace('H', ':')
                                    dt_deb = datetime.strptime(f"{current_date} {h1}", '%d/%m/%Y %H:%M')
                                    dt_fin = datetime.strptime(f"{current_date} {h2}", '%d/%m/%Y %H:%M')
                                    if dt_fin < dt_deb:
                                        dt_fin += timedelta(days=1)
                                    intervalles.append((dt_deb, dt_fin))
                                except Exception:
                                    pass

                        if is_absent:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "ABSENT", "intervalles": []}
                        elif intervalles:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "TRAVAIL", "intervalles": intervalles}
                        elif has_repos:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "REPOS", "intervalles": []}

        except Exception as e:
            pass

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU
# ---------------------------------------------------------
st.subheader("📋 Disponibilités & Heures Complémentaires (Filtré par période)")

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
                dt_jour = parse_date_safe(d)
                
                # CAS 1 : JOUR DE REPOS COMPLET
                if statut == "REPOS":
                    creneau_texte = "Journée complète (Libre)"
                    
                    if i > 0:
                        veille_d = dates_triees[i-1]
                        info_veille = matched_schedule.get(veille_d, {})
                        intervalles_veille = info_veille.get("intervalles", [])
                        if intervalles_veille:
                            derniere_fin_veille = max([iv[1] for iv in intervalles_veille])
                            debut_autorise = derniere_fin_veille + timedelta(hours=11)
                            if debut_autorise.date() == dt_jour.date():
                                heure_min_str = debut_autorise.strftime('%H:%M')
                                creneau_texte = f"Disponible à partir de {heure_min_str} (Repos 11h)"
                            elif debut_autorise > dt_jour + timedelta(days=1):
                                continue
                    
                    tableau_resultats.append({
                        "Contrats": contrat_nom,
                        "Agent": agent_nom,
                        "Date": d,
                        "Type d'opportunité": "🟢 Jour de Repos",
                        "Créneau horaire / Heures possibles": creneau_texte,
                        "Dernier recours": ""
                    })

                # CAS 2 : JOUR OÙ IL TRAVAILLE DÉJÀ
                elif statut == "TRAVAIL":
                    intervalles = info_jour["intervalles"]
                    if not intervalles:
                        continue 
                    
                    total_secondes_travail = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles])
                    heures_deja_travaillees = total_secondes_travail / 3600.0
                    
                    if heures_deja_travaillees >= 10.0:
                        continue
                    
                    heures_restantes_jour = 10.0 - heures_deja_travaillees
                    
                    if heures_restantes_jour > 0:
                        derniere_fin_ce_jour = max([iv[1] for iv in intervalles])
                        
                        limite_par_lendemain = derniere_fin_ce_jour + timedelta(hours=15)
                        if i < len(dates_triees) - 1:
                            lendemain_d = dates_triees[i+1]
                            info_lendemain = matched_schedule.get(lendemain_d, {})
                            if info_lendemain.get("intervalles"):
                                premier_debut_lendemain = min([iv[0] for iv in info_lendemain["intervalles"]])
                                limite_fin_autorisee = premier_debut_lendemain - timedelta(hours=11)
                                if limite_fin_autorisee