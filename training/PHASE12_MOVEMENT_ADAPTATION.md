# ATENA – faza 12: prilagajanje izbire vaj na podlagi gibalne samoocene

## Namen

Faza 12 poveže neobvezno gibalno samooceno iz faze 11 z determinističnim generatorjem programa. Samoocena lahko vpliva na izbiro začetne različice vaje in njeno začetno odmerjanje. Ne predstavlja diagnoze, kliničnega presejanja ali dovoljenja za zahtevnejšo vadbo.

## Pravila odločanja

| Samoocena | Odločitev generatorja |
|---|---|
| `comfortable` | Izbira vaj ostane enaka kot brez samoocene. Samoocena sama ne sproži napredovanja. |
| `needs_support` | Generator poišče preverjeno, praviloma začetniško različico istega gibalnega vzorca. Upošteva cilj, dovoljeno opremo, izključene vaje in vzorce. Za izbrano lažjo različico uporabi največ 2 seriji in najmanj 3 ponovitve v rezervi. |
| `uncertain` | Generator ne ugiba in ne menja vaje. Izbiro ohrani, doda pojasnilo, da je treba ustreznost preveriti pred delovno serijo, ter zadrži samodejno napredovanje tega vzorca. |
| `symptoms_reported` | Povezani gibalni vzorec se izpusti iz programa. ATENA ga ne nadomesti samodejno z drugo vajo. Uporabnik vidi razlog in potrebo po dodatni presoji. |
| `not_assessed` | Brez sklepanja in brez spremembe izbire. |

Če katalog ali uporabnikova oprema ne omogočata preverjene lažje različice, generator vzorca ne ugiba: izpusti ga in to jasno sporoči.

## Dovoljene začetne različice

Izbira ni prosto generirana. Generator uporablja le obstoječe zapise v katalogu in pred izborom preveri gibalni vzorec, namen vaje, opremo, zahtevnost in uporabnikove izključitve.

- Počep: podprta oziroma manj obremenjena različica, npr. `reaching_squat` ali `air_squat`.
- Predklon z ravnim hrbtom: `bodyweight_hip_hinge`.
- Izpadni korak: `split_squat` oziroma `reverse_lunge`.
- Horizontalni potisk: `push_up_incline`, `wall_push_up` ali `push_up`.
- Vertikalni potisk: `band_overhead_press` oziroma `overhead_press`, če ustreza razpoložljivi opremi.
- Horizontalni poteg: `band_row`, `trx_row` ali `one_arm_row`, če je oprema potrjena.
- Vertikalni poteg: asistirana različica zgiba ali vleka elastike, če so sidrišče in oprema potrjeni.
- Lokomocija: `brisk_walking`.
- Ravnotežje na eni nogi: obstoječa naloga ostane, vendar se doda jasen namig za uporabo dosegljive stabilne opore; sistem ne trdi, da je našel drugo vajo.

To so prednostne možnosti, ne obvezna zamenjava. Če pogoji niso izpolnjeni, se vaja ne izbere.

## Varnostne meje

- Bolečina ali nelagodje se ne pretvarjata v diagnozo in se ne širita na druge vzorce brez podatkov.
- Pri poročanih simptomih se izpusti samo neposredno povezani vzorec; pri novih, izrazitih, napredujočih ali nenavadnih simptomih je potrebna ustrezna strokovna presoja.
- Samoocena počepa, ravnotežja ali hoje ne potrjuje pripravljenosti za skoke, doskoke ali hitre spremembe smeri.
- Za vzorca z oznako `needs_support` ali `uncertain` se ne uporablja samodejna progresija na podlagi lahke povratne informacije.
- Drugi, neodvisni vzorci se še vedno prilagajajo po obstoječih pravilih odziva na trening.
- V program se ne dodajajo stabilizacijske vaje zgolj zato, ker je uporabnik označil potrebo po opori.

## Zasebnost in tehnična izvedba

- Samoocena ostane neobvezna in zahteva ločeno izrecno soglasje.
- Podatek se uporabi samo pri pripravi trenutnega programa; ne shranjuje se v profil, zgodovino treningov ali izvoz.
- Podatek se ne pošilja ponudniku AI-modela.
- Rezultat je del odgovora generatorja in je označen kot samoocena, ne diagnoza.
- Če samoocena ni poslana, obstoječa izbira programa ostane nespremenjena.

## Testiranje

Dodani so regresijski testi za:
- preverjeno lažjo različico in konservativno odmerjanje;
- zadržanje progresije pri potrebi po opori;
- ohranitev izbire pri negotovosti;
- izpust vzorca ob simptomih brez samodejne zamenjave;
- nespremenjeno izbiro pri udobni izvedbi;
- zavrnitev neveljavnih nalog in statusov.
