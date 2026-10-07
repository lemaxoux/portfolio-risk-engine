# Méthodologie

Cette page dit comment l'outil obtient chaque chiffre de l'analyse&nbsp;: d'où viennent les données, quelles conventions suit le calcul, ce que chaque mesure calcule, ce qu'elle suppose et où elle s'arrête. Elle suit l'ordre de la page d'analyse. L'analyse dit ce qu'un chiffre signifie pour votre portefeuille&nbsp;; cette page dit comment il est obtenu. Chaque formule y est d'abord dite en mots, et aucun chiffre de votre portefeuille n'y figure&nbsp;: seulement les règles du calcul, les mêmes pour tous.

## Ce que fait l'outil {#principes}

L'outil décrit votre portefeuille tel que vous le détenez aujourd'hui&nbsp;: comment sa valeur aurait varié, ce qu'il aurait pu perdre, quelles lignes, c'est-à-dire quels titres détenus, portent ses variations, ce que de grandes crises passées lui auraient fait. Il ne dit jamais quoi en faire&nbsp;: il ignore votre horizon de placement, vos objectifs, votre situation fiscale et le reste de votre patrimoine.

Ses mesures décrivent le passé et ne prédisent rien&nbsp;: l'avenir peut s'en écarter fortement, en particulier lors d'une crise.

Chaque chiffre est une estimation sous conditions, et il les porte avec lui&nbsp;: sous «&nbsp;Détails du calcul&nbsp;», sa méthode, le nombre de jours de bourse sur lesquels il repose et sa période&nbsp;; dans le bandeau, en haut de la page, la date de valorisation, celle des cours retenus. La volatilité, qui mesure l'ampleur habituelle des variations, ne dit pas la même chose estimée sur deux ans ou sur sept jours.

**Pourquoi aucune note globale.** L'outil ne résume jamais le risque en une note unique, sur cent, en lettres ou en couleurs. Une telle note additionnerait, avec une pondération que rien ne justifie, des grandeurs qui ne se comparent pas&nbsp;: la concentration du portefeuille sur quelques lignes, la part de ses variations qui suit le marché, la part de sa valeur qu'une crise rejouée a pu couvrir. Elle cacherait les arbitrages que la page existe pour montrer, et aurait l'air d'un avis sans en être un.

## Les données {#donnees}

**Les cours.** Ils viennent de Tiingo, un fournisseur de données de marché&nbsp;: le cours de clôture, le dernier de chaque jour de bourse, d'actions et de fonds cotés aux États-Unis, en dollars américains (USD). Pour chaque jour, la base garde deux cours&nbsp;: le cours brut, auquel on pouvait traiter, et le cours ajusté, corrigé des divisions d'actions (une action coupée en plusieurs) et des dividendes.

**Deux cours, deux usages.** La valeur de votre portefeuille se calcule au cours brut, un prix réel&nbsp;; les rendements, c'est-à-dire les variations d'un jour de bourse au suivant, au cours ajusté. Le jour où une action détache un dividende ou se divise, son cours brut baisse sans que son détenteur s'appauvrisse&nbsp;: le calcul y verrait une perte qui n'en est pas une. Au cours ajusté, les dividendes comptent comme réinvestis. Quand un dividende ou une division s'ajoute, la mise à jour recharge tout l'historique du titre, pour que sa série repose sur une seule base.

**La profondeur.** Les cours remontent au 1er&nbsp;janvier&nbsp;2005, une date fixe&nbsp;: une durée glissante, comme «&nbsp;les cinq dernières années&nbsp;», ferait un jour sortir une crise de l'historique sans que rien ne le signale. Cette date couvre les trois crises que l'outil rejoue&nbsp;; un titre coté plus tard entre avec l'historique qui existe.

**L'indice de référence.** Le marché est représenté par le S&P 500, l'indice de 500 grandes entreprises américaines, à travers SPY, le fonds coté qui le réplique.

**La date de valorisation.** La date «&nbsp;Valorisé au&nbsp;» est la plus ancienne des dernières clôtures de vos lignes&nbsp;: c'est jusque-là que la valeur est vraie pour toutes. Elle date les cours, pas les quantités&nbsp;: la date de modification de vos positions est donnée à part, dans le bandeau.

## Les conventions {#conventions}

**La composition d'aujourd'hui, rejouée sur le passé.** Les mesures appliquent à chaque jour passé les poids d'aujourd'hui, la part de chaque ligne dans la valeur actuelle, comme si le portefeuille avait été remis chaque soir à sa composition actuelle. Elles disent quel risque porte ce que vous détenez maintenant, pas ce qu'a fait votre portefeuille depuis que vous l'avez constitué&nbsp;: d'où le conditionnel des phrases, «&nbsp;aurait perdu&nbsp;». Un montant en dollars représente une part de la valeur d'aujourd'hui&nbsp;; il ne dit pas ce qui a été perdu ce jour-là.

**Les rendements.** Le rendement d'un jour est la variation du cours ajusté depuis le jour de bourse précédent&nbsp;; celui du portefeuille, la moyenne des rendements de ses lignes, pondérée par leurs poids actuels.

$$r_{t} = P_{t} / P_{t−1} − 1$$

$$r_{p,t} = w_{1} r_{1,t} + w_{2} r_{2,t} + … + w_{N} r_{N,t}$$

Ici, $P$ est le cours ajusté, $w_{i}$ le poids actuel de la ligne $i$ et $N$ le nombre de lignes.

**Simples entre les lignes, composés dans le temps.** Entre les lignes, ces rendements simples se moyennent, parce que la valeur d'un portefeuille est la somme de celles de ses lignes. Dans le temps, ils se composent&nbsp;: la valeur est multipliée par $(1 + r)$ jour après jour, ce qui revient à additionner des rendements logarithmiques, $ln(1 + r)$. Les deux ne s'échangent pas, et l'écart grandit avec les fortes variations, celles qui comptent pour le risque.

**La fenêtre d'estimation.** Les mesures du temps ordinaire portent sur les 504&nbsp;jours de bourse les plus récents, environ deux ans, que les phrases disent «&nbsp;ces deux&nbsp;dernières années&nbsp;»&nbsp;: assez de jours pour des estimations stables, assez récents pour décrire les marchés d'aujourd'hui. Les cours plus anciens ne servent qu'à rejouer les crises&nbsp;: une volatilité calculée sur tout l'historique serait dominée par la Crise financière 2008.

**Les mêmes jours pour toutes les lignes.** Les séries sont rapprochées par date, et seuls les jours où toutes vos lignes ont un cours sont retenus. Une ligne cotée depuis peu ramène donc toutes les mesures à son historique&nbsp;: le bandeau le dit, avec le nombre de jours obtenus sur les 504&nbsp;jours de bourse demandés, et nomme la ligne en cause quand c'est prouvé&nbsp;: sa première cotation est le jour à partir duquel toutes vos lignes ont un cours. Chaque mesure donne, dans ses détails du calcul, le nombre de jours qui a réellement servi.

## Le portefeuille {#portefeuille}

### Valeur et poids {#valeur-et-poids}

La section 1 donne, pour chaque ligne, la quantité, le dernier cours brut, la valeur et le poids.

$$V = q_{1} P_{1} + … + q_{N} P_{N}$$

$$w_{i} = q_{i} P_{i} / V$$

Ici, $q_{i}$ est la quantité de la ligne $i$, $P_{i}$ son dernier cours brut et $V$ la valeur du portefeuille. Le poids est une part de la valeur, et non du nombre de titres.

**Hypothèses.** Des positions acheteuses, des titres que vous possédez&nbsp;: une quantité nulle ou négative est refusée à la saisie.

**Limites.** Un prix de revient saisi, le prix auquel vous avez acheté, n'entre dans aucun calcul de risque.

## Un jour ordinaire {#jour-ordinaire}

### La VaR historique {#var-historique}

La VaR, ou valeur à risque, est un seuil de perte&nbsp;: à 95&#x202F;%, celui qu'atteignent ou dépassent les 5&#x202F;% de jours les plus mauvais de la fenêtre&nbsp;; à 99&#x202F;%, le 1&#x202F;% le plus mauvais. La version historique le lit dans les jours observés&nbsp;: les rendements sont rangés du plus mauvais au meilleur, et la VaR est la perte du rendement qui marque ce rang.

$$VaR_{α} = −q_{1−α}(r)$$

Ici, $q_{1−α}(r)$ est le quantile empirique des rendements quotidiens, le rendement sous lequel tombe la part $1 − α$ des jours observés, et $α$ le niveau de confiance, 95&#x202F;% ou 99&#x202F;%. La VaR s'écrit en perte et se lit comme une perte d'au moins ce pourcentage&nbsp;; négative, elle serait un gain. Le quantile est toujours un rendement observé&nbsp;: entre deux jours, l'outil prend le plus mauvais, sans moyenne («&nbsp;interpolation 'lower'&nbsp;»).

**Hypothèses.** Aucune loi n'est supposée&nbsp;: les variations observées, extrêmes compris, sont dans le chiffre.

**Limites.** Le chiffre décrit la fenêtre, et ne vaut pour d'autres jours que s'ils lui ressemblent. Ce n'est pas un plafond&nbsp;: il ne dit rien des pertes au-delà du seuil (voir [la CVaR](#cvar), la perte moyenne des pires jours), ni d'un choc plus violent que le pire jour de la fenêtre, cité sous la VaR à 95&#x202F;%. À 99&#x202F;%, il repose sur quelques jours seulement. Sous 20&nbsp;jours de bourse à 95&#x202F;%, et sous 100&nbsp;jours de bourse à 99&#x202F;%, il n'est pas chiffré&nbsp;: aucun jour ne tomberait dans la part la plus mauvaise.

### Le graphique des variations {#histogramme}

Le graphique compte les jours de bourse de la fenêtre par tranches de 0,25&nbsp;point, soit 0,25&#x202F;% de variation. Les tranches sont les mêmes pour tout portefeuille, et zéro en est toujours une borne&nbsp;: une baisse et une hausse ne partagent jamais une barre, et deux portefeuilles se comparent sur la même grille. Les traits marquent les seuils des VaR historiques, la zone ombrée les jours au-delà du seuil à 95&#x202F;%. La largeur des tranches change l'allure du dessin, jamais un chiffre.

### La VaR paramétrique {#var-parametrique}

La même question, posée à une courbe plutôt qu'aux jours observés&nbsp;: la loi normale, la courbe en cloche des statistiques, ou la loi de Student, une cloche aux bords plus épais, qui laisse plus de place aux jours extrêmes. La courbe est ajustée à la volatilité quotidienne du portefeuille.

$$VaR_{α} = z_{α} × σ_{p}$$

$$σ_{p} = √(w^{T} Σ w)$$

Ici, $σ_{p}$ est la volatilité quotidienne du portefeuille, son écart-type quotidien&nbsp;: l'écart-type mesure de combien les rendements s'écartent d'habitude de leur moyenne. L'outil le tire des covariances de vos lignes, rangées dans un tableau noté $Σ$ (la covariance de deux lignes mesure combien elles varient ensemble), et de leurs poids $w$&nbsp;: c'est le même nombre que l'écart-type de la série du portefeuille, obtenu par un autre chemin. Pour la loi normale, $z_{α}$, son quantile, vaut 1,645 à 95&#x202F;% et 2,326 à 99&#x202F;%. La moyenne des rendements est prise nulle («&nbsp;$μ = 0$&nbsp;»)&nbsp;: sur deux ans, la tendance d'un jour se mesure moins bien que sa dispersion.

La loi de Student a un paramètre de plus, le nombre de degrés de liberté, noté $ν$ (la lettre grecque nu)&nbsp;: plus il est petit, plus les jours extrêmes sont fréquents. L'outil l'estime sur les rendements de votre portefeuille, par maximum de vraisemblance&nbsp;: la valeur de $ν$ qui rend les rendements observés les plus probables. Il met ensuite la courbe à la même variance que la loi normale, la variance étant le carré de l'écart-type&nbsp;: entre les deux VaR, seule la forme des queues change, ces extrémités de la courbe où se trouvent les jours extrêmes.

$$VaR_{α} = t_{ν,α} × √((ν − 2) / ν) × σ_{p}$$

Ici, $t_{ν,α}$ est le quantile de la loi de Student. À variance égale, elle compte plus de jours très calmes et de jours extrêmes, et moins de jours moyens&nbsp;: sa VaR est d'ordinaire plus basse à 95&#x202F;% et plus haute à 99&#x202F;%.

**Contrôle.** Chaque VaR paramétrique est refaite par simulation («&nbsp;Monte Carlo&nbsp;» dans les détails du calcul)&nbsp;: 100&#x202F;000&nbsp;tirages au hasard dans la même loi, avec une graine fixe, le point de départ du hasard, pour que le chiffre ne change pas d'un calcul à l'autre. Ce n'est pas une troisième mesure&nbsp;: le résultat, à la ligne «&nbsp;Contrôle&nbsp;» des détails du calcul, retrouve la formule aux aléas du tirage près, et un écart signalerait une erreur. Il manque notamment quand la fenêtre ne compte pas plus de jours de bourse que le portefeuille n'a de lignes&nbsp;: la simulation est alors impossible, et la page dit pourquoi.

**Hypothèses.** Les variations suivent la forme de la courbe&nbsp;: la loi normale rend les très mauvais jours très rares, la loi de Student leur laisse plus de place.

**Limites.** Chaque chiffre vaut ce que vaut la forme supposée&nbsp;; l'écart entre les deux courbes montre combien ce choix compte. Sous 30&nbsp;jours de bourse, la loi de Student n'est pas ajustée, et la VaR normale est marquée «&nbsp;Estimation mince&nbsp;». Avec 2&nbsp;degrés de liberté ou moins, la loi de Student n'a pas de variance finie&nbsp;; au-delà de 30&nbsp;degrés de liberté, elle ne se distingue plus de la loi normale. Dans les deux cas, elle n'est pas chiffrée.

### La volatilité {#volatilite}

La volatilité mesure l'ampleur habituelle des variations, à la hausse comme à la baisse&nbsp;: l'écart-type des rendements quotidiens de la fenêtre, ramené à une année de 252&nbsp;jours de bourse.

$$σ_{an} = σ_{jour} × √252$$

Ici, $σ_{jour}$ est l'écart-type des $n$ rendements quotidiens, avec $n − 1$ au dénominateur, la convention de tout le calcul&nbsp;; les détails du calcul le donnent aussi. Pour comparer, la page cite celle du S&P 500, mesurée sur les mêmes jours et de la même façon.

**Hypothèses.** Multiplier par $√252$ suppose des jours indépendants et de même loi.

**Limites.** Quand un jour tend à prolonger ou à corriger la veille, ou quand les fortes variations se suivent, la règle se trompe. La volatilité ne dit pas dans quel sens va la valeur. Sous 30&nbsp;jours de bourse, elle est marquée «&nbsp;Estimation mince&nbsp;», et l'outil n'en tire aucune conclusion.

### La CVaR {#cvar}

La CVaR répond à la question que la VaR laisse ouverte&nbsp;: les jours où le seuil est franchi, combien perd-on en moyenne&nbsp;? C'est la moyenne des rendements qui atteignent le seuil de la VaR historique, écrite en perte.

$$CVaR_{α} = −(r_{(1)} + r_{(2)} + … + r_{(k)}) / k$$

Ici, $r_{(1)}$ est le plus mauvais rendement, $r_{(2)}$ le suivant, et $k$ le nombre de jours qui atteignent le seuil, donné dans les détails du calcul («&nbsp;Séances dans la queue&nbsp;»).

**Hypothèses.** Aucune loi n'est supposée, comme pour la VaR historique.

**Limites.** C'est une moyenne de peu de jours, et à 99&#x202F;% de quelques-uns&nbsp;: chacun pèse lourd, et l'outil le rappelle en permanence sous la CVaR à 99&#x202F;%. Elle est refusée avec la VaR historique du même niveau. Un prochain mauvais jour peut être plus dur que cette moyenne.

## Au pire {#au-pire}

### La perte maximale {#perte-maximale}

La perte maximale est la pire chute de la fenêtre, d'un plus haut au plus bas qui le suit&nbsp;: chaque jour, l'écart entre la valeur et le plus haut atteint jusque-là, puis le plus grand de ces écarts.

$$perte maximale = min_{t} (V_{t} / M_{t} − 1)$$

Ici, $M_{t}$ est le plus haut atteint jusqu'au jour $t$ inclus. Ce plus haut est glissant&nbsp;: jamais un plus haut venu après la baisse, qui mesurerait une perte que personne n'a pu subir. Le retour au pic est le premier jour, après le creux, où la valeur retrouve ce plus haut&nbsp;; s'il n'a pas eu lieu avant la fin de la fenêtre, la page le dit.

**Hypothèses.** Les poids d'aujourd'hui, appliqués chaque jour, comme pour toutes les mesures du temps ordinaire.

**Limites.** C'est la pire baisse de cette fenêtre seulement&nbsp;; une prochaine peut être plus forte. Les crises plus anciennes sont rejouées à part, en section 5.

### La courbe de valeur {#courbe-de-valeur}

La courbe suit un dollar placé au début de la fenêtre, avec les poids d'aujourd'hui. Elle part de 1 la veille du premier rendement retenu&nbsp;: sans ce point de départ, une baisse dès le premier jour échapperait à la perte maximale.

$$V_{t} = V_{t−1} × (1 + r_{p,t})$$

## Qui porte le risque {#qui-porte}

### Les lignes effectives {#lignes-effectives}

En capital, le nombre de lignes effectives est le nombre de lignes de même montant qui donneraient la même concentration. En risque, la même formule s'applique aux parts des variations $c_{i}$, présentées juste après.

$$N_{capital} = 1 / (w_{1}^{2} + … + w_{N}^{2})$$

$$N_{risque} = 1 / (c_{1}^{2} + … + c_{N}^{2})$$

Avec $N$ lignes de même montant, le premier vaut $N$&nbsp;; plus quelques lignes dominent, plus il baisse&nbsp;: deux lignes de 90&#x202F;% et 10&#x202F;% de la valeur pèsent comme 1,2&nbsp;ligne de même montant. L'écart entre les deux dit que le risque ne se répartit pas comme l'argent.

**Hypothèses.** Des positions acheteuses&nbsp;: la mesure vient de l'indice de Herfindahl, la somme des carrés des poids, défini pour des parts positives.

**Limites.** En risque, le nombre peut descendre sous un quand une ligne a une part négative&nbsp;: la lecture en nombre de lignes n'est plus qu'une approximation, et la page le signale. Sous 3&nbsp;jours de bourse, il n'est pas chiffré.

### La part dans les variations {#part-des-variations}

La part d'une ligne dans les variations, ou contribution à la variance, tient compte de son poids et de la façon dont elle bouge avec les autres&nbsp;: de deux lignes de même poids et de même volatilité, celle qui suit le reste du portefeuille pèse davantage.

$$c_{i} = w_{i} (Σw)_{i} / (w^{T} Σ w)$$

Ici, $(Σw)_{i}$ est la covariance de la ligne $i$ avec le portefeuille. Les parts somment à 100&#x202F;%. L'écart, en points, est la part dans les variations moins la part dans la valeur.

**Hypothèses.** Les covariances de la fenêtre d'estimation, avec les poids d'aujourd'hui.

**Limites.** Une part dit de combien une ligne fait bouger le portefeuille, jamais dans quel sens&nbsp;: une ligne peut peser lourd dans les variations et rapporter en crise, ce que montre le tableau des apports (voir [les trois chiffres d'une crise](#trois-chiffres)). Négative, elle signale une ligne qui a évolué à rebours du reste et qui atténue les variations de l'ensemble. Sous 3&nbsp;jours de bourse, les parts ne sont pas chiffrées.

### La corrélation {#correlation}

La corrélation mesure le lien entre les variations de deux lignes, de −1 à +1&nbsp;: +1 si elles bougent toujours ensemble, dans le même sens et en proportion, 0 sans lien de ce genre, −1 toujours en sens inverse.

$$ρ_{ij} = σ_{ij} / (σ_{i} σ_{j})$$

Ici, $σ_{ij}$ est la covariance des deux lignes, $σ_{i}$ et $σ_{j}$ leurs écarts-types, tous tirés du même tableau, sur les mêmes jours&nbsp;: estimées paire par paire, sur des jours différents, les corrélations pourraient former un tableau incohérent. La carte les colore sur une échelle fixe, la même pour tout portefeuille, et écrit chaque valeur.

**Hypothèses.** Un lien linéaire, c'est-à-dire proportionnel, et stable sur la fenêtre.

**Limites.** Un lien mesuré en temps ordinaire peut devenir plus fort en crise. Sous 3&nbsp;jours de bourse, la corrélation n'est pas chiffrée&nbsp;: avec deux jours, elle vaudrait +1 ou −1 quelles que soient les lignes.

## En crise {#en-crise}

### Le rejeu {#rejeu}

La section 5 rejoue trois grandes crises sur votre portefeuille actuel&nbsp;: la Crise financière 2008, le Krach COVID et le Resserrement monétaire 2022. Chacune va du sommet de clôture du S&P 500 à son point bas&nbsp;; des tests vérifient ces dates sur l'historique en base.

Au premier jour, chaque ligne pèse son poids d'aujourd'hui&nbsp;; les quantités qui en découlent sont ensuite figées. Rien n'est acheté ni vendu&nbsp;: les poids dérivent avec les cours, comme chez un porteur qui ne touche à rien, et les dividendes comptent, réinvestis.

$$q_{i} = w_{i} / P_{i,0}$$

$$V_{t} = q_{1} P_{1,t} + … + q_{N} P_{N,t}$$

C'est une autre convention que celle des autres sections&nbsp;: sur plusieurs mois, des poids constants supposeraient de déplacer chaque jour de l'argent des lignes qui ont le mieux tenu vers celles qui viennent de chuter. Sur un seul jour, les deux conventions donnent le même chiffre.

### Les trois chiffres d'une crise {#trois-chiffres}

- **Au point bas du marché**&nbsp;: la valeur rejouée le dernier jour, quand le S&P 500 touche son point bas, rapportée à celle du premier, $V_{fin} / V_{début} − 1$. Le rejeu s'arrête là&nbsp;: il ne dit rien de la remontée qui a suivi.
- **Pire moment traversé**&nbsp;: la plus forte baisse pendant la crise, depuis le plus haut atteint pendant la crise, comme la perte maximale de la section 3. Elle peut être plus profonde que le premier chiffre. C'est la baisse du portefeuille entier, jamais la somme des pires moments de chaque ligne.
- **Couverture**&nbsp;: la part de la valeur d'aujourd'hui que représentent les lignes rejouées.

Les trois s'affichent à la même taille. Seul le premier reçoit un montant, sur la valeur d'aujourd'hui des lignes rejouées&nbsp;: le second se mesure depuis un plus haut qui peut dépasser le point de départ, et le multiplier par la valeur de départ ne donnerait aucune perte réelle.

L'apport d'une ligne, dans le tableau de la section 4, est sa variation de valeur rapportée à la valeur rejouée au premier jour&nbsp;; la somme des apports redonne le premier chiffre.

$$apport_{i} = (V_{i,fin} − V_{i,début}) / V_{début}$$

### La couverture {#couverture}

Une ligne est rejouée si elle était cotée pendant toute la crise. Sinon, l'outil ne la suppose pas stable, ce qui diluerait la perte dans une valeur non rejouée&nbsp;: il l'écarte et la nomme, rejoue les autres en ramenant leurs poids à 100&#x202F;%, et dit la part de la valeur couverte. Un point la signale dès qu'elle est incomplète. Le chiffre ne décrit alors que la partie rejouée&nbsp;: la perte de l'ensemble a pu être différente, dans un sens comme dans l'autre, et l'outil ne le mesure pas.

Sous 80&#x202F;% de la valeur, la partie rejouée ne représente plus assez l'ensemble&nbsp;: ses chiffres restent affichés à côté de leur couverture, mais aucune phrase ne les donne pour la perte de votre portefeuille. Sans aucune ligne rejouée, aucun chiffre n'est donné.

### La sensibilité au marché {#sensibilite}

Le bêta est la sensibilité de votre portefeuille au marché&nbsp;: de combien il a bougé en moyenne quand le S&P 500 bougeait de 1&#x202F;%, soit la pente de la droite qui relie, jour par jour, leurs rendements. Le R² est la part de ses variations qui suit le marché&nbsp;; la diversification, qui répartit la valeur entre plusieurs lignes, n'agit que sur le reste.

$$β = cov(r_{p}, r_{m}) / var(r_{m})$$

$$R^{2} = β^{2} × var(r_{m}) / var(r_{p})$$

Ici, $r_{p}$ et $r_{m}$ sont les rendements quotidiens du portefeuille et du S&P 500. Le tableau de chaque crise les donne en temps ordinaire, sur la fenêtre d'estimation, et en crise, sur les jours de la crise et la valeur rejouée&nbsp;: jamais moyennés. Après «&nbsp;±&nbsp;» vient l'erreur type de la pente, son incertitude, qui grandit quand la droite repose sur peu de jours ou que les points s'en écartent.

**Hypothèses.** Un lien linéaire et stable sur chaque période. Les rendements sont pris bruts, sans en retrancher celui d'un placement sans risque&nbsp;: retrancher un taux à peu près constant des deux côtés ne déplace pratiquement pas la pente.

**Limites.** Sous 60&nbsp;jours de bourse, une sensibilité de crise est donnée, mais l'outil n'en tire aucune conclusion. En couverture partielle, les deux sensibilités portent sur les mêmes lignes rejouées.

### Ce que la sensibilité laissait attendre {#attendu}

L'outil compare le rejeu à ce que la sensibilité de temps ordinaire laissait attendre, face à la variation du S&P 500 pendant la crise.

$$attendu = exp(β × ln(1 + R_{m})) − 1$$

Ici, $R_{m}$ est la variation du S&P 500 sur la crise. Le calcul passe par les logarithmes parce qu'il met à l'échelle une variation de plusieurs mois&nbsp;: multiplier la baisse de l'indice par le bêta donnerait un autre chiffre. L'écart entre l'attendu et le rejeu est le résultat. L'attendu suppose une sensibilité inchangée en crise&nbsp;: c'est précisément ce que la comparaison met à l'épreuve.

## Ce que le moteur en dit {#moteur}

### Les constats {#constats}

Les constats de la section 6 sont écrits par le moteur de règles, la partie de l'outil qui met les chiffres en phrases, à partir des chiffres déjà calculés&nbsp;: il ne calcule rien de plus. Ils décrivent sans jamais dire quoi faire, et chacun indique les seuils sur lesquels il repose et d'où ils viennent. Deux constats, «&nbsp;Combien de lignes, en réalité&nbsp;» et «&nbsp;Part qui suit le marché&nbsp;», n'en ont aucun tant que la fenêtre compte assez de jours&nbsp;: leur mesure parle d'elle-même.

Un seuil est une frontière posée d'avance, la même pour tout portefeuille&nbsp;; une référence est une valeur calculée sur votre portefeuille, à laquelle une mesure se compare. Chaque ligne de seuil dit d'où vient sa valeur&nbsp;: «&nbsp;choisi à la main (non dérivé des données)&nbsp;», «&nbsp;démontré (le même pour tout portefeuille)&nbsp;» ou «&nbsp;calculée sur ce portefeuille&nbsp;». Un point de couleur précède les seuils choisis à la main.

### Les cinq seuils choisis à la main {#seuils-choisis}

Ils sont cinq dans tout l'outil, et leur rareté est voulue&nbsp;: un nombre rond choisi à la main n'est qu'un dernier recours.

- «&nbsp;corrélation forte = 0,70&nbsp;»&nbsp;: une convention usuelle pour dire qu'une corrélation est forte&nbsp;; aucun calcul sur votre portefeuille ne la produit. Quand aucune paire ne l'atteint, le constat cite la paire la plus corrélée.
- «&nbsp;couverture minimale d'un scénario = 80&#x202F;%&nbsp;», un scénario étant une crise rejouée&nbsp;: à 80&#x202F;%, même si la partie absente avait perdu deux fois plus que la partie rejouée, la perte de l'ensemble ne dépasserait le chiffre affiché que d'un cinquième, contre moitié plus à 50&#x202F;%.
- «&nbsp;nombre minimal de séances d'une régression = 60&nbsp;»&nbsp;: une régression calcule une pente, comme celle de la sensibilité au marché. Ces jours font environ trois mois&nbsp;; en deçà, quelques journées extrêmes dictent la pente à elles seules. Les chiffres qui reposent sur moins de jours sont donnés et signalés, et une crise ainsi estimée n'entre dans aucune conclusion.
- «&nbsp;$ν$ maximal d'une loi de Student = 30&nbsp;»&nbsp;: au-delà, la loi de Student ne se distingue plus de la loi normale. À variance égale, sa VaR à 99&#x202F;% s'en écarte de 2,05&#x202F;% de sa valeur au plus, bien moins que l'incertitude de l'estimation elle-même&nbsp;: l'outil ne publie pas un nombre de degrés de liberté qui ne mesure plus rien.
- «&nbsp;nombre minimal de séances pour estimer une loi = 30&nbsp;»&nbsp;: une convention usuelle, dite du «&nbsp;grand échantillon&nbsp;», l'échantillon étant l'ensemble des jours observés&nbsp;; aucun calcul sur votre portefeuille ne la produit. Avec 30&nbsp;jours de bourse, si les variations suivent une loi normale, l'écart-type varie déjà d'environ 13&#x202F;% d'une période à l'autre, et une loi de Student reposerait sur un ou deux jours extrêmes. En deçà, la loi de Student n'est pas ajustée, la volatilité et la VaR normale sont marquées «&nbsp;Estimation mince&nbsp;», et aucune règle ne les lit.

### Les seuils démontrés {#seuils-demontres}

- «&nbsp;nombre minimal de séances estimables = 3&nbsp;»&nbsp;: avec deux jours, une corrélation vaut +1 ou −1 quelles que soient les lignes, une pente passe exactement par les deux points, et les parts des variations ne décrivent qu'un seul écart entre deux jours. Ce ne sont plus des mesures mais des identités, des valeurs que le calcul impose quelles que soient les données.
- «&nbsp;nombre minimal de séances d'une VaR historique à 95&#x202F;% = 20&nbsp;» et «&nbsp;nombre minimal de séances d'une VaR historique à 99&#x202F;% = 100&nbsp;»&nbsp;: la part la plus mauvaise des jours en compte $n × (1 − α)$. Quand ce compte est inférieur à un, aucun jour n'y tombe, et le chiffre ne serait que le pire jour de la fenêtre, pas un quantile. La CVaR du même niveau, qui moyenne cette part, tombe avec elle.

$$n ≥ 1 / (1 − α)$$

### Les références {#references}

La part d'une ligne dans la valeur du portefeuille, à laquelle se compare sa part dans les variations&nbsp;; la corrélation de la paire la plus corrélée, citée quand aucune paire n'atteint 0,70. Leur ligne dit «&nbsp;calculée sur ce portefeuille&nbsp;»&nbsp;: leur valeur change avec lui.

### Quand l'outil refuse un chiffre {#refus}

L'outil refuse un chiffre quand il ne dépend plus des données, ou qu'il n'est plus la mesure annoncée&nbsp;; il le donne en le signalant quand il en dépend seulement mal. Un chiffre refusé laisse sa place à un tiret court, que les lecteurs d'écran lisent «&nbsp;non disponible&nbsp;», et à sa raison, en clair.

- Sous 3&nbsp;jours de bourse&nbsp;: corrélation, sensibilité au marché, parts des variations et lignes effectives en risque.
- Sous 20&nbsp;jours de bourse à 95&#x202F;%, et sous 100&nbsp;jours de bourse à 99&#x202F;%&nbsp;: VaR historique et CVaR du niveau.
- Sous 30&nbsp;jours de bourse, ou avec 2&nbsp;degrés de liberté ou moins, ou plus de 30&nbsp;degrés de liberté&nbsp;: VaR de Student.
- Une crise que ne couvre aucune ligne&nbsp;: tous ses chiffres. Sous 80&#x202F;% de la valeur couverte&nbsp;: aucune perte n'est donnée pour l'ensemble.

Une estimation signalée comme mince n'entre dans aucune conclusion&nbsp;: un chiffre qu'on vient de juger fragile ne peut pas servir ensuite de preuve.
