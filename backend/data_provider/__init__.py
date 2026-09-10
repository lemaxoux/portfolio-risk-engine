"""Accès aux données de marché.

Seul module autorisé à parler au fournisseur de prix (Tiingo en v1). Le reste
du projet passe exclusivement par l'interface exposée ici, de sorte qu'un
changement de fournisseur ne demande de réécrire qu'un seul adaptateur.
"""
