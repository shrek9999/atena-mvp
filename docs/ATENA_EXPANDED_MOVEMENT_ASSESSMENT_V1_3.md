# ATENA – razširjena začetna ocena gibanja (v1.3)

## Namen

Ocena je strukturiran, samoporočan pogovor o izkušnji pri osnovnih gibalnih nalogah. Ne gre za klinični pregled, diagnozo, oceno poškodbe ali dovoljenje za zahtevnejšo vadbo. Sistem ne izračuna skupnega rezultata in ne razvršča uporabnika.

## Razširjene naloge

| Področje | Naloga | Povezava s programiranjem |
|---|---|---|
| Osnovni vzorci | Vstajanje s stola / počep | Vzorec počepa |
| Osnovni vzorci | Pobiranje lahkega predmeta s tal | Predklon z ravnim hrbtom |
| Osnovni vzorci | Izpadni korak | Enostranski vzorec; brez izmišljene regresije, če je katalog ne vsebuje |
| Zgornji del | Potisk in poteg | Ustrezni vzorci potiska/potega |
| Gibljivost | Pomik kolena naprej nad stopalo ob peti na tleh | Počep in izpadni korak; ne pomeni diagnoze gležnja |
| Gibljivost | Nadzorovan gib kolka v počepu in predklonu | Počep, predklon z ravnim hrbtom in izpadni korak |
| Gibljivost | Dvig rok nad glavo brez siljenja | Vertikalni potisk |
| Ravnotežje | Ravnotežje na eni nogi | Ravnotežje; ne potrjuje pripravljenosti za doskok |
| Koordinacija | Izmenično dotikanje nasprotne dlani in kolena | Koordinacija; negotovost zahteva dodatno pojasnilo |
| Zavedanje telesa | Zaznavanje položaja telesa in nadzor tempa | Samostojen pogovorni namig, ne avtomatska stabilizacijska vaja |
| Lokomocija | Hoja po ravni podlagi | Osnovna toleranca hoje; ne pomeni pripravljenosti za tek ali intervale |

## Odgovori

Vsaka naloga sprejme enega od petih statusov:

- comfortable: uporabnik poroča, da nalogo izvede udobno in nadzorovano;
- needs_support: potrebuje oporo, lažjo različico ali dodatno prilagoditev;
- uncertain: naloge ne pozna ali izvedbe ne zna oceniti;
- symptoms_reported: poroča o bolečini ali drugem simptomu;
- not_assessed: naloge ni izvedel ali je ne želi oceniti.

Manjkajoči podatki ostanejo not_assessed. Ne sklepamo, da je uporabnik nalogo opravil ali da jo izvaja nepravilno.

## Pravila povezave z vadbenim programom

1. Poročilo o potrebi po opori lahko sproži izbiro preverjene lažje različice, vendar samo, če obstaja v katalogu in ustreza opremi, cilju ter izključitvam.
2. Če ustrezne preverjene različice ni, sistem vzorec izpusti in pojasni omejitev. Ne preimenuje običajne vaje v regresijo.
3. Poročani simptomi ustavijo samodejno prilagajanje samo povezanega vzorca. Sistem ne ugiba o vzroku ali diagnozi.
4. Negotovost sproži dodatno vprašanje; sama po sebi ni dokaz pomanjkljivosti.
5. Ocena gležnja je povezana s počepom in izpadnim korakom; ocena kolka s počepom, predklonom in izpadnim korakom; ocena ramenskega giba z vertikalnim potiskom.
6. Zavedanje telesa ostane pogovorni namig. Ne sproži samodejnega dodajanja vaj za stabilizacijo trupa.
7. Koordinacija je samostojno področje. Ne sklepamo o njej na podlagi starosti, trening staža ali cilja.
8. Udobna izvedba počepa, ravnotežja ali hoje ne potrjuje pripravljenosti za skoke, doskoke ali hitro zaviranje.

## Omejitev te izdaje

V1.3 razširi podatkovni model in varno povezavo z gibalnimi vzorci. Še vedno gre za samoporočanje, ne za objektivno meritev gibljivosti ali videoanalizo. Uporabniški vmesnik za vodeno izvedbo testov, prikaz navodil in ponovno testiranje je ločena naslednja naloga. Do takrat se novih nalog ne sme predstavljati kot že izvedenih fizičnih meritev.
