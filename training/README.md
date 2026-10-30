# ATENA – katalog vaj (faza 1)

Ta modul je prva, samostojna podatkovna osnova za izbor vaj. Ne generira še celotnega vadbenega programa in ne nadomešča strokovne presoje.

## Struktura zapisa

Vsaka vaja ima stabilen ID, slovensko in angleško ime, gibalni vzorec, tip sklepanja (večsklepna/enosklepna), cilje, opremo, zahtevnost, primarne in sekundarne mišične skupine, tehnične usmeritve, pogoste napake, regresije, progresije, alternative in opozorila.

## Trenutni obseg

Katalog vključuje osnovne vzorce počepa, kolčnega pregiba, izpadnih korakov, potiskov, vlekov, nošenja, antirotacije, stabilizacije trupa, skokov in eksplozivnega kolčnega pregiba. Med izpadnimi koraki so počep na mestu, izpadni korak naprej/nazaj, bolgarski počep in ATG različica.

## Pravila izbora

- Pri cilju hipertrofije so privzeto vključene večsklepne vaje.
- Enosklepne dopolnilne vaje so na voljo le, ko klicatelj izrecno nastavi `include_accessories=True`.
- Polje `equipment` vsebuje obvezno opremo (zahtevani so vsi elementi); `equipment_any` vsebuje možnosti, pri katerih zadošča vsaj ena razpoložljiva. Telesna teža je vedno dovoljena.
- Filtri so deterministični in ne sklepajo o poškodbah ali diagnozah.
- Polje `warnings` opozarja na tehnične oziroma izvedbene omejitve; ne predstavlja medicinske presoje.

## Uporaba

```python
from training.catalogue import get_exercises, get_exercise

main_lifts = get_exercises(
    goal="hypertrophy",
    equipment={"barbell", "rack", "dumbbell", "bench"},
    patterns={"squat", "hinge", "lunge"},
)
accessories = get_exercises(
    goal="hypertrophy",
    equipment={"dumbbell"},
    include_accessories=True,
)
```

## Omejitve in naslednji korak

Katalog je začetna kurirana različica, ne popolna knjižnica. Pred javno uporabo je treba strokovno pregledati posamezne opise, opozorila, regresije/progresije in dodati še opremo ter variacije, ki jih dejansko podpirajo demonstracije. Naslednja faza bo deterministični sestavljalnik programa z validacijo tedenskega volumna, ravnotežja vzorcev, intenzivnosti, počitkov in trajanja treninga.
