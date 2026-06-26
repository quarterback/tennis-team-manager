# The Committee Is Just Four Numbers
### Modeling a selection committee without modeling a room full of people

The single most controversial object in American sports is a conference room. Every March, a dozen athletic directors disappear into one and emerge with a bracket, and the rest of us spend a week litigating who got snubbed, who got a kind draw, and what "eye test" is supposed to mean when the eye in question is attached to someone whose school is in the field.

When I needed my sim to build a national field, I had two options. I could fake the room — some hand-wavy reputation fudge — or I could decide what the room is *actually for* and write that down. I went with writing it down, and the act of writing it down forced me to be honest about three things that the real committee constantly smears together.

Selection, seeding, and bracketing are different questions. They are *completely* different questions, and the whole credibility of a field depends on never using the answer to one to settle another:

- **Selection** asks *why is this team in?* You won your league (automatic bid), or you're one of the best leftovers (at-large).
- **Seeding** asks *how good is this team?* Strength, full stop.
- **Bracketing** asks *who should it play?* Match-making, and the only place a team's bid type is allowed to matter at all.

The real committee blurs these constantly — a team "earns a better seed" by winning a conference tournament, which is selection logic leaking into seeding. I wanted mine to keep them in separate rooms.

So selection and seeding both run off one number, the **Committee Seed Score**, and it is unromantically just a weighted blend:

- **45% Power Index** — base strength, "how good are you"
- **30% ITA-style résumé points** — results weighted by schedule and league, "what have you done"
- **15% championship bonus** — for automatic qualifiers only, tiered by how strong your conference is, "did you win something that mattered"
- **10% recent form** — your last five, "are you hot right now"

Each input gets turned into a 0–100 rank score before blending, so a strength metric and a résumé metric can sit at the same table without one of them quietly dominating because it happens to live on a bigger scale.

The interesting fights are all in that 15%. A championship bonus is where pedigree gets to touch the seed — but I capped it at 15% on purpose, and I *tiered* it, because a conference title is not a conference title. Winning the toughest league in the country should outweigh winning the weakest by a lot, so the bonus scales with conference strength. A power-conference champ gets the full kick and will seed above a comparable at-large; a champion from a thin league gets a token bump and slides toward the bottom of the field. Both of those are correct. Winning your league gets you *in* — that's selection, and it's sacred, an automatic bid can't be argued away. But it doesn't pretend you're better than you are.

The thing this buys you is the most counterintuitive-looking row on the page, and it's my favorite: an at-large team left *out* of the field can be carrying a higher score than a champion seeded *inside* it. That reads like a bug. It's the system working. The champ was selected — it won its league, then got seeded honestly near the bottom. The at-large team was strong but the at-large seats filled up before it got one. Different questions, different answers, never crossed. I put a little AQ/AL chip on every row specifically so that moment is visible instead of mysterious.

Bracketing is the only stage where I let bid type back in, and only for match-making: avoid same-conference first-rounders, avoid rematches (with the penalty climbing the more often two teams already played), keep two league champions apart early. All of it happens *within* a team's seed line — teams only ever swap with peers on their own line, so the draw improves without anybody's earned seed moving an inch.

None of this makes the result uncontroversial. You can still hate where your team landed. But you can read exactly *why* it landed there, which is more than the conference room has ever offered. Turns out the committee didn't need to be a room. It needed to be four numbers and a rule about not crossing the streams.
