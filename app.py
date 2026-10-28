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

st.title("🚨 SOS Remplacement - Assistant (Gestion Multi-Semaines & Séquencement Propre)")
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

# Sélecteur de semaine à afficher si plusieurs fichiers sont chargés
semaine_selectionnee = st.sidebar.selectbox("3. Semaine à afficher en priorité", ["S43", "S44", "Les deux"])

# ---------------------------------------------------------
# 2. ANALYSE ROBUSTE ET SÉCURISÉE DES PLANNINGS
# ---------------------------------------------------------
planning_agents = {}
logs_debug = []

def noms_sont_compatibles(excel_name, pdf_name):
    e_words = set(excel_name.upper().split())
    p_words = set(pdf_name.upper().split())
    return len(e_words.intersection(p_words)) >= min(len(e_words), len(p_words))

if fichiers_planning:
    for fichier in fichiers_planning:
        # Filtrer selon le sélecteur de la sidebar si l'utilisateur le souhaite
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

            if match_semaine:
                num_semaine = int(match_semaine.group(1))
                jan4 = datetime(2026, 1, 4)
                start_week1 = jan4 - timedelta(days=jan4.weekday())
                start_target = start_week1 + timedelta(weeks=num_semaine - 1)
                
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
                
                # Extraction propre des services uniques valides
                services_trouves = []
                seen = set()
                
                for line in lignes_texte:
                    if "TOTAL" in line.upper() or len(line) < 4:
                        continue
                    
                    hours = re.findall(r'\b([0-2][0-9]:[0-5][0-9])\b', line)
                    if len(hours) >= 2:
                        h1, h2 = hours[0], hours[1]
                        sig = f"{h1}-{h2}"
                        if sig not in seen:
                            try:
                                t1 = datetime.strptime(h1, '%H:%M')
                                t2 = datetime.strptime(h2, '%H:%M')
                                diff = (t2 - t1).total_seconds()
                                if diff <= 0: diff += 24 * 3600
                                duree = diff / 3600.0
                                
                                if 3.0 <= duree <= 13.0:
                                    seen.add(sig)
                                    services_trouves.append((h1, h2))
                            except Exception:
                                pass

                semaine_agent = {}
                # Distribution naturelle (ex: 5 jours de travail, 2 jours de repos aux index 4 et 6 [ex: Vendredi et Dimanche])
                service_idx = 0
                for idx, j_target in enumerate(jours_semaine):
                    if idx in [4, 6]: # Jours de repos fixes hebdomadaires types (ex: Vendredi / Dimanche)
                        semaine_agent[j_target] = {"statut": "REPOS", "intervalles": []}
                    else:
                        if service_idx < len(services_trouves):
                            h1, h2 = services_trouves[service_idx]
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
                logs_debug.append(f"✅ Fichier `{fichier.name}` ({agent_name_pdf}) : Traité avec succès.")
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
        dates_triees = sorted(matched_schedule.keys(), key=lambda x: datetime.strptime(x, '%d/%m/%Y'))
        
        jours_repos_total = sum(1 for d in dates_triees if matched_schedule[d]["statut"] == "REPOS")
        
        if jours_repos_total < 1:
            st.warning(f"⚠️ **Alerte Réglementaire pour {agent_nom}** : Cet agent n'a aucun jour de repos répertorié cette semaine.")

        for idx_d, d in enumerate(dates_triees):
            info_jour = matched_schedule[d]
            statut = info_jour["statut"]
            dt_jour = datetime.strptime(d, '%d/%m/%Y')
            
            if statut == "REPOS":
                creneau_texte = "Journée complète (00h00 - 24h00)"
                opportunite = "🟢 Jour de Repos"
                
                if idx_d > 0:
                    veille_d = dates_triees[idx_d - 1]
                    info_veille = matched_schedule.get(veille_d, {})
                    intervalles_veille = info_veille.get("intervalles", [])
                    if intervalles_veille:
                        derniere_fin_veille = max([iv[1] for iv in intervalles_veille])
                        debut_autorise = derniere_fin_veille + timedelta(hours=11)
                        if debut_autorise.date() == dt_jour.date():
                            heure_min_str = debut_autorise.strftime('%H:%M')
                            dt_fin_max = min(debut_autorise + timedelta(hours=8), datetime.combine(dt_jour.date(), datetime.max.time()) - timedelta(hours=1))
                            creneau_texte = f"De {heure_min_str} à {dt_fin_max.strftime('%H:%M')} (Repos 11h respecté après fin à {derniere_fin_veille.strftime('%H:%M')})"
            else:
                intervalles = info_jour["intervalles"]
                heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                
                if heures_faites >= 10.0:
                    creneau_texte = f"Déjà {round(heures_faites, 2)}h faites ce jour (Complet)"
                    opportunite = "🔴 Complet (10h atteint)"
                else:
                    derniere_fin = max([iv[1] for iv in intervalles])
                    heure_debut_str = derniere_fin.strftime('%H:%M')
                    heures_restantes = max(0.0, 10.0 - heures_faites)
                    dt_fin_pot = derniere_fin + timedelta(hours=heures_restantes)
                    creneau_texte = f"De {heure_debut_str} à {dt_fin_pot.strftime('%H:%M')} ({round(heures_restantes, 2)}h max, déjà {round(heures_faites, 2)}h faites)"
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
                max_chars=150
            )
        },
        disabled=["Contrats", "Agent", "Date", "Type d'opportunité", "Créneau horaire / Heures possibles"],
        hide_index=True,
        use_container_width=True
    )
    st.success("✅ Tableau affiché avec succès !")
else:
    st.warning("⚠️ Aucun résultat dans le tableau. Vérifiez vos fichiers PDF importés.")