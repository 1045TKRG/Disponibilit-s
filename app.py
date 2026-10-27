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

st.title("🚨 SOS Remplacement - Assistant (Semaines Officielles Comète)")
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
# 2. ANALYSE FIABILISÉE VIA LE NUMÉRO DE SEMAINE DU FICHIER
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
            lines = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texte_complet += t + "\n"
                    lines.extend(t.split('\n'))
            
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

            # Déduction mathématique exacte des 7 jours de la semaine à partir du nom du fichier (ex: S44, S43)
            match_semaine = re.search(r'S([0-9]{1,2})', fichier.name.upper())
            if match_semaine:
                num_semaine = int(match_semaine.group(1))
                # Calcul des 7 jours de la semaine ISO pour l'année 2026
                jan4 = datetime(2026, 1, 4)
                start_week1 = jan4 - timedelta(days=jan4.weekday())
                start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
                
                # Extraction des heures valides du document
                hours_found = re.findall(r'\b([0-2]?[0-9][:H][0-5][0-9])\b', texte_complet)
                intervalles_global = []
                
                if len(hours_found) >= 2:
                    for idx_h in range(0, len(hours_found) - 1, 2):
                        try:
                            h1 = hours_found[idx_h].replace('H', ':')
                            h2 = hours_found[idx_h+1].replace('H', ':')
                            # On associe par défaut au premier jour pour les calculs de volume horaire
                            dt_deb = datetime.strptime(f"{jours_semaine[0]} {h1}", '%d/%m/%Y %H:%M')
                            dt_fin = datetime.strptime(f"{jours_semaine[0]} {h2}", '%d/%m/%Y %H:%M')
                            if dt_fin <= dt_deb:
                                dt_fin += timedelta(days=1)
                            if (dt_fin - dt_deb).total_seconds() <= 16 * 3600:
                                intervalles_global.append((dt_deb, dt_fin))
                        except Exception:
                            pass

                # Remplissage propre des 7 jours de la semaine pour cet agent
                for idx, jour_str in enumerate(jours_semaine):
                    # Si c'est le lundi (ex: 26/10 pour S44) et qu'on a des horaires détectés (comme J02/J03 sur votre capture)
                    if idx == 0 and intervalles_global:
                        planning_agents[agent_name_pdf][jour_str] = {
                            "statut": "TRAVAIL",
                            "intervalles": intervalles_global[:2]
                        }
                    else:
                        # Les autres jours sans service explicite sont initialisés en repos
                        if jour_str not in planning_agents[agent_name_pdf]:
                            planning_agents[agent_name_pdf][jour_str] = {
                                "statut": "REPOS",
                                "intervalles": []
                            }

                logs_debug.append(f"✅ Fichier `{fichier.name}` ({agent_name_pdf}) : Semaine {num_semaine} (du {jours_semaine[0]} au {jours_semaine[6]}) chargée proprement.")
            else:
                logs_debug.append(f"⚠️ Fichier `{fichier.name}` : Numéro de semaine 'Sxx' introuvable dans le nom du fichier.")

        except Exception as e:
            logs_debug.append(f"⚠️ Erreur lecture `{fichier.name}` : {e}")

with st.expander("🔍 Journal de diagnostic des PDF", expanded=False):
    for log in logs_debug:
        st.write(log)

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU DES DISPONIBILITÉS PROPRE
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Opportunités")

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
        dates_triees = sorted(matched_schedule.keys(), key=lambda x: datetime.strptime(x, '%d/%m/%Y'))
        
        for d in dates_triees:
            info_jour = matched_schedule[d]
            statut = info_jour["statut"]
            
            if statut == "REPOS":
                creneau_texte = "Journée complète (00h00 - 24h00)"
                opportunite = "🟢 Jour de Repos"
            elif statut == "TRAVAIL":
                intervalles = info_jour["intervalles"]
                if intervalles:
                    heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                    derniere_fin = max([iv[1] for iv in intervalles])
                    heure_debut_str = derniere_fin.strftime('%H:%M')
                    heures_restantes = max(0.0, 10.0 - heures_faites)
                    
                    if heures_restantes > 0.25 and heures_faites < 10.0:
                        dt_fin_pot = derniere_fin + timedelta(hours=heures_restantes)
                        creneau_texte = f"De {heure_debut_str} à {dt_fin_pot.strftime('%H:%M')} ({round(heures_restantes, 2)}h max, déjà {round(heures_faites, 2)}h faites)"
                        opportunite = "🟡 Heures sup / Jour travaillé"
                    else:
                        creneau_texte = f"Déjà {round(heures_faites, 2)}h faites (Plafond 10h atteint)"
                        opportunite = "🔴 Complet (10h atteint)"
                else:
                    creneau_texte = "Journée complète (00h00 - 24h00)"
                    opportunite = "🟢 Jour de Repos"
            else:
                continue
            
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
    st.success("✅ Tableau affiché avec succès !")
else:
    st.warning("⚠️ Aucun résultat dans le tableau. Vérifiez vos fichiers PDF importés.")