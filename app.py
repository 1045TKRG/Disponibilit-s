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

st.title("🚨 SOS Remplacement - Assistant (Extraction Chirurgicale Comète)")
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
# 2. ANALYSE CHIRURGICALE DES PLANNINGS PDF
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

if fichiers_planning:
    for fichier in fichiers_planning:
        try:
            reader = pypdf.PdfReader(fichier)
            texte_complet = ""
            for page in reader.pages:
                try:
                    t = page.extract_text(extraction_mode="layout")
                except Exception:
                    t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
            
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

            # Déduction des 7 jours de la semaine via le nom du fichier (ex: S43, S44)
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            if match_semaine:
                num_semaine = int(match_semaine.group(1))
                jan4 = datetime(2026, 1, 4)
                start_week1 = jan4 - timedelta(days=jan4.weekday())
                start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
                
                semaine_agent = {j: {"statut": "REPOS", "intervalles": []} for j in jours_semaine}
                
                # Extraction de TOUTES les heures valides au format HH:MM du document
                all_hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', texte_complet)
                
                # Filtrage strict : on ne garde que les paires d'heures logiques (début -> fin de vacation)
                # Dans Comète, les vacations sont listées chronologiquement par jour.
                valid_pairs = []
                i = 0
                while i < len(all_hours) - 1:
                    try:
                        h1_str = all_hours[i]
                        h2_str = all_hours[i+1]
                        
                        dt_dummy = datetime(2026, 1, 1)
                        t1 = datetime.strptime(h1_str, '%H:%M')
                        t2 = datetime.strptime(h2_str, '%H:%M')
                        
                        # Calcul de la durée de la vacation
                        diff_sec = (t2 - t1).total_seconds()
                        if diff_sec <= 0:
                            diff_sec += 24 * 3600 # Passage minuit
                        
                        duree = diff_sec / 3600.0
                        
                        # Une vacation valide dure entre 1h et 14h
                        if 1.0 <= duree <= 14.0:
                            valid_pairs.append((h1_str, h2_str))
                            i += 2 # On passe à la paire suivante
                        else:
                            i += 1 # Décalage d'un cran si ce n'est pas une paire valide
                    except Exception:
                        i += 1

                # Répartition des paires valides sur les jours de la semaine (en suivant l'ordre de la grille)
                # Chaque jour peut avoir 0, 1 ou 2 services (ex: Samedi/Dimanche sur votre image)
                jour_idx = 0
                for h1, h2 in valid_pairs:
                    if jour_idx >= 7:
                        # Si on a plus de paires que de jours, on les répartit sur les derniers jours actifs ou on boucle/ajuste
                        jour_cible = jours_semaine[6]
                    else:
                        jour_cible = jours_semaine[jour_idx]
                    
                    try:
                        dt_deb = datetime.strptime(f"{jour_cible} {h1}", '%d/%m/%Y %H:%M')
                        dt_fin = datetime.strptime(f"{jour_cible} {h2}", '%d/%m/%Y %H:%M')
                        if dt_fin <= dt_deb:
                            dt_fin += timedelta(days=1)
                        
                        semaine_agent[jour_cible]["statut"] = "TRAVAIL"
                        semaine_agent[jour_cible]["intervalles"].append((dt_deb, dt_fin))
                    except Exception:
                        pass
                    
                    # On passe au jour suivant tous les 1 ou 2 services (ajustement selon le volume)
                    jour_idx += 1

                planning_agents[agent_name_pdf].update(semaine_agent)
                logs_debug.append(f"✅ Fichier `{fichier.name}` ({agent_name_pdf}) : {len(valid_pairs)} vacations extraites avec succès.")
            else:
                logs_debug.append(f"⚠️ Fichier `{fichier.name}` : Semaine introuvable dans le nom.")

        except Exception as e:
            logs_debug.append(f"⚠️ Erreur lecture `{fichier.name}` : {e}")

with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
    for log in logs_debug:
        st.write(log)

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU ET CONTRÔLE RÉGLEMENTAIRE
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Opportunités (Contrôle Réglementaire)")

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
        dates_trie