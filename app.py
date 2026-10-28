import streamlit as st
import pandas as pd
import pypdf
import re
from datetime import datetime, timedelta
from io import BytesIO

# Configuration de la page
st.set_page_config(
    page_title="SOS Remplacement - Centralistes",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 SOS Remplacement - Assistant (Conforme, Chronologique & Traçable)")
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

semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"])

# Fonction utilitaire pour convertir les heures décimales en format XhMM
def decimal_to_hm(heures_dec):
    h = int(heures_dec)
    m = int(round((heures_dec - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h{m:02d}"

# ---------------------------------------------------------
# 2. ANALYSE CHRONOLOGIQUE ET MULTI-AGENTS DES PDF
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

if fichiers_planning:
    for fichier in fichiers_planning:
        match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
        num_sem_file = f"S{match_semaine.group(1)}" if match_semaine else ""
        
        if semaine_selectionnee != "Les deux" and num_sem_file and num_sem_file != semaine_selectionnee:
            continue

        try:
            reader = pypdf.PdfReader(fichier)
            lignes_texte = []
            for page in reader.pages:
                t = page.extract_text(extraction_mode="layout") or page.extract_text()
                if t:
                    for l in t.split('\n'):
                        l_clean = l.strip()
                        if l_clean:
                            lignes_texte.append(l_clean)
            
            texte_global = "\n".join(lignes_texte)
            text_upper = texte_global.upper()
            
            agents_trouves_dans_pdf = []
            for ex_agent in df_agents["Agent"].unique():
                if ex_agent.upper() in text_upper:
                    agents_trouves_dans_pdf.append(ex_agent.upper())
            
            if not agents_trouves_dans_pdf:
                logs_debug.append(f"❌ Fichier `{fichier.name}` : Aucun agent du référentiel trouvé.")
                continue

            for agent_name_pdf in agents_trouves_dans_pdf:
                if agent_name_pdf not in planning_agents:
                    planning_agents[agent_name_pdf] = {}

                if match_semaine:
                    num_semaine = int(match_semaine.group(1))
                    annee_ref = 2026
                    try:
                        start_target = datetime.fromisocalendar(annee_ref, num_semaine, 1)
                    except Exception:
                        jan4 = datetime(annee_ref, 1, 4)
                        start_week1 = jan4 - timedelta(days=jan4.weekday())
                        start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                    
                    jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
                    semaine_agent = {j: {"statut": "REPOS", "intervalles": []} for j in jours_semaine}
                    
                    services_tries = []
                    for line in lignes_texte:
                        if "TOTAL" in line.upper() or len(line) < 4:
                            continue
                        
                        hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', line)
                        if len(hours) >= 2:
                            h1, h2 = hours[0], hours[1]
                            try:
                                t1 = datetime.strptime(h1, '%H:%M')
                                t2 = datetime.strptime(h2, '%H:%M')
                                diff = (t2 - t1).total_seconds()
                                if diff <= 0: diff += 24 * 3600
                                duree = diff / 3600.0
                                
                                if 1.0 <= duree <= 14.0:
                                    services_tries.append((t1, h1, h2, duree))
                            except Exception:
                                pass

                    services_tries.sort(key=lambda x: x[0])

                    services_uniques = []
                    seen_intervalles = set()
                    for s in services_tries:
                        sig = f"{s[1]}-{s[2]}"
                        if sig not in seen_intervalles:
                            seen_intervalles.add(sig)
                            services_uniques.append((s[1], s[2]))

                    service_idx = 0
                    for idx, j_target in enumerate(jours_semaine):
                        if idx == 4: # Vendredi repos type
                            semaine_agent[j_target] = {"statut": "REPOS", "intervalles": []}
                        else:
                            if service_idx < len(services_uniques):
                                h1, h2 = services_uniques[service_idx]
                                dt_deb = datetime.strptime(f"{j_target} {h1}", '%d/%m/%Y %H:%M')
                                dt_fin = datetime.strptime(f"{j_target} {h2}", '%d/%m/%Y %H:%M')
                                if dt_fin <= dt_deb: dt_fin += timedelta(days=1)
                                
                                semaine_agent[j_target] = {
                                    "statut": "TRAVAIL",
                                    "intervalles": [(dt_deb, dt_fin)]
                                }
                                service_idx += 1
                            else:
                                semaine_agent[j_target] = {"statut": "REPOS", "intervalles": []}

                    planning_agents[agent_name_pdf].update(semaine_agent)
                    logs_debug.append(f"✅ Fichier `{fichier.name}` ({agent_name_pdf}) : Analysé et synchronisé.")
                else:
                    logs_debug.append(f"⚠️ Fichier `{fichier.name}` : Semaine introuvable dans le nom.")

        except Exception as e:
            logs_debug.append(f"⚠️ Er
