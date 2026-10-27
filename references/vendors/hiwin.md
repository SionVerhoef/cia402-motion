# HIWIN D-series EtherCAT (CoE) drives

**Read 2026-10-26**: HIWIN "Drive User Guide" version 1.0 (revision 2014-03-17), for the
D-series CoE drive, https://www.hiwin.com/wp-content/uploads/ethercat_drive_user_guide.pdf,
§3.5 p. 11 and §9.4 pp. 34–37. The guide is from 2014. Check whether a newer one covers the
drive and firmware actually used.

- **0x6098 homing method is typed UINT16**, read/write and not PDO-mappable. The profile types it
  INT8. Write it with a 16-bit SDO: a 1-byte write to a 2-byte object is typically refused with a
  length-mismatch SDO abort.
- **Eight homing methods: 1–6, 33 and 34.** 0 is no homing. There are no methods without the
  index pulse (17–30), no current-position method (35/37), and no negative methods.
