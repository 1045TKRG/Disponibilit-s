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

st.title("🚨 SOS Remplacement - Assistant (Extraction Grille Propre)")
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
# 2. ANALYSE ET NETTOYAGE DES GRIFFES DE PLANNING
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
logs_debug = []

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
            lines = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    lines.extend(t.split('\n'))
            
            texte_complet = "\n".join(lines)
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

            dates_dans_doc = []
            for line in lines:
                m = re.search(r'\b([0-9]{2}/[0-9]{2}(?:/[0-9]{2,4})?)\b', line)
                if m:
                    dt = parse_date_safe(m.group(1))
                    if dt and dt not in dates_dans_doc:
                        dates_dans_doc.append(dt)

            current_date = None
            jours_traites = 0
            
            for line in lines:
                line_up = line.upper()
                
                date_match = re.search(r'\b([0-9]{2}/[0-9]{2}(?:/[0-9]{2,4})?)\b', line)
                if date_match:
                    parsed_dt = parse_date_safe(date_match.group(1))
                    if parsed_dt:
                        current_date = parsed_dt.strftime('%d/%m/%Y')
                
                if current_date:
                    dt_Obj = parse_date_safe(current_date)
                    if dt_Obj and dt_Obj.month in [10, 11]:
                        is_absent = any(re.search(motif, line_up) for motif in MOTIFS_ABSENCE)
                        hours_found = re.findall(r'\b([0-2]?[0-9][:H][0-5][0-9])\b', line)
                        intervalles = []
                        
                        if len(hours_found) >= 2:
                            for idx_h in range(0, len(hours_found) - 1, 2):
                                try:
                                    h1 = hours_found[idx_h].replace('H', ':')
                                    h2 = hours_found[idx_h+1].replace('H', ':')
                                    dt_deb = datetime.strptime(f"{current_date} {h1}", '%d/%m/%Y %H:%M')
                                    dt_fin = datetime.strptime(f"{current_date} {h2}", '%d/%m/%Y %H:%M')
                                    if dt_fin <= dt_deb:
                                        dt_fin += timedelta(days=1)
                                    
                                    if (dt_fin - dt_deb).total_seconds() <= 16 * 3600:
                                        intervalles.append((dt_deb, dt_fin))
                                except Exception:
                                    pass

                        has_repos = "REPOS" in line_up

                        if current_date not in planning_agents[agent_name_pdf]:
                            if is_absent:
                                planning_agents[agent_name_pdf][current_date] = {"statut": "ABSENT", "intervalles": []}
                                jours_traites += 1
                            elif intervalles:
                                planning_agents[agent_name_pdf][current_date] = {"statut": "TRAVAIL", "intervalles": intervalles}
                                jours_traites += 1
                            elif has_repos:
                                planning_agents[agent_name_pdf][current_date] = {"statut": "REPOS", "intervalles": []}
                                jours_traites += 1
                        elif intervalles and planning_agents[agent_name_pdf][current_date]["statut"] == "TRAVAIL":
                            planning_agents[agent_name_pdf][current_date]["intervalles"].extend(intervalles)

            logs_debug.append(f"✅ Fichier `{fichier.name}` ({agent_name_pdf}) : analysé proprement.")

        except Exception as e:
            logs_debug.append(f"⚠️ Erreur lecture `{fichier.name}` : {e}")

with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
    for log in logs_debug:
        st.write(log)

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU DES DISPONIBILITÉS PROPRE
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Opportunités")

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
                
                # CAS 1 : JOUR DE REPOS
                if statut == "REPOS":
                    creneau_texte = "Journée complète (00h00 - 24h00)"
                    
                    if i > 0:
                        veille_d = dates_triees[i-1]
                        info_veille = matched_schedule.get(veille_d, {})
                        intervalles_veille = info_veille.get("intervalles", [])
                        if intervalles_veille:
                            derniere_fin_veille = max([iv[1] for iv in intervalles_veille])
                            debut_autorise = derniere_fin_veille + timedelta(hours=11)
                            
                            if debut_autorise.date() == dt_jour.date():
                                heure_min_str = debut_autorise.strftime('%H:%M')
                                creneau_texte = f"Disponible à partir de {heure_min_str} (Repos 11h après fin à {derniere_fin_veille.strftime('%H:%M')})"