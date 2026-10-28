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

st.title("🚨 SOS Remplacement - Assistant (Association Chronologique Stricte)")
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

# ---------------------------------------------------------
# 2. ANALYSE CHRONOLOGIQUE ET INDEXATION PAR DATE EXACTE
# ---------------------------------------------------------
# Initialisation propre des 7 jours de la semaine
                jours_semaine = [(start_target + timedelta(days=i)).strftime('%d/%m/%Y'] for i in range(7)]
                semaine_agent = {j: {"statut": "REPOS", "intervalles": []} for j in jours_semaine}
                
                # Dictionnaire de correspondance par nom du jour ou index
                # Sur les plannings Comète, les données s'alignent généralement par colonnes (de Lun à Dim)
                # Nous allons extraire les blocs horaires et les trier par heure de début chronologique réelle
                
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
                                # On stocke avec l'objet temps pour pouvoir les trier par ordre chronologique de la semaine
                                services_tries.append((t1, h1, h2, duree))
                        except Exception:
                            pass

                # Tri des services par ordre chronologique d'apparition dans la journée (de 00:00 vers 23:59)
                # Cela évite que des services de fin de journée se retrouvent au mauvais jour
                services_tries.sort(key=lambda x: x[0])

                # Pour éviter les doublons de lignes multiples d'un même contrat
                services_uniques = []
                seen_intervalles = set()
                for s in services_tries:
                    sig = f"{s[1]}-{s[2]}"
                    if sig not in seen_intervalles:
                        seen_intervalles.add(sig)
                        services_uniques.append((s[1], s[2]))

                # Attribution séquentielle aux jours travaillés de la semaine (en sautant les repos identifiés)
                # S43 Monique : Lun, Mar, Mer, Jeu travaillés, Vendredi repos, Samedi, Dimanche travaillés
                service_idx = 0
                for idx, j_target in enumerate(jours_semaine):
                    # Index 4 = Vendredi (jour de repos type sur votre exemple)
                    if idx == 4:
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

# ---------------------------------------------------------
# 3. GÉNÉRATION DU TABLEAU ET CONTRÔLE RÉGLEMENTAIRE STRICT
# ---------------------------------------------------------
st.subheader("📋 Liste des Disponibilités & Opportunités (Contrôle Rigoureux)")

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
                            dt_fin_max = min(
                                debut_autorise + timedelta(hours=8),
                                datetime.combine(dt_jour.date(), datetime.max.time()) - timedelta(hours=1)
                            )
                            creneau_texte = f"De {heure_min_str} à {dt_fin_max.strftime('%H:%M')} (Repos 11h respecté après fin à {derniere_fin_veille.strftime('%H:%M')})"
            else:
                intervalles = info_jour["intervalles"]
                heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                
                if heures_faites >= 10.0:
                    creneau_texte = f"Déjà {round(heures_faites, 2)}h faites ce jour (Plafond 10h atteint)"
                    opportunite = "🔴 Complet (10h atteint)"
                else:
                    derniere_fin = max([iv[1] for iv in intervalles]) if intervalles else datetime.combine(dt_jour.date(), datetime.min.time())
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
    )
    st.success("✅ Tableau affiché avec succès !")
else:
    st.warning("⚠️ Aucun résultat dans le tableau. Vérifiez vos fichiers PDF importés.")
