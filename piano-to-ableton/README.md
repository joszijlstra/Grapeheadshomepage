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

## 1. Installeren (eenmalig)

Je hebt [Python 3.10 of nieuwer](https://www.python.org/downloads/) nodig.

```bash
cd piano-to-ableton
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Piano aansluiten

- De meeste digitale piano's hebben een **USB-B-poort ("USB to Host")**: een gewone
  USB-printerkabel naar je laptop is genoeg, geen driver nodig (class compliant).
- Heeft je piano alleen 5-pins **MIDI OUT**, gebruik dan een USB-MIDI-interface
  (bv. Roland UM-ONE of M-Audio Uno).

Controleer of de piano herkend wordt:

```bash
python -m pianotool ports
```

De poort met een `→` wordt automatisch gekozen.

## 3. Opnemen

```bash
python -m pianotool record --bpm 90
```

- De opname start vanzelf bij de eerste toets.
- Na 4 seconden stilte (geen toetsen en geen sustainpedaal) wordt de take
  opgeslagen in `~/Music/Piano Takes/` en wacht het programma op de volgende.
- Aanslag (velocity) en sustainpedaal worden meeopgenomen. Stoppen met **Ctrl+C**.

Handige opties:

| Optie | Betekenis |
|---|---|
| `--bpm 90` | het tempo waarin je (ongeveer) speelt; zet Ableton op hetzelfde tempo |
| `--silence 6` | pas na 6 s stilte een nieuwe take |
| `--out "pad/naar/map"` | andere opslagmap |
| `--port "Yamaha"` | een specifieke MIDI-ingang kiezen |
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
> of kijk met `python -m pianotool analyze take.mid` wat het geschatte tempo is.

## 5. AI: een compleet muziekstuk maken

Maak een API-sleutel aan op [console.anthropic.com](https://console.anthropic.com)
en zet die in je omgeving:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows (PowerShell): $env:ANTHROPIC_API_KEY="sk-ant-..."
```

Dan een bestaande take laten uitwerken:

```bash
python -m pianotool arrange ~/Music/"Piano Takes"/take_20260924_201512.mid \
    --style "melancholische indie-pop, 80 bpm feel, piano, strijkers, lichte drums" \
    --bars 48
```

Of direct tijdens het spelen: `python -m pianotool record --bpm 90 --arrange --style "..."`.

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
| **Ableton Live 12 MIDI Tools** (Seed, Stacks, Shape…) | algoritmische variaties op clips | MIDI | snelle variaties; let op: geen echte AI |

**Aanbevolen werkwijze:**

1. Opnemen met deze tool → `.mid` in Ableton.
2. Arrangement laten maken met `arrange` → instrumenten kiezen in Ableton en verder produceren.
3. Wil je horen hoe het klinkt als volledig geproduceerd nummer (of met zang)?
   Upload de take of het arrangement in **Suno Studio** en exporteer de stems terug naar Ableton.

## Probleemoplossing

- **"Geen piano gevonden"**: piano aan? Andere USB-kabel/poort proberen; op
  macOS in *Audio MIDI-configuratie* → *MIDI-studio* kijken of hij verschijnt.
- **Takes worden te vroeg afgebroken**: verhoog `--silence`.
- **Ableton gebruikt de piano tegelijk**: dat mag; beide programma's kunnen
  op macOS dezelfde MIDI-ingang lezen. Op Windows kan een poort soms maar door één
  programma geopend worden; sluit dan Ableton tijdens het opnemen of gebruik
  [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html).

## Ontwikkelen

```bash
pip install pytest
python -m pytest
```
