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

st.title("🚨 SOS Remplacement - Mode Diagnostic & Secours")
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

st.success(f"✅ Référentiel Excel chargé : {len(df_agents)} agents trouvés.")

# ---------------------------------------------------------
# 2. ANALYSE DES PDF ET JOURNAL DE BOGUE (DEBUG)
# ---------------------------------------------------------
planning_agents = {}
journal_debug = []

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
            texte_complet = ""
            lines = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
                    lines.extend(t.split('\n'))
            
            text_upper = texte_complet.upper()
            
            # Recherche du nom de l'agent
            agent_name_pdf = None
            for ex_agent in df_agents["Agent"].unique():
                if ex_agent.upper() in text_upper:
                    agent_name_pdf = ex_agent.upper()
                    break
            
            if not agent_name_pdf:
                journal_debug.append(f"❌ Fichier `{fichier.name}` : Aucun agent du référentiel trouvé dans le texte.")
                continue
            
            journal_debug.append(f"✅ Fichier `{fichier.name}` associé à l'agent : **{agent_name_pdf}**")
            
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
                                intervalles.append((dt_deb, dt_fin))
                            except Exception:
                                pass

                    has_repos = "REPOS" in line_up and len(intervalles) == 0

                    if intervalles:
                        if current_date not in planning_agents[agent_name_pdf]:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "TRAVAIL", "intervalles": []}
                        planning_agents[agent_name_pdf][current_date]["intervalles"].extend(intervalles)
                    elif has_repos:
                        if current_date not in planning_agents[agent_name_pdf]:
                            planning_agents[agent_name_pdf][current_date] = {"statut": "REPOS", "intervalles": []}

        except Exception as e:
            journal_debug.append(f"⚠️ Erreur sur `{fichier.name}` : {e}")

# Affichage du rapport de diagnostic des PDF
with st.expander("🔍 Rapport de diagnostic de lecture des PDF", expanded=True):
    if fichiers_planning:
        for log in journal_debug:
            st.write(log)
    else:
        st.warning("Aucun fichier PDF importé pour l'instant.")

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU DES DISPONIBILITÉS (SOUPLE)
# ---------------------------------------------------------
st.subheader("📋 Tableau des Opportunités")

tableau_resultats = []
tous_agents = df_agents[["Contrats", "Agent"]].drop_duplicates().to_dict(orient="records")

for item in tous_agents:
    contrat_nom = item["Contrats"]
    agent_nom = item["Agent"]
    
    matched_schedule = {}
    for pdf_name, schedule_dict in planning_agents.items():
        if noms_sont_compatibles(agent_nom, pdf_name):
            matched_schedule.update(schedule_dict)
            break
    
    if matched_schedule:
        dates_triees = sorted([d for d in matched_schedule.keys() if parse_date_safe(d) is not None], key=lambda x: parse_date_safe(x))
        for d in dates_triees:
            info_jour = matched_schedule[d]
            statut = info_jour["statut"]
            
            if statut == "REPOS":
                creneau_texte = "Journée complète (00h00 - 24h00)"
                opportunite = "🟢 Jour de Repos"
            else:
                intervalles = info_jour["intervalles"]
                if not intervalles:
                    continue
                total_h = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                if total_h >= 10.0:
                    continue
                creneau_texte = f"Vacation en cours ({round(total_h, 2)}h déjà faites, max 10h/j)"
                opportunite = "🟡 Heures sup / Jour travaillé"
            
            tableau_resultats.append({
                "Contrats": contrat_nom,
                "Agent": agent_nom,
                "Date": d,
                "Type d'opportunité": opportunite,
                "Créneau horaire / Heures possibles": creneau_texte,
                "Dernier recours": ""
            })

if tableau_resultats:
    df_table = pd.DataFrame(tableau_resultats)
    st.data_editor(
        df_table,
        column_config={
            "Dernier recours": st.column_config.TextColumn(
                "Dernier recours (Saisie quotidienne)",
                help="Saisir manuellement des notes",
                max_chars=150,
            )
        },
        disabled=["Contrats", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
        hide_index=True,
        use_container_width=True
    )
else:
    st.warning("⚠️ Aucun résultat affiché. Regardez dans le rapport de diagnostic ci-dessus si les noms de vos PDF sont bien reconnus.")