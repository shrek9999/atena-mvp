# ATENA – faza 2: deterministični sestavljalnik programov

## Vhodni profil

Obvezna polja:
- `goal`: `hypertrophy`, `strength`, `general_fitness`, `functional` ali `power`
- `experience`: `beginner`, `intermediate` ali `advanced`
- `equipment`: seznam opreme, ki je dejansko na voljo
- `sessions_per_week`: 2, 3 ali 4
- `session_minutes`: 25–120 minut

Neobvezno:
- `excluded_exercise_ids`, `excluded_patterns`: vaje oziroma vzorci, ki jih generator ne sme izbrati
- `include_accessories`: enosklepne dopolnilne vaje; dovoljeno samo naprednim vadečim

## Načela

- Za gibalni vzorec, ki se v angleščini pogosto označuje kot *hip hinge*, uporabljamo slovensko poimenovanje **predklon z ravnim hrbtom**.

- Izbor uporablja izključno preverjeni katalog; jezikovni model ne izmišlja vaj.
- Pri hipertrofiji so privzeto izbrane večsklepne vaje. Enosklepne dopolnilne vaje so opt-in za napredne.
- Predloge so zasnovane kot treningi celotnega telesa z razporeditvijo osnovnih gibalnih vzorcev.
- Predpis vključuje serije, razpon ponovitev, RIR in odmor.
- Ocena trajanja vključuje 6-minutno ogrevanje, čas izvedbe, odmore in prehode; rezultat je približek in se primerja z razpoložljivim časom.
- Generator vrne pregled tedenskih delovnih serij in izpostavljenosti primarnih mišičnih skupin. Slednja ni enaka neposrednemu volumnu za posamezno mišico.
- Progresija je dvojna progresija; razbremenitev je vezana na odziv, ne na avtomatičen koledarski teden.
- Izključitve se spoštujejo, vendar generator ne diagnosticira in ne presoja zdravstvene primernosti vaje.

## Uporaba

```python
from training.program import generate_program

plan = generate_program({
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": ["barbell", "rack", "dumbbell", "bench"],
    "sessions_per_week": 2,
    "session_minutes": 60,
})
```

## API in stanje integracije

Osnovni zaščiten endpoint `POST /coach/program` ostaja stateless in združljiv z obstoječim klicem. Razširitev profila in zgodovine je opisana v [fazi 2.1 – profil, zgodovina programa in dnevnik treningov](PHASE2_PROFILE_HISTORY.md). Novi endpointi omogočajo shranjevanje profila, ustvarjenih programov, dnevnika serij in strukturiranih povratnih informacij.

## Omejitve

To je deterministični MVP, ne klinični sistem in ne individualna presoja trenerja. Backend hrani podatke v SQLite, vendar trenutna brezplačna Render storitev nima priključene trajne podatkovne baze ali potrjenega trajnega diska. Zato je trajna hramba na gostovanem pilotu še odprta infrastrukturna zahteva. Spletni vmesnik še ni povezan z novimi endpointi. Brez novega plačljivega modelnega API-ja ne nastajajo stroški modela.
