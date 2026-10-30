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

## Omejitve

To je deterministični MVP, ne klinični sistem in ne individualna presoja trenerja. V tej fazi še ni shranjevanja profila, dnevnika izvedenih treningov, samodejnega spremljanja odziva ali longitudinalne periodizacije. API je zaščiten z obstoječim pilotnim žetonom. Brez ključa za model ne nastajajo stroški modela.
