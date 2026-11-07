# ATENA CORE 2.0 — stabilizacija podatkovne in odločitvene osnove

**Status:** predlog arhitekture za fazno izvedbo  
**Osnova:** `phase-18-athlete-history-integration`  
**Omejitev:** ta dokument ne dovoljuje migracije produkcijske baze, spremembe produkcijskih nastavitev ali deploya.

## 1. Produktna meja

Primarni produkt za naslednjo validacijsko fazo je **ATENA Coach**: digitalni trener za končnega uporabnika, ki vodi začetno oceno, pripravi individualen program, zbira izvedbo in odziv ter varno prilagaja nadaljnjo vadbo.

Odločitveni sistem ATENA za druge AI-agente ostane ločena produktna/integra­cijska plast. Lahko uporablja skupna preverjena pravila in podatkovne pogodbe, vendar ne sme narekovati uporabniškega toka Coach ali povzročiti, da se B2B API, MCP, obračunavanje in agentna integracija obravnavajo kot že dokončan B2C trener.

**Načelo:** en strokovni vir pravil, ločeni produktni vmesniki in jasne meje podatkov.

## 2. Zakaj je potrebna stabilizacija

Trenutna osnova že vključuje:
- različico 1 kanoničnega stanja športnika z izvorom podatkov;
- povezavo profila s kanoničnim stanjem;
- oceno gibalnih nalog in kontekst simptomov;
- zgodovino treningov in več modulov za prilagajanje;
- deterministični generator ter obsežno regresijsko testiranje.

Pred razširitvijo funkcionalnosti je treba odpraviti štiri sistemska tveganja:

1. **Podatkovna nedoslednost:** profil in trening sta shranjena kot serializirana JSON-podatka, medtem ko manjkajo jasni, trajni zapisi za posamezne izvedene serije, različice programa in odločitve prilagajanja.
2. **Nejasen življenjski cikel sheme:** `coach_store._init()` izvaja ustvarjanje tabel, indeksov in varnostnih nastavitev ob običajnih operacijah shrambe. To je treba nadomestiti z nadzorovanimi, različicami označenimi migracijami.
3. **Več možnih odločevalcev:** več modulov izračuna signale za prilagajanje. Potreben je en končni orkestrator, ki določi prednost in izhod, specialistični moduli pa ostanejo ponudniki dokazov.
4. **Nezaključen dokaz kakovosti:** uspešni avtomatizirani testi dokazujejo predvsem tehnično regresijsko pravilnost. Ne dokazujejo strokovne kakovosti vseh programov, varnosti vseh odzivov modela ali pripravljenosti na plačljive uporabnike.

## 3. Ciljna arhitektura

### 3.1 Kanonično stanje športnika
En veljaven, različicami označen profil vsebuje:
- cilj in poudarek;
- izkušnje, opremo in razpoložljivost;
- samoporočane sposobnosti;
- ločeno gibalno oceno z virom in datumom;
- simptome in omejitve samo ob ustrezni privolitvi;
- izvor podatkov in čas zadnje potrjene posodobitve.

Obstoječa `athlete_state` različica 1 ostane začetna pogodba. Nadgradnja sheme zahteva eksplicitno migracijo in preverjanje; neznana polja ali manjkajoči podatki se ne smejo dopolnjevati z ugibanjem.

### 3.2 Program in izvedba
Ločiti je treba:
- **programsko različico:** kaj je ATENA predpisala, s katerim ciljem, omejitvami in različico generatorja;
- **izvedeni trening:** kaj je uporabnik dejansko opravil;
- **rezultate serij:** ponovitve, obremenitev, RIR/RPE, trajanje ali razdalja, tempo, kakovost izvedbe;
- **odziv:** zahtevnost, regeneracija, simptomi/nelagodje, dokončanje in odziv naslednji dan;
- **odločitev:** kaj se spremeni, kaj ostane enako, zakaj in na podlagi katerih dokazov.

Predpisanih vrednosti nikoli ne prepisujemo z dejansko izvedbo. Manjkajoči podatki ostanejo neznani.

### 3.3 Dnevnik dogodkov in odločitev
Vsak pomemben dogodek mora biti časovno označen in povezljiv z uporabnikom ter programom:
- profil ustvarjen ali posodobljen;
- ocena gibanja potrjena;
- privolitev podana ali preklicana;
- program ustvarjen ali zamenjan;
- trening začet, dokončan ali prekinjen;
- rezultat serije in povratna informacija zabeležena;
- odločitev o napredovanju, ohranitvi, regresiji, ponovni oceni ali napotitvi.

Zapis odločitve mora vsebovati vsaj: vrsto odločitve, rezultat, razlogne kode, uporabljene dokaze, manjkajoče podatke, uporabljeno različico pravil in pogoje za ponovno presojo. Dnevnik je dodajalen; popravek se zabeleži kot nov dogodek, ne kot tiho prepisovanje pretekle odločitve.

### 3.4 Enotni orkestrator odločanja
Specialistični moduli ne smejo samostojno spreminjati programa. Končni orkestrator uporabi naslednjo prednostno hierarhijo:

1. varnostni opozorilni znaki in potreba po ustrezni zdravstveni oceni;
2. novi, slabšajoči se ali nejasni simptomi ter potrjene omejitve;
3. veljaven cilj in dejanska oprema/čas;
4. gibalna pripravljenost in ustreznost vaje;
5. izvedba in primerljiva zmogljivost;
6. regeneracija in odziv po treningu;
7. napredovanje, ohranjanje ali regresija.

Višja prioriteta vedno preglasi nižjo. Neznan podatek ne pomeni pozitivnega signala. Orkestrator mora vrniti eno razložljivo odločitev, ne več nasprotujočih si priporočil.

## 4. Podatkovna shramba: migracijski pristop

Trenutna shramba uporablja `atena_profiles` in `atena_training_sessions`. Ta faza ne spreminja obstoječih tabel v živi bazi.

Pred prvo migracijo je treba:
1. potrditi dejansko vrsto baze in aktivno aplikacijsko vlogo;
2. preveriti, ali je v uporabi PostgreSQL JSON ali TEXT serializacija, saj mora biti tip stolpca skladen z adapterjem;
3. ugotoviti, ali je aplikacijska vloga lastnik tabel oziroma ali lahko obide RLS; preveriti privilegije anon/authenticated in dejansko politiko dostopa;
4. izdelati migracijo, ki je ponovljiva, zabeležena v tabeli različic in ima dokumentiran postopek povrnitve;
5. preveriti backup in dejansko obnovitev v izolirano okolje;
6. preveriti izbris profila, preklic privolitve, izvoz in roke hrambe;
7. migracijo najprej izvesti na testni kopiji z anonimiziranimi/sintetičnimi podatki.

**Pomembno:** nastavitev RLS sama po sebi ni dokaz izolacije. Lastnik tabele in vloga z `BYPASSRLS` lahko pravila obideta; preveriti je treba dejansko vlogo, privilegije in politike. Produkcijski dostop se ne testira z branjem ali izpisom osebnih podatkov.

### Predlagana logična področja podatkov
- `profiles`: identiteta profila, varnostni metapodatki, privolitve;
- `athlete_state_versions`: potrjene različice kanoničnega stanja;
- `program_versions`: nespremenljiv posnetek predpisanega programa;
- `training_sessions`: dejanski trening in status izvedbe;
- `set_results`: strukturirani rezultati posameznih serij oziroma intervalov;
- `feedback_events`: zahtevnost, regeneracija, simptomi in odziv;
- `decision_events`: končna odločitev, dokazi, razlogi in različica pravil;
- `schema_migrations`: uporabljene migracije.

To je logična meja, ne zahteva, da se vsako polje takoj normalizira v svojo tabelo. JSON je primeren za razširljive vsebine; ključni identifikatorji, relacije, časovni žigi, statusi in podatki za poizvedovanje morajo biti strukturirani.

## 5. Varnost, zasebnost in zanesljivost

- Zdravstveni in gibalni podatki se obdelujejo samo z jasno, ločeno privolitvijo.
- Preklic privolitve mora izbrisati vse kopije zdravstvenih/gibalnih podatkov, vključno z dogodki in varnostnimi kopijami v skladu z dokumentiranim postopkom; zakonsko zahtevane izjeme morajo biti izrecno navedene.
- Tokeni morajo biti kriptografsko naključni, dovolj dolgi in nikoli zapisani v loge.
- Vsi zapisi morajo biti vezani na preverjeno identiteto profila; ne zanašamo se na CORS kot avtentikacijo.
- RLS, privilegiji baze in strežniška avtentikacija so ločeni obrambni sloji.
- Napake ne smejo razkriti povezovalnih nizov, tokenov, osebnih ali zdravstvenih podatkov.
- Backup brez uspešnega testa obnovitve ni preverjen backup.

## 6. Faze izvedbe in merila zaključka

### Faza 19 — arhitekturna osnova
- potrditi produktno mejo Coach vs Decision Engine;
- določiti kanonični življenjski cikel podatkov;
- določiti enotno hierarhijo odločanja;
- opredeliti migracijske in varnostne pogoje.
**Izhod:** odobrena specifikacija pred posegom v bazo.

### Faza 20 — podatkovna pogodba in migracije
- dodati različice sheme in migracijski runner;
- dodati dogodkovno pogodbo in preverjanje vhodov;
- ustvariti samo aditivne migracije;
- pokriti združljivost obstoječih zapisov.
**Izhod:** CI preveri svežo bazo, nadgradnjo stare sheme, ponovitev migracije in zavrnitev neveljavnih dogodkov.

### Faza 21 — enotni odločitveni orkestrator
- obstoječe module povezati kot ponudnike dokazov;
- centralno uveljaviti prioritete in pravila ob neznanih podatkih;
- vrniti eno odločitev z razlogi, dokazi in naslednjim korakom.
**Izhod:** testi konfliktnih signalov in scenarijev, v katerih varnost preglasi progresijo.

### Faza 22 — dejanski trening in longitudinalna zgodovina
- zapis predpisanega proti izvedenemu;
- strukturirane serije/intervali in povratne informacije;
- povezava z različico programa in odločitvijo;
- varno brisanje/izvoz/preklic privolitve.
**Izhod:** end-to-end simulacija 8–12 tednov.

### Faza 23 — uporabniški tok in pilot
- povezati frontend z oceno gibanja in simptomov;
- uporabniku omogočiti pregled in popravek svojih podatkov;
- validirati slovenski jezik, razumljivost, čas vadbe in kakovost programov;
- pilot z majhno skupino in človeškim pregledom.
**Izhod:** merljivi dokazi uporabnosti, varnosti in ponovne uporabe.

## 7. Merila za plačljivi produkt

ATENA Coach ni pripravljen za plačljivo lansiranje, dokler niso izpolnjeni vsi naslednji pogoji:

- brez kritičnih varnostnih napak v vnaprej določenem naboru scenarijev;
- strokovni pregled programov za različne cilje, izkušnje, opremo in omejitve;
- potrjena pravilnost prilagajanja skozi večtedensko zgodovino;
- popoln uporabniški tok od prijave do izvedenega in prilagojenega treninga;
- preverjeni dostop, privolitve, izvoz, izbris, backup in obnovitev;
- stabilno delovanje, spremljanje napak in omejevanje stroškov modela;
- jasna cena, plačilni tok, pogoji uporabe in podpora;
- pilotni uporabniki, ki izkažejo dejansko uporabo in pripravljenost plačati.

Tehnični CI, delujoč API ali izdelan program sami po sebi ne štejejo kot dokaz tržne pripravljenosti.

## 8. Pravila izvajanja

- Najprej aditivne, testirane spremembe; brez neposrednega posega v produkcijske podatke.
- Brez novih plačljivih storitev ali infrastrukture brez izrecne odobritve.
- Brez združevanja PR-jev ali produkcijskega deploya brez izrecne odobritve.
- Vsaka faza mora imeti dokazljive teste, dokumentirane omejitve in jasen rollback.
- Če ni mogoče preveriti varnosti ali združljivosti, se sprememba ustavi in poroča o konkretni oviri.
