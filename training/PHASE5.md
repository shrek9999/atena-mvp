# ATENA Phase 5 – Coaching Intelligence

## Namen
Generator ne izbira več le vaj po osnovnem gibalnem vzorcu. Upošteva tudi tip vaje, enostransko izvedbo, primarno funkcijo, opremo in razpoložljiv čas.

## Spremembe
- Most za zadnjico je razvrščen kot **izteg kolkov**, ločeno od predklona z ravnim hrbtom.
- Enostranske vaje in Pallof potisk nosijo izrecen podatek, da so ponovitve predpisane na vsako stran.
- Dead bug uporablja izmenično izvedbo; predpisano število ponovitev pomeni skupno število, ne števila na vsako stran.
- Ocena trajanja pri vajah, predpisanih na vsako stran, upošteva obe strani.
- Predpis serij, ponovitev, RIR in odmora se razlikuje med glavnimi večsklepnimi vajami, enostranskimi vajami in stabilizacijo trupa.
- Stabilizacija trupa in preprečevanje rotacije sta vključena v nabor vaj za hipertrofijo, kadar je ustrezna vaja in oprema na voljo.
- Dodana je vleka elastike od zgoraj, vendar zahteva elastiko in varno sidrišče.
- Alternative in lažje različice se prikažejo samo, če obstajajo v katalogu, so različne od izbrane vaje in ustrezajo razpoložljivi opremi.
- Program ostaja determinističen in uporablja izključno preverjen katalog; ni dodan zunanji LLM ali plačljiva storitev.

## Omejitve
- Ocena trajanja je še vedno približek; dejanski čas je odvisen od tempa, menjave opreme in organizacije vadbe.
- Količina neposrednega dela za posamezno mišico je le približna, ker večsklepne vaje obremenijo več mišičnih skupin.
- Če oprema ne omogoča vertikalnega potega ali drugega vzorca, ga generator izrecno označi kot nezagotovljenega; ne predpostavlja neobstoječe opreme.
- Povratne informacije se v tej fazi še ne shranjujejo trajno na strežniku.

## Testiranje
- Dodani so regresijski testi za klasifikacijo iztega kolkov, enostranske ponovitve in oceno trajanja, različno programiranje, opremo pri alternativah ter varno sidrišče za vleko elastike.


## Dopolnitve po praktičnem testu – Phase 5.1
- Tudi potisk bokov (hip thrust) je razvrščen pod izteg kolkov, ne pod predklon z ravnim hrbtom.
- Vaje za stabilizacijo trupa in preprečevanje rotacije imajo ločeno kategorijo prikaza; niso označene kot običajne večsklepne vaje za hipertrofijo.
- Alternative morajo ohraniti isti gibalni vzorec; pri stabilizaciji trupa je dovoljena zamenjava med sorodnima vzorcema stabilizacije in preprečevanja rotacije.
- Ista vaja se ne prikazuje hkrati kot lažja različica in alternativa.
- Most za zadnjico nima več Romunskega mrtvega dviga kot alternative.
- Ocena časa uporablja 45-sekundni povprečni prehod med vajami in pri 45-minutnem profilu cilja na najmanj 3 minute rezerve. Regresijski test hkrati preverja, da ostanejo ključni gibalni vzorci in stabilizacija trupa vključeni.
- Različica generatorja: 2.3.0.

- Stabilizacijske vaje in vaje za preprečevanje rotacije ne uporabljajo klasičnega RIR; predpisano je merilo kakovosti izvedbe in nadzora.
- Pri konservativni prilagoditvi po zahtevnem treningu se RIR poveča samo pri vajah, kjer je RIR smiseln; stabilizacijske vaje ostanejo vezane na kakovost izvedbe.
- Različica generatorja: 2.3.1.


## Phase 5.2 – izkušenost, tempo in amplituda
- Izkušenost je samostojno programsko merilo. Začetnik tudi pri cilju moč začne večinoma z 8–12 ponovitvami, približno 2–3 ponovitvami v rezervi ter poudarkom na učenju osnovnih gibalnih vzorcev in ponovljivi tehniki. Nižji razponi in večje obremenitve se uvajajo postopno z napredovanjem.
- Intermediate in advanced ohranita bolj specifične razpone ponovitev glede na cilj; pri moči intermediate uporablja 5–8, advanced pa 3–6 pri glavnih vzorcih počepa in predklona z ravnim hrbtom.
- Vsaka vaja ima predpisan tempo in razlago. Glavne večsklepne vaje uporabljajo privzeti tempo 3–0–1–0; stabilizacijske in eksplozivne vaje imajo tempo, prilagojen funkciji.
- Vsaka vaja ima navodilo za amplitudo: čim večja neboleča amplituda, ki jo omogočata gibljivost in nadzor, brez izgube položaja.
- Pri horizontalnem potisku imata prednost skleca (z višino opore, prilagojeno sposobnostim) in potisk ročk na klopi. Potisk ročk na tleh ostane rezervna možnost zaradi omejene amplitude.
- Ocena trajanja upošteva predpisani tempo, ne več samo generične tri sekunde na ponovitev.
- Različica generatorja: 2.4.0.

- Pri časovno omejenih treningih se najprej odstranijo dopolnilne vaje za izteg kolkov/nošenje; če je potrebno, se serije glavnih večsklepnih vaj začasno zmanjšajo s treh na dve, preden se izpuščajo osnovni gibalni vzorci.
- Ocena trajanja uporablja srednjo vrednost razpona ponovitev in upošteva predpisani tempo. Uporabniku se prikaže, če je bil obseg serij prilagojen zaradi časovne omejitve.
- V katalog sta dodani začetniški različici predklona z lastno težo in mrtvega dviga z ročkama; pri začetniku imata prednost pred zahtevnejšo različico romunskega mrtvega dviga.
- Potisk nad glavo je na voljo tudi začetnikom z ustrezno lahkim bremenom in predpisanim nadzorom.
