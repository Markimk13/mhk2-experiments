; Geometric driver for the computer karts (patch 1.10 work). Assembled by asm2py.py into the
; table GEO_DRIVER of tools/patch_200cc.py; never edit that table by hand.
;
; geo_on per class: 0 off (the stock game), 1 every kart whose set has ON (the test tools,
; geo_params.py), 2 the karts the menu asks for: the second row of the page "Gegner" (NEWV,
; 0..6) makes kart numbers 1..N drive this way; a save without the marker STDM counts as 0.
; Shipped: 2 in every class (up to 1.10-pre14 only in the tuning class).
; Hooked at 0x43A9EA in the controller update 0x43A4E0 (esi = controller), after the stock
; look-ahead: the stock steering ([esp+20h], the bearing of the planner's near point) stays,
; with optional values for it (SF, SN). The second entry, geo_line, gives the path planner a
; line to the inside of the bends (see there). Defaults: the best set of the tests of
; 2026-11-23 (runs\geo\b3, b4).
; In the classes switched on in geo_on it replaces the stock corner speed (0x43A9F5..0x43AAF4)
; by one from the track's own centre line with braking distance:
;   points P0..PK on the centre line, P0 at the kart's progress, spaced max(D0, v * DV) units;
;   radius R of each three neighbours, corner speed KC * (R + RW), allowed now
;   sqrt(vc^2 + 2 * A * distance), the smallest over the points, at most the track's speed
;   limit box (car+33Ch, reset to 999 as the stock code does) and at least VMIN;
;   brake = clamp((v - allowed) * KB, 0, 1). Then on at 0x43AAF5 like the stock code.
; Learned tables (geo_tables.inc, written by learn_tables.py from the player's recorded laps): per
; track 256 places along the lap with the player's speed and line. Where a place has data and PF
; is not 0 the allowed speed is PF * the player's speed there, or PT seconds ahead if that is
; lower, in place of the corner speed above; with PL the planner's line goes to the player's.
; One parameter set per kart number (car+304h, 0..6), so a test race can try six sets.
; The allowed speed is left in the controller's free field +88h for the recorder.
; The track's speed limit boxes (car+33Ch: 14 to 25 units/s at some places of five tracks, made
; for the stock driver) hold a kart with a learned speed far below the player's (15 where the
; player drives 50). Some boxes the learned driver needs, others only cost time (geo_boxes.py),
; so the table says it per place: an odd speed byte overrules a box there. BX (a test value) is
; the least share of the learned speed a box leaves at the other places: 0 the box rules.
; Lift (user, 2026-11-24: "off the gas until they have corrected"): with LS or LE not 0 the kart
; takes the throttle away (the stock code's throttle factor, the caller's [esp+10h]) while it is
; faster than LV, the steering it asks for is LS of the full lock or more and it is LE or more
; road widths from the learned line (LE 0: the steering alone; LS 0: the distance alone).
;
; Watch (user, 2026-11-24: "most importantly, that they reset after a few seconds"): geo_watch
; sits in front of the stock stuck check (0x43A708), which the game runs for every kart, the
; human players' too (a player who stands still for about 4 s is set back by the game itself).
; The watch leaves a kart alone while a human drives it (byte car+308h) and runs for every computer kart of the
; classes in geo_wdon, and in the other classes once a value of the page "Gegner" is changed
; (NEWV not 0 or TEMPOV not "Standard"), so 50 to 150 cc stay as the game has them by default. It keeps the farthest place reached (laps + progress, car+220h) and the
; time since in the controller, at +C0h and +C4h: the patcher makes the controller 8 bytes
; larger for that (0x40976D, 0C0h -> 0C8h; the new section is not writable). A kart that does not get WS laps beyond that place for WT seconds
; gets the game's own way back to the road ([car+5Ch]+8 = 1: the respawn helper 0x438560 posts
; "reset car" without a place, so the car goes to the middle of the road 15 units back). After
; that, and after any other reset (car state 20), it has WA seconds more. The watch also keeps
; the byte car+24Ch at 1: with 0 a reset goes to the place at car+23Ch that a "respawn" box of
; the level stored, and those are in side areas (the floor under Fabrik's bridge, the area at
; (-151, -2, 17) beside Fabrik's place 71) that a computer kart does not find its way out of. A kart that is WD laps or more behind its farthest place (a new
; race, a reset on a short lap) starts anew. Not while the game holds the car (states 10, 15,
; 20, 24, as in the stock check). Stock: the kart backs out for 1 s when it moved less than 1
; unit in 1 s, tries 2 s, and only then may ask for the reset; a kart that moves a little never
; gets one, and a kart that a "reset car" box of the level puts at a place of its own (Fabrik,
; the floor under the bridge at places 114..123: the box puts it at (-68, -1.3, -153), from
; where it drives into the pit again) loops until the race ends.
;
; A slow kart ahead (2026-11-24, after the pile-ups in the user's races: one kart stopped by an
; item, the karts behind drove into it). Two rules, on since 1.10-pre19 with OW 0.4, OB 20,
; OV 15 (OW 0 and OV 0 switch them off):
; - The game's planner (fn 0x439740) already puts every other kart within 50 units ahead on its
;   list of obstacles, as a box 3 units long and 0.15 road widths to each side, whatever its
;   speed, and the node loop moves the path to the nearer edge of a box it is in. geo_obst
;   (hooked at 0x43996A, behind the box's left edge; esi = the other car, edi = the planner)
;   makes the box of a slow kart larger for a kart that drives the learned way: it starts OB
;   units before that kart and reaches OW road widths to each side. "Slow" = its speed is below
;   OS times this kart's. A box that leaves less than 0.1 road widths to one edge of the road is
;   stretched over that edge, so the planner takes the other side. OW 0 = the game's box.
; - Braking (in geo_ai): a slow kart up to OD units ahead and within OW road widths across caps
;   the allowed speed at sqrt((its speed + OV)^2 + A2 * distance), so the kart arrives no faster
;   than OV above it. OV 0 = off.
;
; data magic: GEO1

.686
.model flat
.code
EXTERN X_403790:NEAR, X_42CE50:NEAR, X_4017F0:NEAR, X_4437F0:NEAR, X_4438D0:NEAR
EXTERN X_43AAF5:NEAR, X_43A9F5:NEAR, X_4395A0:NEAR, X_43A711:NEAR, X_439972:NEAR
PUBLIC geo_line
PUBLIC geo_watch
PUBLIC geo_obst

LOC     equ 114h
F       equ LOC + 20h          ; the caller's [esp+0] (behind pushad and the locals)
NP      equ 31                 ; dwords per parameter set
NEWV    equ 2E70h              ; game parameters: "Verbesserte Gegner" (patch_200cc.py NEW_VALUE)
TEMPOV  equ 2E6Ch              ; game parameters: "Tempo" of "Gegner" (OPP_VALUE), TEMPOSTD = "Standard"
TEMPOSTD equ -125
STDM    equ 2D98h              ; game parameters: the marker that makes NEWV and TEMPOV valid (STD_MARK)
STDMAGIC equ 47445453h
GEARV   equ 2E4Ch              ; game parameters: the tuning class' "Uebersetzung" in hundredths (155 = 250 cc)
P_D0    equ 0                  ; least point spacing (units)
P_DV    equ 4                  ; spacing per unit/s of speed
P_K     equ 8                  ; number of points - 1 (int, 2..24)
P_KC    equ 0Ch                ; corner speed per unit of radius
P_RW    equ 10h                ; radius added (the road is wider than its centre line)
P_A2    equ 14h                ; 2 * braking deceleration
P_KB    equ 18h                ; brake per unit/s too fast
P_VMIN  equ 1Ch                ; never ask for less
P_VMAX  equ 20h                ; no corner in sight
P_EPS   equ 24h                ; keeps a straight from dividing by 0
P_LAT   equ 28h                ; lateral position of the sampled line (0.5 = centre; below 0: the
                               ; kart's own, car+22Ch, kept within -LAT .. 1 + LAT)
P_ON    equ 2Ch                ; 0: this kart drives like the stock game (int)
P_CL    equ 30h                ; line: how far the target leaves the middle (0 = stock planner)
P_CS    equ 34h                ; line: curvature * CS = 1 is a full move to the inside
P_LEAD  equ 38h                ; line: the curve is measured this many units ahead of the node
P_LH    equ 3Ch                ; line: half the length of the measured bend (units)
P_LG    equ 40h                ; line: share of the way to the target per node
P_PF    equ 44h                ; learned speed: share of the player's speed (0 = corner speed from the curves)
P_PT    equ 48h                ; learned speed: also looks this many seconds ahead
P_PL    equ 4Ch                ; learned line: share of the way to the player's line per node (0 = the CL line)
P_LC    equ 50h                ; learned line: kept within -LC .. 1 + LC (0..1 = edge to edge; outside -1..2
                               ; the game sets the kart back on the track)
P_LS    equ 54h                ; lift: steering asked for, as a share of the full lock (0 = not looked at)
P_LE    equ 58h                ; lift: distance from the learned line in road widths (0 = not looked at)
P_LV    equ 5Ch                ; lift: never below this speed
P_BX    equ 60h                ; least share of the learned speed that a speed limit box leaves
P_LW    equ 64h                ; learned line: its distance from the middle of the road times LW (1 = the
                               ; player's line, 0 = the middle), so not every kart drives the same line
P_OS    equ 68h                ; a kart ahead is "slow" below OS times this kart's speed
P_OW    equ 6Ch                ; slow kart ahead: its obstacle box reaches OW road widths to each side (0 = the game's box)
P_OB    equ 70h                ; ... and starts OB units before it
P_OV    equ 74h                ; slow kart ahead: arrive no faster than OV above its speed (0 = no braking for it)
P_OD    equ 78h                ; ... looked for up to OD units ahead

; locals
T_OUT   equ 0                  ; point out (16 bytes)
T_V     equ 10h
T_L     equ 14h
T_STEP  equ 18h
T_PROG  equ 1Ch
T_DIST  equ 20h
T_ALLOW equ 24h
T_TP    equ 28h
T_N     equ 2Ch
T_A     equ 30h
T_B     equ 34h
T_LAT   equ 38h
T_CAR   equ 3Ch
T_PTS   equ 40h                ; 25 points * (x, z)
T_TAB   equ 108h               ; this track's learned table or 0
T_GP    equ 10Ch               ; the game parameters
T_BOX   equ 110h               ; a speed limit box may not ask for less than this

geo_ai PROC
    pushad
    sub     esp, LOC
    call    geo_pc
geo_pc:
    pop     ebx
    call    X_403790
    mov     edx, eax
    mov     [esp+T_GP], eax
    mov     eax, [eax+10h]                    ; engine class
    cmp     eax, 5
    ja      geo_off
    movzx   ecx, byte ptr [ebx+eax+(geo_on-geo_pc)]
    test    ecx, ecx
    jz      geo_off
    mov     edi, [esi+10h]                    ; the car
    mov     [esp+T_CAR], edi
    mov     eax, [edi+304h]                   ; kart number
    cmp     eax, 6
    jbe     geo_set
    xor     eax, eax
geo_set:
    cmp     ecx, 2                            ; 2: kart numbers 1..N of the menu
    jne     geo_all
    mov     ecx, eax
    test    ecx, ecx
    jnz     geo_cnt
    inc     ecx                               ; the player's kart after the finish counts as number 1
geo_cnt:
    cmp     dword ptr [edx+STDM], STDMAGIC
    jne     geo_off
    cmp     ecx, [edx+NEWV]
    jg      geo_off
geo_all:
    imul    eax, eax, NP*4
    lea     ebp, [ebx+eax+(geo_par-geo_pc)]
    cmp     dword ptr [ebp+P_ON], 0
    je      geo_off
    mov     eax, [edi+304h]
    call    geo_find
    mov     [esp+T_TAB], eax
    mov     ecx, edi
    call    X_42CE50                          ; speed
    fst     dword ptr [esp+F+1Ch]             ; where the stock code keeps it
    fstp    dword ptr [esp+T_V]
    call    X_4017F0                          ; race object
    mov     ecx, [eax+1Ch]                    ; its track path
    mov     [esp+T_TP], ecx
    call    X_4437F0                          ; lap length
    fstp    dword ptr [esp+T_L]
    fld     dword ptr [esp+T_V]               ; spacing = max(D0, v * DV)
    fmul    dword ptr [ebp+P_DV]
    fld     dword ptr [ebp+P_D0]
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_vstep                         ; D0 < v * DV
    fstp    st(1)
    jmp     geo_step
geo_vstep:
    fstp    st(0)
geo_step:
    fdiv    dword ptr [esp+T_L]
    fstp    dword ptr [esp+T_STEP]            ; progress per point
    fld     dword ptr [edi+224h]
    fstp    dword ptr [esp+T_PROG]
    fld     dword ptr [ebp+P_LAT]             ; the line's lateral position
    fldz
    fcomp   st(1)
    fnstsw  ax
    test    ah, 41h
    jz      geo_latown                        ; LAT < 0
    fstp    dword ptr [esp+T_LAT]
    jmp     geo_latset
geo_latown:
    fchs                                      ; m = -LAT
    fld     dword ptr [edi+22Ch]              ; kart's lateral; st1 = m
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jz      geo_lat1                          ; not below m
    fstp    st(0)
    fld     st(0)
geo_lat1:
    fld1
    fsub    st, st(2)                         ; 1 - m
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_lat2                          ; 1 - m < lateral: keep 1 - m
    fstp    st(0)
    jmp     geo_lat3
geo_lat2:
    fstp    st(1)
geo_lat3:
    fstp    dword ptr [esp+T_LAT]
    fstp    st(0)
geo_latset:
    mov     ecx, [ebp+P_K]
    inc     ecx
    mov     [esp+T_N], ecx
    lea     edi, [esp+T_PTS]
geo_pts:
    push    0
    push    dword ptr [esp+T_LAT+4]
    push    dword ptr [esp+T_PROG+8]
    lea     eax, [esp+T_OUT+0Ch]
    push    eax
    mov     ecx, [esp+T_TP+10h]
    call    X_4438D0                          ; point(out, progress, lateral, 0)
    mov     eax, [esp+T_OUT]
    mov     [edi], eax
    mov     eax, [esp+T_OUT+8]
    mov     [edi+4], eax
    add     edi, 8
    fld     dword ptr [esp+T_PROG]
    fadd    dword ptr [esp+T_STEP]
    fstp    dword ptr [esp+T_PROG]
    dec     dword ptr [esp+T_N]
    jnz     geo_pts

    fld     dword ptr [ebp+P_VMAX]
    fstp    dword ptr [esp+T_ALLOW]
    fldz
    fstp    dword ptr [esp+T_DIST]
    lea     edi, [esp+T_PTS]
    mov     ecx, [ebp+P_K]
    dec     ecx
    mov     [esp+T_N], ecx
geo_curve:                                    ; A = [edi], B = [edi+8], C = [edi+10h]
    fld     dword ptr [edi+8]
    fsub    dword ptr [edi]                   ; ux
    fld     dword ptr [edi+0Ch]
    fsub    dword ptr [edi+4]                 ; uz ux
    fld     st(1)
    fmul    st, st(0)
    fld     st(1)
    fmul    st, st(0)
    faddp   st(1), st
    fsqrt                                     ; la uz ux
    fst     dword ptr [esp+T_B]
    fadd    dword ptr [esp+T_DIST]
    fstp    dword ptr [esp+T_DIST]            ; distance to B
    fld     dword ptr [edi+10h]
    fsub    dword ptr [edi+8]                 ; wx uz ux
    fld     dword ptr [edi+14h]
    fsub    dword ptr [edi+0Ch]               ; wz wx uz ux
    fld     st(3)
    fmul    st, st(1)                         ; ux*wz wz wx uz ux
    fld     st(3)
    fmul    st, st(3)                         ; uz*wx ux*wz wz wx uz ux
    fstp    dword ptr [esp+T_A]
    fsub    dword ptr [esp+T_A]
    fabs
    fstp    dword ptr [esp+T_A]               ; |cross|; wz wx uz ux
    fmul    st, st(0)
    fxch    st(1)
    fmul    st, st(0)
    faddp   st(1), st
    fsqrt                                     ; lb uz ux
    fmul    dword ptr [esp+T_B]
    fstp    dword ptr [esp+T_B]               ; la * lb
    fstp    st(0)
    fstp    st(0)
    fld     dword ptr [edi+10h]
    fsub    dword ptr [edi]
    fmul    st, st(0)
    fld     dword ptr [edi+14h]
    fsub    dword ptr [edi+4]
    fmul    st, st(0)
    faddp   st(1), st
    fsqrt                                     ; lc
    fmul    dword ptr [esp+T_B]
    fstp    dword ptr [esp+T_B]               ; la * lb * lc
    fld     dword ptr [esp+T_A]
    fadd    st, st(0)
    fadd    dword ptr [ebp+P_EPS]
    fstp    dword ptr [esp+T_A]               ; 2 |cross| + eps
    fld     dword ptr [esp+T_B]
    fdiv    dword ptr [esp+T_A]               ; R
    fadd    dword ptr [ebp+P_RW]
    fmul    dword ptr [ebp+P_KC]              ; corner speed
    fmul    st, st(0)
    fld     dword ptr [esp+T_DIST]
    fmul    dword ptr [ebp+P_A2]
    faddp   st(1), st
    fsqrt                                     ; allowed here
    fcom    dword ptr [esp+T_ALLOW]
    fnstsw  ax
    test    ah, 1
    jz      geo_notless
    fst     dword ptr [esp+T_ALLOW]
geo_notless:
    fstp    st(0)
    add     edi, 8
    dec     dword ptr [esp+T_N]
    jnz     geo_curve

    mov     edi, [esp+T_CAR]
    mov     dword ptr [esp+T_BOX], 0
    cmp     dword ptr [ebp+P_PF], 0           ; the player's speed at this place
    je      geo_notab
    mov     eax, [esp+T_TAB]
    test    eax, eax
    jz      geo_notab
    fld     dword ptr [edi+224h]
    call    geo_val
    test    ecx, ecx
    jz      geo_tnone
    fld     dword ptr [esp+T_V]               ; and PT seconds ahead
    fmul    dword ptr [ebp+P_PT]
    fdiv    dword ptr [esp+T_L]
    fadd    dword ptr [edi+224h]
    call    geo_val
    test    ecx, ecx
    jz      geo_tone
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_tahead                        ; slower ahead
geo_tone:
    fstp    st(0)
    jmp     geo_tset
geo_tahead:
    fstp    st(1)
geo_tset:
    fmul    dword ptr [ebx+(geo_half-geo_pc)] ; 2 per unit/s (bit 0 is the box flag: half a unit/s)
    fmul    dword ptr [ebp+P_PF]
    mov     eax, [esp+T_GP]
    cmp     dword ptr [eax+10h], 5
    jne     geo_tgear                         ; the tuning class: the tables are 250 cc laps, so the
    fimul   dword ptr [eax+GEARV]             ; speed goes with the gearing (155 = 250 cc)
    fmul    dword ptr [ebx+(geo_g155-geo_pc)]
geo_tgear:
    fst     dword ptr [esp+T_ALLOW]
    fmul    dword ptr [ebp+P_BX]
    fstp    dword ptr [esp+T_BOX]
    fld     dword ptr [edi+224h]              ; the place: an odd speed byte overrules a box
    mov     dword ptr [esp+T_A], 256
    fimul   dword ptr [esp+T_A]
    fsub    dword ptr [ebx+(geo_half-geo_pc)]
    fistp   dword ptr [esp+T_A]
    mov     eax, [esp+T_A]
    and     eax, 255
    mov     ecx, [esp+T_TAB]
    test    byte ptr [ecx+eax*2], 1
    jz      geo_notab
    mov     eax, [esp+T_ALLOW]
    mov     [esp+T_BOX], eax
    jmp     geo_notab
geo_tnone:
    fstp    st(0)
geo_notab:
    fld     dword ptr [esp+T_ALLOW]
    fld     dword ptr [edi+33Ch]              ; the track's speed limit box
    fcom    dword ptr [esp+T_BOX]
    fnstsw  ax
    test    ah, 1
    jz      geo_boxok                         ; not below BX * the learned speed
    fstp    st(0)
    fld     dword ptr [esp+T_BOX]
geo_boxok:
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jz      geo_nobox
    fstp    st(1)
    jmp     geo_box
geo_nobox:
    fstp    st(0)
geo_box:
    mov     dword ptr [edi+33Ch], 4479C000h   ; 999, as the stock code leaves it
    cmp     dword ptr [ebp+P_OV], 0           ; a slow kart right ahead (st0 = the allowed speed)
    je      geo_anone
    call    X_4017F0                          ; the race: its cars
    mov     ecx, [eax+10h]
    mov     eax, [eax+14h]
    sub     eax, ecx
    sar     eax, 2
    mov     [esp+T_N], eax
    mov     [esp+T_A], ecx
geo_anext:
    dec     dword ptr [esp+T_N]
    js      geo_anone
    mov     eax, [esp+T_N]
    mov     ecx, [esp+T_A]
    mov     ecx, [ecx+eax*4]
    test    ecx, ecx
    jz      geo_anext
    cmp     ecx, edi
    je      geo_anext
    cmp     dword ptr [ecx+44h], 0            ; no vehicle yet: its speed cannot be asked for
    je      geo_anext
    fld     dword ptr [ecx+224h]              ; how far ahead, in laps (over the start line too)
    fsub    dword ptr [edi+224h]
    fcom    dword ptr [ebx+(geo_mhalf-geo_pc)]
    fnstsw  ax
    test    ah, 1
    jz      geo_awrap
    fld1
    faddp   st(1), st
geo_awrap:
    fmul    dword ptr [esp+T_L]               ; in units
    fst     dword ptr [esp+T_B]
    fldz
    fcomp   st(1)
    fnstsw  ax
    test    ah, 1
    jz      geo_apop                          ; not ahead
    fcomp   dword ptr [ebp+P_OD]
    fnstsw  ax
    test    ah, 1
    jz      geo_anext                         ; farther than OD
    fld     dword ptr [ecx+22Ch]
    fsub    dword ptr [edi+22Ch]
    fabs
    fcomp   dword ptr [ebp+P_OW]
    fnstsw  ax
    test    ah, 1
    jz      geo_anext                         ; beside this kart's way
    call    X_42CE50                          ; its speed
    fld     dword ptr [esp+T_V]
    fmul    dword ptr [ebp+P_OS]
    fcomp   st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_afast                         ; OS * this speed < its speed: not slow
    fadd    dword ptr [ebp+P_OV]
    fmul    st(0), st(0)
    fld     dword ptr [esp+T_B]
    fmul    dword ptr [ebp+P_A2]
    faddp   st(1), st
    fsqrt                                     ; the cap, the allowed speed
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_acap                          ; the cap is lower
    fstp    st(0)
    jmp     geo_anext
geo_acap:
    fstp    st(1)
    jmp     geo_anext
geo_afast:
    fstp    st(0)
    jmp     geo_anext
geo_apop:
    fstp    st(0)
    jmp     geo_anext
geo_anone:
    fld     dword ptr [ebp+P_VMIN]
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_abovemin                      ; VMIN < allowed
    fstp    st(1)
    jmp     geo_min
geo_abovemin:
    fstp    st(0)
geo_min:
    fst     dword ptr [esi+88h]
    fsubr   dword ptr [esp+T_V]
    fmul    dword ptr [ebp+P_KB]              ; brake wanted
    fldz
    fcomp   st(1)
    fnstsw  ax
    test    ah, 1
    jz      geo_nobrake                       ; not above 0
    fld1
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jz      geo_brake1                        ; 1 >= brake
    fxch    st(1)
geo_brake1:
    fstp    st(0)
    fstp    dword ptr [esp+F+14h]
    jmp     geo_lift
geo_nobrake:
    fstp    st(0)
    mov     dword ptr [esp+F+14h], 0
geo_lift:
    mov     eax, [ebp+P_LS]
    or      eax, [ebp+P_LE]
    jz      geo_done                          ; both 0: no lift
    fld     dword ptr [esp+T_V]
    fcomp   dword ptr [ebp+P_LV]
    fnstsw  ax
    test    ah, 1
    jnz     geo_done                          ; slower than LV
    fld     dword ptr [esp+F+20h]             ; the steering the stock code is about to ask for
    fdiv    dword ptr [esi+0BCh]
    fabs
    fcomp   dword ptr [ebp+P_LS]
    fnstsw  ax
    test    ah, 1
    jnz     geo_done                          ; less than LS
    cmp     dword ptr [ebp+P_LE], 0
    je      geo_liftnow
    mov     eax, [esp+T_TAB]
    test    eax, eax
    jz      geo_done                          ; no learned line on this track
    inc     eax
    fld     dword ptr [edi+224h]
    call    geo_val
    test    ecx, ecx
    jz      geo_liftnone
    fmul    dword ptr [ebx+(geo_lk-geo_pc)]   ; byte = 1 + 63.5 * (lateral + 1.5)
    fsub    dword ptr [ebx+(geo_lo-geo_pc)]
    fsub    dword ptr [edi+22Ch]
    fabs
    fcomp   dword ptr [ebp+P_LE]
    fnstsw  ax
    test    ah, 1
    jnz     geo_done                          ; nearer than LE
geo_liftnow:
    mov     dword ptr [esp+F+10h], 0
    jmp     geo_done
geo_liftnone:
    fstp    st(0)
geo_done:
    add     esp, LOC
    popad
    jmp     X_43AAF5
geo_off:
    add     esp, LOC
    popad
    mov     ecx, [esi+10h]                    ; displaced
    mov     dword ptr [esp+14h], 0
    jmp     X_43A9F5

;
; geo_pset: eax = a car -> eax = its parameter set, or 0 if it drives like the stock game (the
; same test as at the start of geo_ai and geo_line). Keeps every other register.
geo_pset:
    push    ebx
    push    ecx
    push    edx
    push    esi
    mov     esi, eax
    call    geo_spc
geo_spc:
    pop     ebx
    call    X_403790
    mov     edx, eax
    mov     eax, [edx+10h]
    cmp     eax, 5
    ja      geo_snone
    movzx   ecx, byte ptr [ebx+eax+(geo_on-geo_spc)]
    test    ecx, ecx
    jz      geo_snone
    mov     eax, [esi+304h]
    cmp     eax, 6
    jbe     geo_sok
    xor     eax, eax
geo_sok:
    cmp     ecx, 2
    jne     geo_sall
    mov     ecx, eax
    test    ecx, ecx
    jnz     geo_scnt
    inc     ecx
geo_scnt:
    cmp     dword ptr [edx+STDM], STDMAGIC
    jne     geo_snone
    cmp     ecx, [edx+NEWV]
    jg      geo_snone
geo_sall:
    imul    eax, eax, NP*4
    lea     eax, [ebx+eax+(geo_par-geo_spc)]
    cmp     dword ptr [eax+P_ON], 0
    jne     geo_sdone
geo_snone:
    xor     eax, eax
geo_sdone:
    pop     esi
    pop     edx
    pop     ecx
    pop     ebx
    ret
;
; geo_obst: see "A slow kart ahead" at the top. In: esi = the other car, edi = the planner,
; [esp+18h] the box's length in laps (3 units), [esp+50h] its start, [esp+58h] its length,
; [esp+5Ch] its width; st0 = its left edge, stored by the displaced instruction.
O_F     equ 20h                ; the caller's [esp+0] behind pushad
geo_obst::
    fstp    dword ptr [esp+54h]               ; displaced
    pushad
    call    geo_opc
geo_opc:
    pop     ebx
    mov     eax, [edi+10h]
    call    geo_pset
    test    eax, eax
    jz      geo_oend
    mov     ebp, eax
    cmp     dword ptr [ebp+P_OW], 0
    je      geo_oend
    mov     ecx, [edi+10h]
    cmp     dword ptr [ecx+44h], 0            ; a car without its vehicle yet (while the race loads):
    je      geo_oend                          ; the speed function would read through a null pointer
    cmp     dword ptr [esi+44h], 0
    je      geo_oend
    call    X_42CE50
    fmul    dword ptr [ebp+P_OS]
    mov     ecx, esi
    call    X_42CE50
    fcompp                                    ; its speed, OS * this kart's speed
    fnstsw  ax
    test    ah, 1
    jz      geo_oend                          ; not slower: the game's box
    fld     dword ptr [esp+O_F+18h]
    fmul    dword ptr [ebx+(geo_third-geo_opc)]   ; one unit in laps
    fld     st(0)
    fmul    dword ptr [ebp+P_OB]
    fld     dword ptr [esi+224h]
    fsub    st(0), st(1)
    fstp    dword ptr [esp+O_F+50h]           ; starts OB units before the kart
    fld     dword ptr [esp+O_F+18h]
    fmul    dword ptr [ebx+(geo_half-geo_opc)]
    faddp   st(1), st
    fst     dword ptr [esp+O_F+58h]           ; and ends 1.5 units behind it, as the game's
    fstp    dword ptr [esp+O_F+18h]
    fstp    st(0)
    fld     dword ptr [esi+22Ch]
    fsub    dword ptr [ebp+P_OW]              ; left edge
    fld     dword ptr [ebp+P_OW]
    fadd    st(0), st(0)                      ; width, left edge
    fld     dword ptr [ebx+(geo_om-geo_opc)]
    fcomp   st(2)
    fnstsw  ax
    test    ah, 1
    jnz     geo_oleft                         ; OM < left edge: room on the left
    fstp    st(0)
    fstp    st(0)
    fld1
    fchs                                      ; no room: the box starts far left of the road
    fld     dword ptr [esi+22Ch]
    fadd    dword ptr [ebp+P_OW]
    fld1
    faddp   st(1), st                         ; and still ends OW right of the kart
    jmp     geo_oput
geo_oleft:
    fld     st(1)
    fadd    st(0), st(1)                      ; right edge, width, left edge
    fld1
    fsub    dword ptr [ebx+(geo_om-geo_opc)]
    fcompp                                    ; 1 - OM, right edge
    fnstsw  ax
    test    ah, 1
    jz      geo_oput                          ; room on the right
    fstp    st(0)
    fld     dword ptr [ebx+(geo_wide-geo_opc)]    ; no room: the box reaches far right
geo_oput:
    fstp    dword ptr [esp+O_F+5Ch]
    fstp    dword ptr [esp+O_F+54h]
geo_oend:
    popad
    fld     dword ptr [esp+50h]               ; displaced
    jmp     X_439972
;
; geo_find: eax = kart number -> eax = this track's learned table or 0. The track index as the
; race setup takes it (0x4087C6): in a championship (game modes 1 and 3, parameters +1Ch) the
; entry +48h (the race's number) of the list at +28h, else +20h, the track of the time trial
; menu. (Up to 1.10-pre16 always +20h: in a real championship that is the track the menu showed
; last, so the karts drove another track's line and speed.) While geo_varon is set (the test tools, ai_race.py --geo-tables) every
; kart number has a table of its own in geo_var, so one race compares six tables.
geo_find:
    push    ecx
    push    edx
    push    eax
    call    X_403790
    mov     ecx, [eax+1Ch]
    cmp     ecx, 1
    je      geo_fchamp
    cmp     ecx, 3
    je      geo_fchamp
    mov     eax, [eax+20h]
    jmp     geo_fgot
geo_fchamp:
    mov     ecx, [eax+48h]
    and     ecx, 3
    mov     eax, [eax+ecx*4+28h]
geo_fgot:
    call    geo_fpc
geo_fpc:
    pop     edx
    pop     ecx                               ; the kart number
    cmp     byte ptr [edx+(geo_varon-geo_fpc)], 0
    je      geo_ftrack
    cmp     ecx, 6
    jbe     geo_fvar
    xor     ecx, ecx
geo_fvar:
    shl     ecx, 9
    lea     eax, [edx+ecx+(geo_var-geo_fpc)]
    pop     edx
    pop     ecx
    ret
geo_ftrack:
    cmp     eax, [edx+(geo_ntab-geo_fpc)]
    jae     geo_fnone
    shl     eax, 9
    lea     eax, [edx+eax+(geo_tab-geo_fpc)]
    pop     edx
    pop     ecx
    ret
geo_fnone:
    xor     eax, eax
    pop     edx
    pop     ecx
    ret
;
; geo_val: st0 = progress (any lap) -> st0 = the table's byte there, between two places by the
; share of the way; eax = the table (+1 for the line), kept. ecx = 0 and st0 = 0 when one of the
; two places has no data. Changes ecx, edx.
geo_val:
    sub     esp, 8
    mov     dword ptr [esp], 256
    fimul   dword ptr [esp]
    mov     dword ptr [esp], 3F800000h
    fsub    dword ptr [esp]
    fist    dword ptr [esp+4]                 ; the place before (places count from their middle)
    fisub   dword ptr [esp+4]
    mov     dword ptr [esp], 3F000000h
    fadd    dword ptr [esp]                   ; share of the way to the next
    mov     ecx, [esp+4]
    lea     edx, [ecx+1]
    and     ecx, 255
    and     edx, 255
    movzx   ecx, byte ptr [eax+ecx*2]
    movzx   edx, byte ptr [eax+edx*2]
    test    ecx, ecx
    jz      geo_vnone
    test    edx, edx
    jz      geo_vnone
    mov     [esp], ecx
    mov     [esp+4], edx
    fild    dword ptr [esp+4]
    fisub   dword ptr [esp]
    fmulp   st(1), st
    fiadd   dword ptr [esp]
    add     esp, 8
    ret
geo_vnone:
    fstp    st(0)
    fldz
    xor     ecx, ecx
    add     esp, 8
    ret

;
; The line: hooked at 0x439596 in the path planner's node loop (fn 0x4394C0; esi = planner,
; [esi+10h] its car, ebp = the track path, [esp+1Ch] the node's progress, [esp+10h] its lateral
; position, carried from node to node, after the stock drift towards the middle). With PL and
; a learned line at the node it moves the lateral position towards that line by PL. Else it moves the
; lateral position towards 0.5 + CL * clamp(CS * curvature, -1, 1), the curvature (signed) of
; the centre line LEAD units ahead of the node, by LG per node. The obstacle dodging follows.
L_F     equ 60h                ; the caller's [esp+0]
L_L     equ 28h
L_PROG  equ 2Ch
L_STEP  equ 30h
L_N     equ 34h
L_A     equ 38h
L_B     equ 3Ch
geo_line::
    pushad
    sub     esp, 40h
    call    geo_lpc
geo_lpc:
    pop     ebx
    call    X_403790
    mov     edx, eax
    mov     eax, [eax+10h]
    cmp     eax, 5
    ja      geo_lstock
    movzx   edi, byte ptr [ebx+eax+(geo_on-geo_lpc)]
    test    edi, edi
    jz      geo_lstock
    mov     ecx, [esi+10h]
    mov     eax, [ecx+304h]
    cmp     eax, 6
    jbe     geo_lset
    xor     eax, eax
geo_lset:
    cmp     edi, 2                            ; 2: kart numbers 1..N of the menu
    jne     geo_lall
    mov     ecx, eax
    test    ecx, ecx
    jnz     geo_lcnt
    inc     ecx
geo_lcnt:
    cmp     dword ptr [edx+STDM], STDMAGIC
    jne     geo_lstock
    cmp     ecx, [edx+NEWV]
    jg      geo_lstock
geo_lall:
    imul    eax, eax, NP*4
    lea     edi, [ebx+eax+(geo_par-geo_lpc)]
    cmp     dword ptr [edi+P_ON], 0
    je      geo_lstock
    cmp     dword ptr [edi+P_PL], 0           ; the player's line at the node
    je      geo_lgeo
    mov     eax, [esi+10h]
    mov     eax, [eax+304h]
    call    geo_find
    test    eax, eax
    jz      geo_lgeo
    inc     eax
    fld     dword ptr [esp+L_F+1Ch]
    call    geo_val
    test    ecx, ecx
    jz      geo_lnone
    fmul    dword ptr [ebx+(geo_lk-geo_lpc)]  ; byte = 1 + 63.5 * (lateral + 1.5)
    fsub    dword ptr [ebx+(geo_lo-geo_lpc)]
    fsub    dword ptr [ebx+(geo_half-geo_lpc)]
    fmul    dword ptr [edi+P_LW]              ; this kart's share of the way from the middle to the line
    fadd    dword ptr [ebx+(geo_half-geo_lpc)]
    fld     dword ptr [edi+P_LC]              ; kept within -LC .. 1 + LC
    fchs
    fcom    st(1)
    fnstsw  ax
    test    ah, 41h
    jnz     geo_lca                           ; -LC <= line
    fxch    st(1)
geo_lca:
    fstp    st(0)
    fld1
    fadd    dword ptr [edi+P_LC]
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jnz     geo_lcb                           ; 1 + LC < line
    fstp    st(0)
    jmp     geo_lcc
geo_lcb:
    fstp    st(1)
geo_lcc:
    fsub    dword ptr [esp+L_F+10h]
    fmul    dword ptr [edi+P_PL]
    fadd    dword ptr [esp+L_F+10h]
    fstp    dword ptr [esp+L_F+10h]
    jmp     geo_lstock
geo_lnone:
    fstp    st(0)
geo_lgeo:
    cmp     dword ptr [edi+P_CL], 0
    je      geo_lstock
    mov     ecx, ebp
    call    X_4437F0                          ; lap length
    fstp    dword ptr [esp+L_L]
    fld     dword ptr [edi+P_LEAD]
    fsub    dword ptr [edi+P_LH]
    fdiv    dword ptr [esp+L_L]
    fadd    dword ptr [esp+L_F+1Ch]
    fstp    dword ptr [esp+L_PROG]
    fld     dword ptr [edi+P_LH]
    fdiv    dword ptr [esp+L_L]
    fstp    dword ptr [esp+L_STEP]
    mov     dword ptr [esp+L_N], 3
    lea     esi, [esp+10h]
geo_lpts:
    push    0
    push    3F000000h
    push    dword ptr [esp+L_PROG+8]
    lea     eax, [esp+0Ch]
    push    eax
    mov     ecx, ebp
    call    X_4438D0
    mov     eax, [esp]
    mov     [esi], eax
    mov     eax, [esp+8]
    mov     [esi+4], eax
    add     esi, 8
    fld     dword ptr [esp+L_PROG]
    fadd    dword ptr [esp+L_STEP]
    fstp    dword ptr [esp+L_PROG]
    dec     dword ptr [esp+L_N]
    jnz     geo_lpts
    fld     dword ptr [esp+18h]
    fsub    dword ptr [esp+10h]               ; ux
    fld     dword ptr [esp+24h]
    fsub    dword ptr [esp+1Ch]               ; wz ux
    fmul                                      ; ux * wz
    fld     dword ptr [esp+1Ch]
    fsub    dword ptr [esp+14h]               ; uz
    fld     dword ptr [esp+20h]
    fsub    dword ptr [esp+18h]               ; wx uz
    fmul                                      ; uz * wx, ux * wz
    fstp    dword ptr [esp+L_A]
    fsub    dword ptr [esp+L_A]               ; cross
    fadd    st, st(0)
    fstp    dword ptr [esp+L_A]               ; 2 cross
    fld     dword ptr [esp+18h]               ; la * lb * lc
    fsub    dword ptr [esp+10h]
    fmul    st, st(0)
    fld     dword ptr [esp+1Ch]
    fsub    dword ptr [esp+14h]
    fmul    st, st(0)
    faddp   st(1), st
    fsqrt
    fld     dword ptr [esp+20h]
    fsub    dword ptr [esp+18h]
    fmul    st, st(0)
    fld     dword ptr [esp+24h]
    fsub    dword ptr [esp+1Ch]
    fmul    st, st(0)
    faddp   st(1), st
    fsqrt
    fmul
    fld     dword ptr [esp+20h]
    fsub    dword ptr [esp+10h]
    fmul    st, st(0)
    fld     dword ptr [esp+24h]
    fsub    dword ptr [esp+14h]
    fmul    st, st(0)
    faddp   st(1), st
    fsqrt
    fmul
    fadd    dword ptr [edi+P_EPS]
    fstp    dword ptr [esp+L_B]
    fld     dword ptr [esp+L_A]
    fdiv    dword ptr [esp+L_B]               ; signed curvature
    fmul    dword ptr [edi+P_CS]
    fld1                                      ; clamp to -1 .. 1
    fcom    st(1)
    fnstsw  ax
    test    ah, 1
    jz      geo_lc1                           ; 1 >= t
    fxch    st(1)
geo_lc1:
    fstp    st(0)
    fld1
    fchs
    fcom    st(1)
    fnstsw  ax
    test    ah, 41h
    jnz     geo_lc2                           ; -1 <= t
    fxch    st(1)
geo_lc2:
    fstp    st(0)
    fmul    dword ptr [edi+P_CL]
    fadd    dword ptr [ebx+(geo_half-geo_lpc)] ; target
    fsub    dword ptr [esp+L_F+10h]
    fmul    dword ptr [edi+P_LG]
    fadd    dword ptr [esp+L_F+10h]
    fstp    dword ptr [esp+L_F+10h]
    add     esp, 40h
    popad
    mov     [esp+18h], edi                    ; displaced
    jmp     X_4395A0
geo_lstock:
    add     esp, 40h
    popad
    mov     [esp+18h], edi                    ; displaced
    jmp     X_4395A0

; ---- the watch: a kart without progress goes back to the road -------------------------------
; in: esi = controller, [esp+8Ch] = frame time; eax, ecx, edx free. out: ecx = car,
; eax = [car+2D0h], as the two displaced instructions leave them.
geo_watch::
    mov     ecx, [esi+10h]                    ; displaced
    push    ebx
    push    edi
    call    geo_wpc
geo_wpc:
    pop     ebx
    lea     edi, [esi+0C0h]                   ; farthest place, seconds since
    cmp     byte ptr [ecx+308h], 0            ; a human player drives this kart: the game's own check only
    jne     geo_wend
    cmp     dword ptr [ecx+2D0h], 2           ; the race runs?
    jne     geo_wnew
    push    ecx
    call    X_403790
    pop     ecx
    mov     edx, eax
    mov     eax, [edx+10h]                    ; engine class
    cmp     eax, 5
    ja      geo_wend
    cmp     byte ptr [ebx+eax+(geo_wdon-geo_wpc)], 0
    jne     geo_won
    cmp     dword ptr [edx+STDM], STDMAGIC    ; 50 to 150 cc: only with a changed "Gegner" value
    jne     geo_wend
    cmp     dword ptr [edx+NEWV], 0
    jne     geo_won
    cmp     dword ptr [edx+TEMPOV], TEMPOSTD
    je      geo_wend
geo_won:
    mov     byte ptr [ecx+24Ch], 1            ; every reset goes to the road, see above
    cmp     dword ptr [ecx+29Ch], 20          ; just set back by anything: WA seconds to get going
    je      geo_wgrace
    fld     dword ptr [ecx+220h]
    fld     dword ptr [edi]
    fld     st(1)
    fadd    dword ptr [ebx+(geo_wdd-geo_wpc)]
    fcomp   st(1)                             ; place + WD < farthest: start anew
    fnstsw  ax
    test    ah, 1
    jnz     geo_wpop
    fadd    dword ptr [ebx+(geo_wds-geo_wpc)]
    fcompp                                    ; farthest + WS < place: progress
    fnstsw  ax
    test    ah, 1
    jnz     geo_wnew
    fld     dword ptr [edi+4]
    fadd    dword ptr [esp+94h]               ; the frame time (8Ch + two pushes)
    fst     dword ptr [edi+4]
    fcomp   dword ptr [ebx+(geo_wdt-geo_wpc)]
    fnstsw  ax
    test    ah, 41h
    jnz     geo_wend                          ; not yet WT seconds
    mov     eax, [ecx+29Ch]                   ; the game holds the car: wait
    cmp     eax, 10
    je      geo_wend
    cmp     eax, 15
    je      geo_wend
    cmp     eax, 20
    je      geo_wend
    cmp     eax, 24
    je      geo_wend
    mov     eax, [ecx+5Ch]
    test    eax, eax
    jz      geo_wend
    mov     byte ptr [eax+8], 1               ; back to the road, the game's own way
geo_wgrace:
    mov     eax, [ebx+(geo_wda-geo_wpc)]
    mov     [edi+4], eax                      ; -WA: time to get there again
    jmp     geo_wend
geo_wpop:
    fstp    st(0)
    fstp    st(0)
geo_wnew:
    mov     eax, [ecx+220h]
    mov     [edi], eax
    mov     dword ptr [edi+4], 0
geo_wend:
    pop     edi
    pop     ebx
    mov     eax, [ecx+2D0h]                   ; displaced
    jmp     X_43A711

    db      "GEO1"
geo_on  db  2, 2, 2, 2, 2, 2, 0, NP           ; per class: 50, 100, 150, 200, 250 cc, tuning; -; NP
geo_par LABEL DWORD
    REPT 7                                    ; kart numbers 0..6
    dd  4.0, 0.12, 14, 2.2, 4.0, 50.0, 0.5, 12.0, 999.0, 0.001, 0.5, 1
    dd  -0.25, 30.0, 10.0, 6.0, 0.4, 1.1, 0.2, 0.5, 0.75, 0.0, 0.0, 25.0, 0.0, 1.0
    dd  0.5, 0.4, 20.0, 15.0, 40.0            ; OS, OW, OB, OV, OD: the best set of the races of 2026-11-24
    ENDM
geo_half dd 0.5
geo_mhalf dd -0.5
geo_third dd 0.33333334
geo_om  dd  0.1                               ; least room beside a slow kart's box (road widths)
geo_wide dd 3.0
geo_g155 dd 0.0064516129                      ; 1 / 155
geo_lk  dd  0.015748031                       ; 1 / 63.5
geo_lo  dd  1.515748031                       ; 1.5 + 1 / 63.5
geo_ntab dd 8                                 ; tracks in geo_tab
geo_tab LABEL BYTE
    INCLUDE geo_tables.inc
    db      "GEO2"                            ; the test tools find the next two by this
geo_varon db 0, 0, 0, 0                       ; not 0: every kart number drives its table in geo_var
geo_var db  7 * 512 dup (0)
    db      "GEO3"                            ; the watch (the test tools find it by this)
geo_wdon db 0, 0, 0, 1, 1, 1, 0, 0            ; per class: 50, 100, 150, 200, 250 cc, tuning
geo_wdt dd  5.0                               ; WT: seconds without progress
geo_wda dd  -3.0                              ; -WA: seconds more after the watch set the kart back
geo_wdd dd  0.02                              ; WD: laps behind the farthest place that start it anew
geo_wds dd  0.002                             ; WS: laps that count as progress
    db      0                                 ; so the zeros end where dumpbin reads the next code in step
geo_ai ENDP
END
