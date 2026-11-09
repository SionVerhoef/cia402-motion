# SEW-EURODRIVE MOVI-C with the CiA402 device profile (MOVIDRIVE, MOVITRAC advanced, decentralized units)

**Read 2026-11-08**: SEW-EURODRIVE, *Manual – Inverters of the MOVI-C® Modular Automation
System with CiA402 Device Profile – Startup with EtherCAT® or POWERLINK*, 27805557/EN, edition
07/2023, cited as **[S p. N]**; and SEW-EURODRIVE, *Manual – Application Inverter
MOVIDRIVE® modular/system with CiA402 Device Profile – Parameter Description*, 25835130/EN,
edition 07/2018, cited as **[P p. N]**. SEW-EURODRIVE publishes its manuals and ESI
files under Online Support → Data & Documents at https://www.sew-eurodrive.com [S pp. 6, 32].

Neither document gives a firmware version; the 2023 manual says it describes the firmware
current at publication [S p. 6]. The startup manual covers MOVIDRIVE modular, system and
technology, MOVITRAC advanced, and the decentralized MOVIGEAR performance, MOVIMOT performance,
advanced and flexible units [S p. 10]. The parameter description covers MOVIDRIVE modular and
system only. The CiA402 profile is a separate device profile, with its own ESI files
(`SEW_MOVI-C_..._CiA402.xml`), not SEW's default SBusPLUS profile [S pp. 32, 56]. Where the two
documents disagree, this page says so.

## Index numbering and the second axis

- **SEW tools show every object in decimal**: 24640.0 is 0x6040:00, and SEW's own parameters
  (8334, 8364 …) are 0x208E, 0x20AC …, inside the manufacturer range [S pp. 17, 23, 61]. Convert
  before typing an index from MOVISUITE into a master's start-up list.
- **A MOVIDRIVE modular double-axis module (MDD..) puts axis 2 at index + 0x1000**: 0x7040,
  0x7041 …, and SEW parameters likewise [S pp. 17–22, 61, 88]. The profile's multi-axis offset
  is 0x800 (axis 2 at 0x6840), so a master that derives axis 2's indices itself gets them wrong.
- **Axis 2 is not created by a scan.** The master gets one axis per slave; axis 2 of an MDD has
  to be added by hand in the slot configuration [S pp. 55, 59].
- **SDO access is at most 4 bytes per parameter** [S p. 89].

## State machine

- **Statusword and transition bit patterns are the profile's** [S p. 16]. The documents do not
  say whether 0x000F in Ready to switch on goes through T3 and T4 in one step.
- **Each state is an SEW drive function (FCB)**: Switch on disabled to Switched on run FCB 01
  (output stage inhibit); Operation enabled with 0x6060 = 0 runs FCB 02 (stop) [S p. 15].
  0x6060 defaults to 0 [S p. 18], so enabling without writing a mode gives an enabled drive that
  holds and will not move.
- **The brake is applied in Switched on and released only in Operation enabled, Quick stop
  active and Fault reaction active** [S p. 15]. Configuration is marked as not permitted in those
  three states [S p. 16].
- **Controlword bit 14 (SEW) releases the brake without enable**, only if that is enabled under
  FCB 01 (SEW parameter 8501.2) [S pp. 17, 22; P pp. 249–250].
- **Statusword bit 3 is labelled "Fault reset"** in the 2023 object list [S p. 17] and "Fault"
  in the 2018 parameter description [P p. 342]: treat it as the profile's fault bit.

## Option codes

| Object | SEW allows | Default | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | 2, 6 | not stated | no 0, 1, 3–5, 7, 8 |
| 0x605B shutdown | absent | — | not in the object list |
| 0x605C disable operation | absent | — | not in the object list |
| 0x605D halt | 1 (slow-down ramp) | listed as 0, which is not an allowed value | only one choice |
| 0x605E fault reaction | −1, 2 | **−1** | −1 = decelerate "with 2147483647 inc/s" (sic), in effect as hard as the drive can |

[S p. 17; P p. 342]. **The braking delay at a fault is applied whatever 0x605E says** [S p. 13].
Quick-stop deceleration is 0x6085 [S p. 19]. The 2018 parameter description lists only 0x605D
of these [P p. 342].

**Bus loss is SEW's, not 0x6007.** The EtherCAT/SBusPLUS timeout is SEW parameter 8455.3,
default 500 ms [P p. 240]; the reaction is 8622.6, from warning to output stage inhibit, each
also with self-reset [P p. 301]. 0x6007 is not in the object list [S pp. 17–22].

## Modes of operation

- **1, 3, 6, 8, 9, 10.** No vl, PT, IP or CSTCA [S pp. 13, 18]. 0x6502 default 933 (bits 0, 2,
  5, 7, 8, 9) matches [S p. 22].
- **Negative 0x6060 values are SEW drive functions**: −13 stop at application limit, −14
  emergency stop (both on the quick-stop ramp), −18 rotor position identification, −19 position
  hold without brake, −21 brake test, −25 motor parameter measurement [S pp. 13, 18]. 0x6061 can
  also show −23 (brake test by the safety card) [S p. 18]; the 2018 list also shows −1, −4, −13
  and −22 there [P p. 343]. The 2018 0x6060 list has only −18, −19, −25 [P p. 343], so the set
  grew between editions.
- **The inverter's display shows the FCB number, not the mode**: pp 24, pv 3, hm 11, csp 16,
  csv 15, cst 17 [S pp. 13, 66, 68, 69, 71, 75–76].
- **Cycle times**: MOVIDRIVE 1 ms and multiples; MOVITRAC advanced and the DSI.. electronics
  cover 2 ms and multiples; at most 10 ms with distributed clocks [S p. 33]. MOVIGEAR performance
  on POWERLINK: 2 ms or longer [S p. 110].
- **0x60C2 must equal the master's cycle.** Default 1 ms (value 1, index −3) [S p. 21; P p. 353];
  set it in MOVISUITE or write 0x60C2:01 in the master's start-up list [S pp. 22, 62–64]. The
  2023 table gives both sub-indices a range of 0–2, which contradicts its own default of −3;
  the 2018 ranges are 1–255 and −3 to 0 [S p. 21; P p. 353].
- **CSV: the actual position lags 3–4 cycles.** SEW advises the master to compensate about 3.5
  cycles of dead time when it computes the following error [S p. 66].
- **CST: the drive limits speed only at the motor maximum**; the master must monitor it
  [S p. 68].

## Mode-specific bits

- **Statusword bit 10 in CSP, CSV and CST is a "status toggle"** [S p. 17; P p. 342], where the
  profile reserves it. Its rule is not described.
- **Bit 13 is listed only as homing error** [S p. 17; P p. 342]. No CSP following-error bit is
  documented; the lag-error reaction is SEW parameter 8622.3 [P p. 300].
- **PV bit 12 (speed zero) and PV target reached are not listed**; bit 10 is "target reached"
  for pp only [S p. 17].
- **0x6065 following error window defaults to −1** (signed INT32, range −1 to 2³¹−1) [S p. 18;
  P p. 344]. Presumably monitoring off; neither document says.

## Profile position

- New set-point on a rising edge of bit 4, acknowledged on statusword bit 12 (the timing diagram
  labels it "control word") [S p. 72].
- **0x60F2 takes 0, 64, 128, 192** (normal, negative only, positive only, shortest way) [S p. 73;
  P p. 356]. At exactly 180° in a 360° axis, "shortest" goes positive [S p. 73]. The manual
  says the code works only with controlword bits 5 and 6 "assigned accordingly", and labels its
  table "bit 6 / bit 5" [S pp. 72–73]; how that maps to the profile's 0x60F2 bits 6–7 is unclear.
- **The modulo range is 0x607B** (±2³⁰), and the text swaps sub-indices 1 and 2 between
  paragraphs [S pp. 18–19, 72–73; P p. 346].
- **0x6081 and 0x6083 default to 0**, 0x6084 to 300000 [S p. 19].

## Homing

- **Methods 1, 2, 10, 14, 17, 18, 26, 30, 33 and 37.** Default 37 [S p. 19; P pp. 348, 355–356].
  **37 only, not 35; no negative methods.** No home-switch-only methods (3–6, 19–22): home-cam
  homing is the reversing variant at a limit switch (10, 14, 26, 30) [S pp. 77–82].
- **The 2023 mode table calls methods 1 and 2 "negative/positive index pulse"** [S p. 13]; its
  object list, the method diagrams and the 2018 description all say limit switch and index pulse
  [S pp. 19, 76–77; P p. 348].
- **0x6098 is PDO-mappable in both directions**, and a value sent by PDO overrides one set in
  MOVISUITE or by SDO [S pp. 23–24, 75]. 0x6099 is not in the PDO lists [S p. 24].
- **The methods run SEW's reference travel (FCB 12)** [S p. 76].
- **The home cam and limit switches are drive inputs DI 01–DI 05**, assigned in SEW parameters
  8334.11–8334.15; 0x60FD shows them only once assigned [P pp. 50–52, 357]. **Limit switches
  must be 0-active** [P p. 30]. 0x60FD bit 3 is SEW's "interlock" [S p. 22].
- **When the axis otherwise runs in CSP, CSV or CST, the master's axis builds up following
  error while the drive homes**; reset the master axis before the next move [S p. 76].

## Units and scaling

- **No factor group.** 0x608F, 0x6091 and 0x6092 are not in the object list [S pp. 17–22]. The
  drive works in 65536 increments per motor revolution, whatever the encoder; user units belong
  in the master [S pp. 14, 65, 114]. Gear ratios therefore go in the master too [S pp. 65,
  117–118].
- **The documents disagree on velocity and acceleration units.** The 2023 manual states pp and
  pv speeds in inc/s and ramps in inc/s² (1800 rpm = 1966080 inc/s) [S pp. 14, 70, 73]. The
  2018 description gives 0x606C, 0x6081, 0x60FF and 0x6099 as "1E-4/min user unit" and
  0x6083/0x6084 as "1E-02/(min·s) user unit" [P pp. 344, 347–349, 357]. SEW's own speed user unit
  (8557) defaults to 9375/1024 with unit "inc/…" [P pp. 272–273], which converts 0.0001 rpm to
  inc/s, and the acceleration one (8560) 375/4096 "inc/s²" [P pp. 275–276]. Read that way, both
  documents mean inc/s at factory settings, but that is our inference. Check on the drive at
  low speed.
- **Torque objects (0x6071, 0x6072, 0x6077, 0x60B2, 0x60E0, 0x60E1) are in 0.1 % of nominal
  motor torque.** 0x6072, 0x60E0 and 0x60E1 default to 5000, i.e. 500 % [S pp. 18, 20–21].

## PDO mapping

- **Predefined slot modules: csp, csv, and "switching pp/pv" (the default)** [S p. 58].
- **Up to 8 extra objects of 32 bits each** can be added, including SEW parameters by index and
  sub-index (e.g. DC link voltage 8364.160) [S pp. 60–61]. The mode sections speak of at most 8
  entries in the cyclic image [S pp. 65–75]; whether that is 8 in total or 8 added is unclear.
- Mappable inputs and outputs are listed on [S pp. 23–24]. On POWERLINK only the objects
  listed under "channels" can be cyclic; the rest are SDO only [S p. 114].
- **0x1000 = 0x00020192** [S p. 17].

## Touch probe

Two probes, each on DI 1–4 or the encoder zero pulse, chosen in 0x60D0, with edge counters
0x60D5–0x60D8 [S pp. 20–21; P pp. 350–354]. The 2023 table says probe 2 also takes its source
from 0x60D0:01; the 2018 description says 0x60D0:02 [S p. 20; P p. 351].
