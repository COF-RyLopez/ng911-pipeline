# One Address UID per real-world address; NGUID built from it, not the GERS ID

Overture address GERS IDs change whenever any attribute or location changes and aren't in the GERS
registry, so an NGUID built on them (as the Extension did at 0.7.0) changes under a 911 authority's feet.
Each real-world address gets one Address UID instead: the Source agency's own ID where it has one,
otherwise one we mint. NGUIDs are built from the Address UID, and every GERS ID the address has carried is
recorded against it in the lineage ledger. Changing this later would change every published NGUID.
