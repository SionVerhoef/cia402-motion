# Units and scaling on the drive

Position, velocity and acceleration objects are in **user units**, which the drive converts to
encoder increments. Master and drive must agree on what one unit is, or the axis moves the wrong
distance at the wrong speed and nothing reports an error. Scaling inside the master (TwinCAT NC's
scaling factor and so on) belongs to **twincat-motion**. This page covers the drive side.

## The factor group

All of these are optional in the profile, and many drives leave some or all of them out:

| Object | Holds | Meaning |
|---|---|---|
| 0x608F position encoder resolution | :01 increments, :02 motor revolutions | increments per motor revolution |
| 0x6091 gear ratio | :01 motor revolutions, :02 shaft revolutions | motor turns per output-shaft turn |
| 0x6092 feed constant | :01 feed, :02 shaft revolutions | user units per output-shaft turn |
| 0x6096 velocity factor | :01 numerator, :02 divisor | velocity units relative to position units |

Together:

    increments = user units × (0x608F:01 / 0x608F:02) × (0x6091:01 / 0x6091:02)
                            / (0x6092:01 / 0x6092:02)

Example: a 20-bit encoder (1,048,576 increments per turn), a 1:1 gear, and 10,000 user units per
turn. Set 0x6092 = 10,000 : 1, and 10,000 units then make 1,048,576 increments: one turn.

Where the factor group is missing, the drive works in increments, or in its own unit objects.
Some drives use SI-unit objects (0x60A8 position, 0x60A9 velocity). Others put the gear in a
manufacturer object, or allow it only at some cycle times. The vendor pages have the cases read
for this skill. Ask **ethercat-esi** which of these objects a particular drive has.

Velocity is usually user units per second and acceleration user units per second², unless
0x6096, the SI-unit objects or a vendor object say otherwise. Masters differ in what they assume,
so set it explicitly and test with a slow move of known length.

Torque and current are in thousandths of the rated values 0x6076 (mN·m) and 0x6075 (mA): 1000 is
rated torque.

## The 32-bit budget

Position is INT32: ±2,147,483,648 units. The travel before it wraps is

    revolutions each way = 2^31 / (user units per motor revolution)

With raw increments from a 24-bit encoder (16,777,216 per turn) that is 128 turns each way:
640 mm on a 5 mm-pitch screw, which a long axis exceeds. With 1 µm units on the same screw (5000
per turn) it is about 429,000 turns. Check the budget for the longest stroke, and for the run
time of an endless rotary axis. Whether a drive tolerates the wrap, and how it handles a modulo
axis (0x607B), is vendor-specific.

## Direction

0x607E polarity: bit 7 reverses position (set-point and actual), bit 6 reverses velocity. Set
direction in one place only, drive or master. Reversing it in both cancels out, and the next
person to change one makes the axis run away from where it should go.
