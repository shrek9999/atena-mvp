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
