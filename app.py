else:
                intervalles = info_jour["intervalles"]
                # Calcul exact cumulé de toutes les vacations du jour
                heures_faites = sum([(iv[1] - iv[0]).total_seconds() for iv in intervalles]) / 3600.0
                
                # Si le cumul dépasse ou atteint 10h
                if heures_faites >= 10.0:
                    creneau_texte = f"Déjà {round(heures_faites, 2)}h faites ce jour (Plafond 10h atteint)"
                    opportunite = "🔴 Complet (10h atteint)"
                else:
                    # On prend la fin de la dernière vacation réelle du jour
                    derniere_fin = max([iv[1] for iv in intervalles]) if intervalles else datetime.combine(dt_jour.date(), datetime.min.time())
                    heure_debut_str = derniere_fin.strftime('%H:%M')
                    
                    heures_restantes = max(0.0, 10.0 - heures_faites)
                    dt_fin_pot = derniere_fin + timedelta(hours=heures_restantes)
                    
                    creneau_texte = f"De {heure_debut_str} à {dt_fin_pot.strftime('%H:%M')} ({round(heures_restantes, 2)}h max, déjà {round(heures_faites, 2)}h faites)"
                    opportunite = "🟡 Heures sup / Jour travaillé"