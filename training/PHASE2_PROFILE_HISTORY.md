# ATENA – faza 2.1: profil, zgodovina programa in dnevnik treningov

## Namen

Ta razširitev poveže deterministični generator iz faze 2 s ponovljivim uporabniškim profilom in zgodovino dejansko izvedenih treningov. Generator ostaja edini vir predpisanih vaj; povratna informacija se shrani in uporabi pri naslednjem programu.

## Podatkovni model

Shranjujejo se samo podatki, potrebni za sestavo in spremljanje treninga:
- cilj, izkušenost, razpoložljiva oprema, število treningov in prilagodljiv čas treninga;
- izključene vaje oziroma gibalni vzorci ter nastavitev dopolnilnih vaj;
- različice ustvarjenih programov;
- izvedene vaje, serije, ponovitve, uporabljena masa, RIR in trajanje treninga;
- strukturirana povratna informacija o zahtevnosti, dokončanosti, regeneraciji, nelagodju in nadzoru trupa.

Prosto besedilo o diagnozah, zdravstveni dokumentaciji, polnem imenu, e-pošti ali naslovu se v tej fazi ne zbira. Profilni ID je naključen. Osebni profilni ključ se shrani samo kot zgoščena vrednost; surovi ključ se vrne samo ob ustvarjanju profila.

## API

Vsi endpointi uporabljajo HTTPS v gostovanem okolju.

| Endpoint | Namen | Dostop |
|---|---|---|
| `POST /coach/profile` | Ustvari profil in izda osebni ključ | `X-Pilot-Token` |
| `GET /coach/profile` | Prebere profil | `X-Profile-Token` |
| `PUT /coach/profile` | Posodobi profil | `X-Profile-Token` |
| `POST /coach/programs` | Sestavi in shrani nov program iz profila | `X-Profile-Token` |
| `GET /coach/programs` | Vrne shranjene programe | `X-Profile-Token` |
| `POST /coach/workouts` | Zabeleži izvedbo serij in povratno informacijo | `X-Profile-Token` |
| `GET /coach/workouts` | Vrne zgodovino treningov | `X-Profile-Token` |
| `POST /coach/check-ins` | Zabeleži novo strukturirano samooceno | `X-Profile-Token` |

Pri dnevniku se preveri, ali so zabeležene vaje del izbranega shranjenega treninga. Vsaka serija lahko vsebuje ponovitve, maso v kilogramih in RIR. Podatki drugega profila niso dostopni z osebnim ključem prvega profila.

## Prilagajanje in varnost

- Naslednji program uporabi zadnjo shranjeno povratno informacijo.
- Težek ali nedokončan trening oziroma slaba regeneracija sproži že obstoječe konservativno zmanjšanje serij glavnih večsklepnih vaj.
- En sam lahek trening ne sproži samodejnega zvišanja obremenitve; ostane v veljavi pravilo dvojne progresije.
- Prijavljeno nelagodje ustavi samodejno prilagajanje in vrne HTTP 409.
- Nov check-in z izrecno samooceno `discomfort: no` omogoči ponovno generiranje. To je samo uporabnikova izjava o trenutnem stanju, ne zdravstvena presoja ali zdravniško dovoljenje za vadbo.

## Hramba podatkov in omejitve

Uporablja se standardna knjižnica Python `sqlite3`; dodatna knjižnica ali plačljiv API nista potrebna. Pot do baze določa `ATENA_DATABASE_PATH`, privzeto `data/atena.sqlite3`.

**Pomembno za trenutno gostovanje:** Render storitev ATENA je na brezplačnem načrtu, brez priključene baze Postgres ali potrjenega trajnega diska. Lokalni SQLite je zato primeren za razvoj in testiranje, vendar na trenutnem Render okolju ne zagotavlja ohranitve podatkov po ponovni namestitvi ali zamenjavi instance. Pred javnim pilotom je treba priključiti trajno shrambo in nastaviti `ATENA_DATABASE_PATH` nanjo. Tega koraka ni bilo mogoče varno opraviti brez odločitve o hrambi in morebitnih stroških.

Osebni ključ deluje kot skrivnost za dostop do profila. Trenutni skupni pilotni žeton za ustvarjanje profilov ni sistem uporabniških računov ali produkcijska avtentikacija. Ključa ne smemo vgraditi v javno spletno kodo. Spletni vmesnik še ni povezan s temi novimi endpointi.

## Lokalni zagon

```bash
export ATENA_DATABASE_PATH=./data/atena.sqlite3
export AI_COACH_TEST_TOKEN='local-pilot-secret'
pytest -q
```

Faza je backend MVP. Ne vključuje še uporabniškega vmesnika, prijave/registracije, pozabljene prijave, izvoza ali brisanja podatkov prek uporabniškega računa, šifriranja baze na ravni aplikacije, niti javne produkcijske aktivacije.
