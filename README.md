# 🎯 PourCombien ?

Jeu de pari en différé entre deux personnes.

## Installation

```bash
pip install flask
```

## Lancement

```bash
python app.py
```

Puis ouvre http://localhost:5000

## Comment ça marche ?

1. **Personne A** crée un pari sur la page d'accueil et reçoit un lien unique
2. **Personne A** envoie le lien à la **Personne B**
3. **Personne B** ouvre le lien et choisit un nombre entre 1 et le max
4. **Personne A** peut ensuite choisir son nombre sur le même lien
5. Si les deux ont choisi le même nombre → **le pari est réalisé !**

Les paris sont stockés dans `paris.json` dans le même dossier.
