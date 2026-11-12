# Clipping-Business: Plan & Werkzeuge

Stand: 12.11.2026

## 1. Ablauf (Pipeline)

```
[1 Quelle]  ->  [2 Analyse]  ->  [3 Auswahl]  ->  [4 Schnitt]  ->  [5 Veredeln]  ->  [6 Posten]  ->  [7 Auswerten]
 VOD + Chat     Audio, Chat,     Top-Momente      9:16, Länge     Untertitel,      TikTok,        Views, Retention
 laden          Transkript       prüfen (Mensch)  20-60 s         Hook, Titel      Shorts, Reels  -> Gewichte anpassen
```

| Schritt | Werkzeug (heute) | Ausbau |
|---|---|---|
| 1 Quelle | VOD-Datei, Chat via [TwitchDownloader](https://github.com/lay295/TwitchDownloader) (JSON) | Automatischer Download neuer VODs |
| 2 Analyse | `clipper.py find` (Lautstärke + Chat) | + Whisper-Transkript, Lacher/Keywords, LLM-Bewertung |
| 3 Auswahl | `kandidaten.json` ansehen, schlechte löschen | Vorschau-Seite mit Ja/Nein |
| 4 Schnitt | `clipper.py cut --vertical` | Face-Cam oben / Gameplay unten (Split-Layout) |
| 5 Veredeln | – | Untertitel einbrennen (Whisper), Hook-Text, Zoom |
| 6 Posten | manuell | Planer / Upload-APIs |
| 7 Auswerten | – | Views pro Clip erfassen, Score-Gewichte lernen |

## 2. Recherche: KI-Tools

**Fertige Dienste (Abo):**
- **Eklipse** – stärkste Erkennung speziell für Gaming-VODs; Clips nur in Bezahlplänen (ca. 25 $/Monat).
- **OpusClip** – beste Untertitel & Editor, aber eher für Talk/Podcast; analysiert keinen Twitch-Chat.
- **StreamLadder** – sehr guter 9:16-Editor für Clips, die man selbst ausgewählt hat; KI-Clipping kostet extra.
- **Powder.gg** – Alternative zu Eklipse für Gaming.

**Open Source (lokal, kostenlos, anpassbar):**
- **faster-whisper / WhisperX** – Transkription & Wort-Zeitstempel (für Untertitel und Keyword-Suche).
- **zhouxiaoka/autoclip** – Whisper + LLM sucht Highlights, schneidet automatisch.
- **artbyjazi/autoclip** – lokal mit Whisper + Ollama, 9:16, Untertitel, Speaker-Tracking.
- **nirvagold/stream-clipper** – Audio-Spikes + Chat-Aktivität (liest TwitchDownloader-JSON).
- **auto-editor** – entfernt Stille automatisch (Jump-Cuts).

**Empfehlung:** Eigene Pipeline (dieses Repo) als Kern, weil Chat-Signale + eigene Bewertung den Unterschied machen; für schnelle Ergebnisse parallel Eklipse testen und vergleichen.

## 3. Geld verdienen
- **Content Rewards (früher „Whop Clipping“)**, ClipAffiliates, Vyro: Bezahlung pro 1.000 verifizierte Views, meist ca. 0,50–3 $ (Median ca. 1 $). Budget pro Kampagne ist begrenzt.
- **Direkt mit Streamern** (Discord, DMs): Festpreis oder pro View.
- **Rechte:** Nur Streamer clippen, die das erlauben (Kampagne oder schriftliche Zustimmung). Vorsicht mit Musik im Stream (Copyright-Strikes).

## 4. Sub-Agents im Business
| Agent | Aufgabe | Parallel? |
|---|---|---|
| Scout | Neue Kampagnen/Streamer suchen, Raten vergleichen | ja |
| Analyst | Pro VOD Highlights finden (ein Agent pro VOD) | ja |
| Editor | Kandidaten schneiden, Untertitel, Hook | ja, pro Clip |
| Texter | Titel, Beschreibung, Hashtags je Plattform | ja |
| Prüfer | Qualitätskontrolle: Länge, Ton, Rechte, Duplikate | nach Editor |
| Auswerter | Views sammeln, Gewichte in `clipper.py` anpassen | wöchentlich |

## 5. Fehlerbehandlung
- Jeder Schritt prüft sein Ergebnis (z. B. Clip-Auflösung 1080×1920, Dauer, Ton vorhanden).
- Kleine Fehler (falscher Parameter, Format) behebe ich selbst und melde es.
- Größere Entscheidungen (Rechte, Geld, Posten in deinem Namen) frage ich immer vorher.
