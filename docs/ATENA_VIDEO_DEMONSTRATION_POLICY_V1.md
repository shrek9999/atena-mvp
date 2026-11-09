# ATENA — politika in register video demonstracij

**Status:** specifikacija za vključitev video demonstracij v zaprti pilot.

## 1. Namen

Video je kratka vizualna demonstracija določene vaje ali učne metode. Uporabniku pomaga razumeti začetni položaj, potek giba in izbrano različico. Video ni individualna ocena tehnike, diagnoza ali nadomestilo za povratno informacijo trenerja.

ATENA mora prikazati video, ki ustreza trenutno izbrani učni metodi ali vadbeni različici, ne zgolj splošnega videa za isti mišični sklop.

## 2. Prednostni viri

1. Uradni javni videoposnetki FZS, kadar so vsebinsko ustrezni in je v YouTubu omogočeno vdelovanje.
2. Videoposnetki, ki jih FZS oziroma nosilec pravic izrecno odobri za uporabo v ATENI.
3. Lastne demonstracije ATENE, posnete in odobrene za ta namen.
4. Drugi strokovni javni viri šele, ko primernega FZS ali lastnega posnetka ni.

Uradni YouTube kanal, ki je povezan s spletne strani FZS:
https://www.youtube.com/@fitneszvezaslovenijefzs2912

## 3. Način vključitve

- Uporabi YouTube uradni embed za konkretni video ID.
- Ne prenašaj, ne izreži in ne nalagaj tujih videov na Atenin strežnik brez izrecnega dovoljenja nosilca pravic.
- Pred vdelavo preveri, da je video javen, da vdelava ni onemogočena in da vsebina dejansko prikazuje navedeno vajo.
- Kjer je mogoče, uporabi zasebnostno izboljšano domeno youtube-nocookie.com.
- Predvajalnik naloži šele po uporabnikovi izbiri oziroma kliku; začetni zaslon naj prikaže naslov, vir in gumb za predvajanje.
- Ohraniti je treba YouTubovo atribucijo in povezavo do izvirnika.
- Če video ni več dosegljiv ali je vdelava onemogočena, prikaži varno povezavo do izvirnika ali lastno demonstracijo. Ne prikazuj praznega predvajalnika.

## 4. Video ni enak gibalnemu vzorcu

En vzorec ima lahko več videov:
- osnovna učna metoda;
- lažja oziroma podprta različica;
- običajna vadbena različica;
- različica z drugo opremo;
- naprednejša različica.

Primer za počep:
- reaching squat s protiutežjo kot učna metoda;
- goblet squat;
- back squat;
- front squat.

ATENA ne sme samodejno prikazati videa back squata uporabniku, ki se šele uči osnovnega počepa. Izbira videa sledi izbrani vaji oziroma učni metodi.

## 5. Metapodatki registra

Vsak video zapis naj vsebuje:
- `video_id` oziroma preverjen YouTube ID;
- `provider` in `channel_name`;
- `source_url` in `embed_url`;
- `title`;
- `movement_pattern`;
- `exercise_id` ali `learning_method_id`;
- `equipment_variant`;
- `language`;
- `duration_seconds`, če je preverjena;
- `rights_status` (npr. public_youtube_embed, permission_confirmed, own_content);
- `embed_allowed`;
- `review_status` (pending, approved, rejected);
- `reviewed_at` in `reviewed_by`;
- `notes` o vsebinski ustreznosti in omejitvah.

Video brez potrjenega naslova, dejanskega prikaza vaje in preverjenega dovoljenja za vdelavo ne sme biti objavljen kot priporočena demonstracija.

## 6. Uredniška merila

Pred odobritvijo preveri:
- ali je prikazana prava vaja in prava različica;
- ali so jasno vidni začetni položaj, izvedba in zaključek;
- ali demonstracija ustreza uporabniku prikazanim navodilom;
- ali video ne vsebuje zavajajočih univerzalnih trditev o eni sami pravilni tehniki za vse;
- ali je mogoče videti pomembne dele telesa in pripomoček;
- ali je posnetek dovolj kratek in razumljiv za uporabo v aplikaciji.

Za RDL s palico mora biti vsebina skladna z Atenino metodo treh stičnih točk in četrte kontrolne točke roke v ledveni krivini. Za počep mora biti jasno, ali gre za običajen kontroliran počep, reaching squat, goblet, back ali front squat.

## 7. Prva zbirka

Za začetno zbirko ciljamo na šest osnovnih vzorcev:
1. počep;
2. predklon z nevtralno hrbtenico;
3. skleca;
4. veslanje v predklonu;
5. potisk nad glavo;
6. izpadni korak.

Ne zahtevamo šestih videov na silo. Če za določen vzorec ni primernega in preverjenega FZS posnetka, ga označimo kot manjkajočega in uporabimo lastno demonstracijo ali pozneje odobren zunanji vir.

## 8. Trenutno stanje raziskave

Uradni FZS kanal je bil najden, vendar iz javno indeksiranih rezultatov v tej raziskavi še ni bilo mogoče potrditi posameznih URL-jev videov za vseh šest vzorcev. Kanal:
https://www.youtube.com/@fitneszvezaslovenijefzs2912

Zato posameznih video ID-jev ne izmišljamo in še ne dodajamo v produkcijski register. Ko so konkretni URL-ji preverjeni, jih vnesemo v register ter vsebinsko odobrimo.
