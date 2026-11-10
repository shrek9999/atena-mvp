# ATENA – faza 3: prilagajanje glede na odziv

## API

POST /coach/program sprejme bodisi neposreden profil (združljivost s fazo 2) bodisi:

    {
      "profile": {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "equipment": ["bodyweight", "dumbbell", "resistance_band"],
        "sessions_per_week": 2,
        "session_minutes": 60
      },
      "feedback": {
        "difficulty": "hard",
        "completed": true,
        "discomfort": "no"
      }
    }

Endpoint ostaja zaščiten z X-Pilot-Token in strežniško spremenljivko AI_COACH_TEST_TOKEN. Skrivnost se ne pošilja v uporabniški brskalnik.

## Pravila prilagoditve

- Brez povratne informacije: običajni program iz preverjenega kataloga.
- Ustrezno zahtevno: program ostane nespremenjen.
- Prelahko in dokončano: po enem samem odzivu se obremenitev ne poveča samodejno; uporabi se pravilo progresije iz metodologije.
- Pretežko ali nedokončano: serije se konservativno zmanjšajo za eno (najmanj dve), RIR se poveča za eno (največ štiri), odmori pa se podaljšajo za 30 sekund.
- Prijavljeno nelagodje/bolečina: HTTP 409 in varnostna ustavitev. Generator ne poskuša ugibati vzroka ali samodejno predpisati druge vaje.

Povratna informacija se uporabi samo pri trenutnem zahtevku; backend je ne shranjuje. Za longitudinalno prilagajanje so potrebni več zaporednih zapisov, preverjanje trenda in kasnejša razširitev profila. Ta faza ne trdi, da že izvaja dolgoročno periodizacijo.

## Testi

Endpoint testi preverijo gnezden profil, konservativno zmanjšanje po težkem/nedokončanem treningu, ohranitev progresijskega pravila po lahkem treningu in varnostno ustavitev ob nelagodju.
