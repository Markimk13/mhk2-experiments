---
name: mhk2-fps-physics-root-cause
description: Why the original Moorhuhn Kart 2 drives slower / slippery / hops at 200 FPS - suspension stiffness scales with the physics step (measured + proven 2026-11-18)
metadata:
  type: project
---

Root cause found on 2026-11-18 for the user's "60 FPS normal, 200 FPS slower + slippery like ice + random jumps" (original MHK2-XXL.exe V1.0, same on any Windows; it is frame rate, not Windows):

- Frame loop (fn 0x472D40) skips frames shorter than 5 ms (=> 200 FPS cap) and passes the real dt on. `RwPhysics::Update` (0x469060) does n = round(dt*60) substeps (min 1), so frames longer than 1/60 s are subdivided but shorter frames step the physics with the short dt (5 ms at 200 FPS).
- In the per-step kart force function (0x43F700, wheel loop at 0x43FB79..0x43FBBF) the suspension spring/damper are turned into soft-contact parameters P0 = 1/(dt*(c + k*dt)) and P1 = k*dt/(c + k*dt), with k = "wheels stiffness" * mass and c = "wheels damping" * mass from karts.txt. The solver treats them so that the effective spring is k*dt and the effective damper dt*(c + k*dt): 6663 N/unit and 178 Ns/unit per wheel at 60 FPS, but 2000 and 30 at 200 FPS (3.3x softer, ~6x less damped).
- Consequences at 200 FPS: kart sits 3.4 cm lower at rest (measured rest height fits sag = (W/4)/(k*dt) within 1 %); downforce (0.5*v^2) pushes the chassis box onto the road above ~29 units/s (clearance 0.1), so 16-49 % of the load rides on the chassis instead of the tyres -> drag (AI karts cover 17 % less distance), about 35 % less cornering force in a full-lock turn, and 2.5x more sudden vertical kicks.
- Proof: replacing dt by a fixed 1/60 in those formulas (P0 = 1/(h0*(c + k*h0)), P1 = k*dt/(c + k*h0)) makes a 200 FPS run match the 60 FPS run (ride height, acceleration, wheel loads, AI pace, cornering) within ~1 %. What remains is a pure time shift: at 200 FPS the controls are read more often, so the speed curve runs ~0.04-0.05 s ahead of the 60 FPS one (the user asked whether "38 > 37.7" means 60 FPS has the problem too - it does not).
- Since 2026-11-18 `tools/patch_200cc.py` ships this as an options-menu switch "60-FPS-Fahrphysik" (default off; stored as bytes `36 30 46` at settings.dat offset 0x49, i.e. GameParameters+0x4D..0x4F padding); details in the repo README.
- Grounding speed for a 20 kg kart: sqrt((0.4*400000/fps - 392)/0.5) -> 55 at 85 FPS, 49 at 100, 43 at 120, 38 at 144, 29 at 200 (kart top speed ~42-50), i.e. trouble starts around 100-120 FPS.
- Smaller frame-rate dependencies also seen in the code: airborne wheel spin decays *0.995 per step; computer karts' controllers run every other frame.

**Why:** the user keeps separate "FPS 60" and "FPS 200" installs because of this, and on 2026-11-18 asked for the fix as a setting they can turn on (not always-on).
**How to apply:** when touching the real-game switch, re-verify with the unattended test approach in [[mhk2-windowed-test-recipe]].
