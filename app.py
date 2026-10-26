<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Analyseur de Plannings & Disponibilités Sûreté</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
  <style>
    body { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
    .badge-repos { background-color: #DEF7EC; color: #03543F; }
    .badge-travail { background-color: #E1EFFE; color: #1E429F; }
    .badge-depassement { background-color: #FDE8E8; color: #9B1C1C; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen">

  <div class="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
    
    <!-- En-tête -->
    <header class="mb-8 bg-white p-6 rounded-xl shadow-sm border border-slate-200">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-2xl font-bold text-slate-900 flex items-center gap-2">
            🛡️ Analyseur de Plannings & Disponibilités
          </h1>
          <p class="text-sm text-slate-500 mt-1">
            Calcul automatique des vacations, temps de travail journaliers et jours de repos (Contrainte 10h/jour & 48h/semaine)
          </p>
        </div>
      </div>
    </header>

    <!-- Zone d'importation -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      
      <!-- Import Contrats Excel -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <label class="block text-sm font-semibold text-slate-700 mb-2">1. Fichier des contrats (.xlsx)</label>
        <input type="file" id="contratFile" accept=".xlsx, .xls" class="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded