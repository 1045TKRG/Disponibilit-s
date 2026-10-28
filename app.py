if idx_d + 1 < len(dates_triees):
                            info_lendemain = matched_schedule.get(dates_triees[idx_d + 1], {})
                            intervalles_lendemain = info_lendemain.get("intervalles", [])
                            if intervalles_lendemain:
                                premiere_debut_lendemain = min([iv[0] for iv in intervalles_lendemain])
                                
                                max_fin_par_repos = premiere_debut_lendemain - timedelta(hours=11)
                                if max_fin_par_repos > derniere_fin:
                                    dt_fin_pot = min(derniere_fin + timedelta(hours=heures_restantes), max_fin_par_repos)
                                    heures_restantes = (dt_fin_pot - derniere_fin).total_seconds() / 3600.0
                                    limite_fin_str = dt_fin_pot.strftime('%H:%M')
                                else:
                                    heures_restantes = 0.0
                                    limite_fin_str = heure_debut_str
                            else:
                                dt_fin_pot = derniere_fin + timedelta(hours=heures_restantes)
                                limite_fin_str = dt_fin_pot.strftime('%H:%M')
                        else:
                            dt_fin_pot = derniere_fin + timedelta(hours=heures_restantes)
                            limite_fin_str = dt_fin_pot.strftime('%H:%M')
