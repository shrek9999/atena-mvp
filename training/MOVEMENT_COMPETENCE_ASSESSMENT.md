# ATENA: začetna ocena gibalne kompetentnosti

## Namen in umestitev

Začetna ocena je kratek, nalogam specifičen način zbiranja informacij o uporabnikovi izkušnji pri osnovnih gibalnih nalogah. Namenjena je boljšemu izboru začetne različice vaje in prepoznavanju področij, o katerih mora ATENA vprašati več. Ni klinični pregled, diagnostični test, ocena poškodbe ali splošno dovoljenje za zahtevnejšo vadbo.

Ocena dopolnjuje obstoječi vprašalnik; ne spreminja ga in ne spreminja videza aplikacije. V tej razvojni fazi je na voljo kot ločen, pilotno zaščiten in brezstanj­ski API. Podatki se ne shranjujejo.

## Načela

1. **Naloga pred domnevno diagnozo.** Ocenjujemo uporabnikovo izkušnjo pri konkretni nalogi, ne sklepamo o poškodovanem tkivu ali vzroku.
2. **Ločimo obseg, nadzor in toleranco.** Ne enačimo omejene amplitude, nepoznavanja naloge, pomanjkanja samozavesti in bolečine.
3. **Ni univerzalne idealne tehnike.** Gibanje presojamo v kontekstu cilja, naloge, trenutne zmogljivosti in odziva.
4. **Brez avtomatskega kaznovanja.** Odgovor »potrebujem oporo« je razlog za dodatno vprašanje ali ustrezno podprto različico, ne za avtomatsko dodajanje stabilizacijskih vaj.
5. **Neocenjeno ni neuspešno.** Manjkajoči odgovor ostane »ni ocenjeno«; sistem ne sklepa.
6. **Bolečina ni diagnoza.** Simptom se obravnava ločeno od gibalne kompetentnosti. Pri novih, izrazitih, napredujočih ali nenavadnih simptomih se avtomatsko prilagajanje ustavi in uporabnika usmeri k ustreznemu zdravstvenemu strokovnjaku.
7. **Napredna naloga zahteva ločeno presojo.** Samoporočilo o počepu ali ravnotežju ne potrjuje pripravljenosti za skoke, doskoke ali hitre spremembe smeri.

## Nabor osnovnih nalog

| Naloga | Namen opazovanja | Kaj ne smemo sklepati |
|---|---|---|
| Počep | Izkušnja z osnovnim vzorcem počepa in nadzorom v razpoložljivi amplitudi | Da je vsako odstopanje napaka ali omejitev kolena/kolka |
| Predklon z ravnim hrbtom | Izkušnja z vzorcem predklona in obremenitvijo zadnje verige | Da položaj sam določa gibljivost ali poškodbo hrbta |
| Izpadni korak | Nadzor enostranske naloge, ravnotežje in toleranca | Da je asimetrija sama po sebi patologija |
| Potisk | Izkušnja s potisnim vzorcem in oporo | Da položaj lopatice v eni ponovitvi dokazuje motnjo |
| Poteg | Izkušnja s potegom in razpoložljivo opremo | Da odsotnost opreme pomeni primanjkljaj uporabnika |
| Dvig roke nad glavo | Aktivni obseg in nadzor v konkretni nalogi | Da vidni položaj določa vzrok omejitve |
| Ravnotežje na eni nogi | Izkušnja z enonožno oporo | Da ravnotežje potrjuje pripravljenost za doskok |
| Hoja/lahka lokomocija | Osnovna toleranca ritmičnega gibanja | Da je uporabnik pripravljen na tek ali intenzivne intervale |

Naloge naj bodo prikazane z varno, preprosto različico in možnostjo, da jih uporabnik preskoči. Uporabnik jih ne izvaja skozi bolečino ali prisilo. Videoanaliza ni predpogoj za to različico.

## Standardizirani odgovori

- `comfortable`: uporabnik poroča, da nalogo pozna in jo izvede udobno ter nadzorovano.
- `needs_support`: uporabnik poroča, da potrebuje oporo, lažjo različico ali dodatno prilagoditev.
- `uncertain`: naloge ne pozna ali ne zna zanesljivo oceniti svoje izvedbe.
- `symptoms_reported`: pri nalogi poroča o bolečini ali drugem simptomu; to ni diagnostična oznaka.
- `not_assessed`: naloge ni izvedel ali je ne želi oceniti.

## Pravila odločanja

- `comfortable`: zabeleži kot uporabnikovo poročilo; samo po sebi ne sproži napredovanja.
- `needs_support`: ATENA lahko vpraša, kakšna opora ali sprememba je pomagala, in razmisli o podprti oziroma manj zahtevni različici.
- `uncertain`: pred izbiro zahtevnejše različice zbere dodatne informacije.
- `symptoms_reported`: avtomatsko spreminjanje obremenitve ali zahtevnosti za to nalogo se ustavi; uporabi se ločen protokol za simptome in meje napotitve.
- `not_assessed`: brez sklepanja in brez avtomatske spremembe programa.

Ocena ne izračuna skupnega rezultata in ne razvršča uporabnika v »slabega« ali »dobrega« gibalca. V tej fazi ne spreminja programa samodejno.

## Varnost in omejitve

- Brez diagnostičnih trditev ali sklepanja o poškodovanem tkivu.
- Brez sklepanja o pripravljenosti za skoke ali hitro zaviranje iz splošne izkušenosti.
- Brez obveznega testiranja maksimalne amplitude, moči, hitrosti ali bolečinskega praga.
- Brez avtomatskega dodajanja stabilizacijskih vaj samo na podlagi samoporočila.
- Ocena se uporablja kot dopolnilo pogovoru in povratnim informacijam, ne kot nadomestilo za strokovno presojo.

## Tehnična izvedba v fazi 10

- Pilotno zaščiten endpoint `POST /coach/movement-assessment`.
- Brez shranjevanja podatkov in brez sprememb podatkovne baze.
- Obvezna validacija dovoljenih nalog in statusov.
- Vrnjen rezultat izrecno označi, da ne gre za diagnozo ali točkovanje.
- Obstoječi vprašalnik in uporabniški vmesnik ostaneta nespremenjena.
