# Dora Dash! — Game Design Document

*A 3D third-person stage runner: Pepsi Man's frantic energy meets Dora the Explorer.*

## 1. Core Concept
Dora sprints forward automatically, ever faster. The player steers across three lanes, jumps gaps and slides under barriers. Every stage ends with a flying leap onto the **Banana Swing**, which triggers the victory animation.

**Tone:** fast, slapstick, cheerful. Over-the-top reactions, exaggerated crashes, and Dora breaking the fourth wall ("Can you say *JUMP*?").

## 2. Core Loop
1. Stage intro (Map sings the route) → 2. Run (dodge, collect) → 3. Hit hazard (comedic wipeout, checkpoint respawn) or reach the end → 4. Banana Swing leap → 5. Victory animation + score/star rating → 6. Unlock next stage / cosmetics.

A stage lasts 2–3 minutes. Speed ramps from 12 to 32 m/s.

## 3. Controls
| Action | Keyboard | Gamepad |
|---|---|---|
| Lane left/right | A/D or ←/→ | Left stick / D-pad |
| Jump | W / ↑ / Space | A |
| Slide (mid-air = fast-fall slam) | S / ↓ | B |
| Pause | Esc | Start |

Fairness aids: input buffering (0.15 s), coyote time (0.1 s), lane-snap smoothing.

## 4. Hazards
| Hazard | Behaviour | Counter |
|---|---|---|
| **Swiper the Fox** | Leaps out from the side, throws junk (crates, banana peels, buckets) into a lane | Switch lane; telegraphed by "Oh man!" voice line and a lane flash |
| **Grumpy Old Troll** | Drops bridge planks; gaps appear/close in rhythm | Jump gaps; time the plank drops |
| **Low barriers** (logs, signs, vines) | Block the upper body | Slide |
| **Gaps / pits** | Missing ground | Jump |
| **Rolling Boulders** | Roll down a lane, sometimes bouncing | Dodge lanes or jump |
| **Moving traffic** | Cars/buses crossing lanes | Lane timing, jump onto low vehicles |
| **Snappy Crocs** | Surface and snap at lane edges | Stay out of edge lanes or jump |
| **Fake Boots** | Boots-the-monkey decoy items that look like pickups but are hazards | Read the shape |

Failure is comedic: Dora flattens, spins, or is launched sideways, then respawns at the last checkpoint with a short invulnerability window.

## 5. Collectibles & Scoring
- **Map Pieces** (3 per stage, hidden in risky lines): unlock bonus content.
- **Stars** (chains of 5–10): points and combo multiplier.
- **Backpack Boost:** short speed burst + invulnerability (Backpack's "shield" mode).
- **Banana Magnet:** pulls nearby stars.
- **Checkpoint flags:** respawn points.
- **Final rating:** 1–3 map stars from time, stars collected, and deaths.

## 6. Finale: the Banana Swing
The last 100 m is a boost ramp. Speed locks in, a cinematic camera swings to Dora's side, and the player taps **Jump** at the glowing marker. Perfect timing = perfect-grab bonus. Dora leaps, grabs the giant Banana Swing, swings with confetti, and the victory song plays. Missing the leap still lands her softly, with a lower rating.

## 7. Levels
### Level 1 — The Spooky Forest (Tutorial / easy)
Dusk forest, glowing mushrooms, fog. Teaches the basics.
- Hazards: fallen logs (slide), low pits (jump), rare Swiper trash throws, rolling boulders late.
- Mid-level beat: a short Troll bridge with planks dropping slowly.
- Speed: 12 → 20 m/s.

### Level 2 — The Chaotic Highway (Medium)
A cartoon highway through the jungle. Traffic and signage.
- Hazards: cars and buses crossing lanes, traffic cones, construction barriers (slide), road gaps from collapsed sections, Swiper on overpasses dropping junk.
- Fake Boots pickups on the road.
- Mid-level beat: a truck convoy with only one safe lane at a time.
- Speed: 18 → 27 m/s.

### Level 3 — Crocodile Lake (Hard)
Floating platforms, lily pads, swinging vines over a lake.
- Hazards: Snappy Crocs surfacing in rhythm, Troll-controlled plank bridges that collapse behind you, moving platforms, Swiper on a rowboat flinging junk, boulders bounced down shorelines.
- Gaps are frequent; jump-chains need precision.
- Boss beat: Swiper's Giant Junk Machine chases Dora through the finale.
- Speed: 25 → 32 m/s.

## 8. Engine Recommendation: **Unity (URP)**
- Mature 3D runner tooling and a huge asset ecosystem (CharacterController, Cinemachine, Timeline for the swing cutscene).
- Fast iteration, easy to prototype and polish juice (camera shake, FOV punch, particles).
- C# is approachable; strong PC build pipeline and gamepad support (Input System).
- Alternatives: *Godot 4* is lighter, free and great for small teams (GDScript); *Unreal* is overkill for a stylised runner.

**Suggested stack:** Unity 2022 LTS or newer, URP, Cinemachine, Input System, Addressables for stage chunks.

## 9. Technical Notes
- **Level building:** modular 30 m chunks pooled and spawned ahead; hand-authored per level with weighted random variety for replays.
- **Camera:** Cinemachine behind-the-back, FOV widens with speed, slight shake on landing.
- **Juice:** speed lines, squash and stretch on jump/slide, slow-mo on near misses.
- **Audio:** upbeat music with tempo scaling by speed; Dora voice barks.
- **Accessibility:** speed cap option, colorblind-safe lane markers, rebindable keys.

## 10. Roadmap
1. **Prototype (2 wks):** controller, 3 lanes, one chunk set (starter script in `Assets/Scripts/DoraRunnerController.cs`).
2. **Vertical slice (4 wks):** Level 1, Swiper/Troll, Banana Swing finale.
3. **Content (8 wks):** Levels 2–3, collectibles, UI, audio.
4. **Polish (4 wks):** juice, balancing, playtests, builds.

> **Note:** Dora the Explorer is a trademark of Viacom/Nickelodeon. Treat this as a fan prototype; a commercial release needs licensing or original characters.
