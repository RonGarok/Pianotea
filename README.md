# Pianotea Piano App

Application de piano MIDI open source inspirée du principe de Synthesia.

## Prérequis

- Python 3.12 ou plus
- Windows 10/11
- Un clavier MIDI physique comme le Yamaha P-45

## Installation

Ouvrez PowerShell dans le dossier du projet puis exécutez :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Pour le son réaliste, installez aussi FluidSynth pour Windows et placez une banque
General MIDI `.sf2` dans `assets/`, ou définissez la variable `PIANOTEA_SOUNDFONT`
vers son chemin complet. Par exemple dans PowerShell :

```powershell
$env:PIANOTEA_SOUNDFONT = "C:\chemin\vers\GeneralUser-GS.sf2"
```

Sans banque SoundFont ou sans FluidSynth natif, l'application utilise automatiquement
le synthétiseur de secours intégré.

## Lancement

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

## Utilisation

1. Connectez votre clavier MIDI (Yamaha P-45).
2. Chargez un fichier `.mid` ou `.midi` avec le bouton `Ouvrir MIDI`.
3. Cliquez sur `Play` : le son logiciel est activé par défaut et sort directement par les haut-parleurs du PC.
4. Sélectionnez une piste, puis l'instrument GM souhaité.
5. Décochez `Son logiciel` uniquement si vous voulez couper le son.
6. Pour utiliser un clavier MIDI, cochez `Activer MIDI`, puis sélectionnez le port dans `MIDI Input`.
7. En mode `Learning`, jouez les notes attendues sur votre clavier MIDI.

## Notes techniques

- L'interface est construite avec PySide6.
- Les fichiers MIDI sont analysés avec `mido`.
- La détection des périphériques MIDI utilise `python-rtmidi`.
- Le clavier virtuel couvre la plage MIDI 21 à 108, soit A0 à C8.

## Limitations

- `python-rtmidi` dépend de la disponibilité du driver MIDI du système.
- La détection de port peut varier selon le système d'exploitation et le pilote MIDI installé.
- Le son de lecture utilise le synthétiseur logiciel intégré à l'application et ne nécessite aucun périphérique MIDI.
- `python-rtmidi` est optionnel et sert uniquement aux périphériques MIDI physiques.
- L'édition de MIDI ou le rendu avancé peut nécessiter des améliorations futures.
