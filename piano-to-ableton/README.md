# Piano → Ableton (+ AI-arrangeur)

Sluit je digitale piano via USB aan op je laptop, speel, en elke melodie die je
speelt komt automatisch als `.mid`-bestand in een map die je in Ableton Live kunt
openen. Wil je dat er een compleet stuk van gemaakt wordt, dan schrijft Claude
(AI) er een meersporig arrangement omheen: songstructuur, akkoorden, bas, drums,
pads en tegenmelodieën. Ook dat is gewoon MIDI, dus alles blijft te bewerken in Ableton.

```
 piano ──USB──▶ laptop ──▶ take_20260924_201512.mid              (jouw spel, precies zoals gespeeld)
                      └──▶ take_20260924_201512_arrangement.mid  (compleet stuk, één track per instrument)
```

## 1. Installeren op je MacBook (eenmalig)

1. Installeer Python 3.12, bijvoorbeeld met [Homebrew](https://brew.sh): `brew install python@3.12`
   (of download "Python 3.12" op [python.org](https://www.python.org/downloads/macos/)).
   De Python die bij macOS zit is te oud.
2. Dubbelklik in de Finder op `mac/Installeren.command`.
   Geeft macOS een waarschuwing, klik dan met rechts → *Open*.

In de map `mac/` staan daarna drie starters om te dubbelklikken:

| Bestand | Wat het doet |
|---|---|
| `Installeren.command` | eenmalige installatie |
| `Piano opnemen.command` | luistert naar de piano en bewaart elke melodie |
| `Laatste take naspelen.command` | de piano speelt je laatste opname na |

Liever de Terminal? Alles kan ook met `.venv/bin/python -m pianotool …` (zie hieronder).

## 2. Piano aansluiten

- De meeste digitale piano's hebben een **USB-B-poort ("USB to Host")**. Een
  USB-B-naar-USB-C-kabel naar je MacBook is genoeg. Een driver heb je niet nodig,
  macOS herkent de piano vanzelf.
- Heeft je piano alleen 5-pins **MIDI IN/OUT**, gebruik dan een USB-MIDI-interface
  (bv. Roland UM-ONE). Voor naspelen moeten dan beide kabels (IN en OUT) aangesloten zijn.

Controleer of de piano herkend wordt:

```bash
.venv/bin/python -m pianotool ports
```

Je ziet de ingangen (opnemen) en uitgangen (naspelen); die met `→` worden automatisch gekozen.
Zie je niets, kijk dan in *Audio MIDI-configuratie* → *Venster* → *Toon MIDI-studio*.

## 3. Opnemen en naspelen

```bash
.venv/bin/python -m pianotool record --bpm 90
```

- De opname start vanzelf bij de eerste toets.
- Na 4 seconden stilte (geen toetsen en geen sustainpedaal) wordt de take
  opgeslagen in `~/Music/Piano Takes/` en wacht het programma op de volgende.
- Aanslag (velocity) en sustainpedaal worden meeopgenomen. Stoppen met **Ctrl+C**.

**Naspelen:**

```bash
.venv/bin/python -m pianotool play laatste                # de piano speelt je laatste take na
.venv/bin/python -m pianotool play take_….mid             # een bepaalde take of arrangement
.venv/bin/python -m pianotool play arr.mid --virtual      # via GarageBand/Logic/Ableton, over de Mac-speakers
.venv/bin/python -m pianotool play arr.mid --track Piano  # alleen bepaalde tracks
```

- Op de piano speelt de piano zelf, met zijn eigen klank en speakers. Je ziet het ook
  op de toetsen bij piano's met verlichte toetsen.
- Met `--virtual` maakt het programma een MIDI-poort "Pianotool" aan. Open
  GarageBand (gratis op elke Mac) met een instrumenttrack en je hoort het via je
  MacBook. In Ableton zet je bij een MIDI-track *MIDI From* op "Pianotool". Zo hoor
  je een arrangement met drums, bas en strijkers in één keer.
- Speel je een arrangement naar de piano, dan speelt de piano alle partijen met
  pianoklank. Met `--track` kies je welke partijen.

Handige opties voor `record`:

| Optie | Betekenis |
|---|---|
| `--bpm 90` | het tempo waarin je (ongeveer) speelt; zet Ableton op hetzelfde tempo |
| `--playback` | elke take direct laten naspelen (de echo wordt niet opnieuw opgenomen) |
| `--silence 6` | pas na 6 s stilte een nieuwe take |
| `--out "pad/naar/map"` | andere opslagmap |
| `--port "Yamaha"` / `--to "Yamaha"` | een specifieke MIDI-ingang / -uitgang kiezen |
| `--arrange` | elke take direct door de AI laten uitwerken (zie 5) |

## 4. In Ableton Live

1. Sleep de map `Piano Takes` één keer naar **Places** in de browser (linkerzijbalk).
   Nieuwe takes verschijnen daar vanzelf.
2. Sleep een `.mid`-bestand in een MIDI-track (of in een lege plek → Ableton maakt
   tracks aan). Een arrangement-bestand geeft een track per instrument.
3. Zet het tempo van je set gelijk aan de `--bpm` die je gebruikte, dan staan de
   noten op de juiste maten. Kies zelf de instrumenten (Ableton negeert de General
   MIDI-klanken; de tracknamen vertellen wat bedoeld is).

> Tip: speelde je zonder metronoom, gebruik dan in Ableton *Quantize* (Ctrl/Cmd+U)
> of kijk met `.venv/bin/python -m pianotool analyze take.mid` wat het geschatte tempo is.

## 5. AI: een compleet muziekstuk maken

Maak een API-sleutel aan op [console.anthropic.com](https://console.anthropic.com)
en zet die in je omgeving:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc   # daarna een nieuw Terminal-venster openen
```

Dan een bestaande take laten uitwerken:

```bash
.venv/bin/python -m pianotool arrange ~/Music/"Piano Takes"/take_20260924_201512.mid \
    --style "melancholische indie-pop, 80 bpm feel, piano, strijkers, lichte drums" \
    --bars 48
```

Of direct tijdens het spelen: `.venv/bin/python -m pianotool record --bpm 90 --arrange --style "..."`.
Beluisteren: `.venv/bin/python -m pianotool play …_arrangement.mid --virtual`.

Wat je terugkrijgt:

- `…_arrangement.mid`: de tracks. Jouw eigen take staat er **ongekwantiseerd**
  in (met jouw timing en aanslag) op de plekken waar het thema terugkomt; de AI
  schrijft de rest eromheen.
- `…_arrangement.json`: titel, toonsoort, uitleg en de songstructuur (intro,
  couplet, refrein…), handig als markers in Ableton.

Een arrangement duurt meestal een paar minuten en kost meestal minder dan een euro
aan API-gebruik. Met `--effort medium` gaat het sneller en goedkoper, met `--effort max`
denkt het model langer na.

## Welke AI-tools passen hier het best bij? (september 2026)

| Tool | Wat het doet met jouw melodie | Uitvoer | Past bij |
|---|---|---|---|
| **Deze tool (Claude)** | schrijft volledig arrangement om je MIDI heen | MIDI, per instrument | je wilt zelf in Ableton produceren en alles kunnen aanpassen |
| **[Suno Studio 2.0](https://suno.com/blog/studio-2)** | importeert je `.mid` en gebruikt de clip als prompt voor nieuwe audio-stems; kan ook zang toevoegen | audio (WAV-stems) + MIDI-export | je wilt snel een af, geproduceerd nummer *met klank*, ook met zang |
| **[MIDI Agent](https://www.midiagent.com/ai-midi-generator-for-ableton-live)** | plugin in Ableton; genereert akkoorden, bas, drums, varianten en vervolgen op basis van je MIDI (werkt met o.a. Claude/ChatGPT) | MIDI, binnen Ableton | je wilt de AI rechtstreeks in je Ableton-set |
| **[Logic Pro Session Players](https://support.apple.com/guide/logicpro/session-players-overview-lgcpbf624405/mac)** (Mac) | AI-drummer, -bassist, -toetsenist en -strijkers spelen mee met de akkoorden van je melodie; Logic kan ook akkoorden uit je MIDI halen | MIDI per speler | je wilt een realistische "band" om je piano heen op je Mac |
| **[AIVA](https://www.aiva.ai/)** | gebruikt je MIDI (vanaf 8 maten) als "influence" en componeert een nieuw, volledig stuk in die stijl | MIDI, WAV, MP3 | filmische/klassieke stukken; let op: het wordt een *nieuw* stuk, niet jouw melodie |
| **Ableton Live 12 MIDI Tools** (Seed, Stacks, Shape…) | algoritmische variaties op clips | MIDI | snelle variaties; let op: geen echte AI |

**Aanbevolen werkwijze:**

1. Opnemen met deze tool → `.mid` in Ableton.
2. Arrangement laten maken met `arrange` → instrumenten kiezen in Ableton en verder produceren.
3. Wil je horen hoe het klinkt als volledig geproduceerd nummer (of met zang)?
   Upload de take of het arrangement in **Suno Studio** en exporteer de stems terug naar Ableton.

## Probleemoplossing

- **"Geen piano gevonden"**: piano aan? Andere USB-kabel of -poort proberen (sommige
  kabels laden alleen op), en in *Audio MIDI-configuratie* → *MIDI-studio* kijken of hij verschijnt.
- **Naspelen geeft geen geluid**: staat *Local Control* aan en het volume open? Sommige
  piano's hebben een instelling "MIDI In" of "USB MIDI" die aan moet.
- **Takes worden te vroeg afgebroken**: verhoog `--silence`.
- **Ableton gebruikt de piano tegelijk**: dat mag; op macOS kunnen meerdere
  programma's dezelfde piano tegelijk gebruiken.

## Ontwikkelen

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```
