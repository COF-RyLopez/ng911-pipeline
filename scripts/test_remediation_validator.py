#!/usr/bin/env python3
"""
scripts/test_remediation_validator.py

Unit tests for the NG911 Gamified Remediation Validation Engine and Fix Token Economy.
Verifies:
1. Spatial containment (inside vs outside building footprint)
2. Offset distance delta (improving vs deteriorating)
3. NENA / CLDXF schema integrity (numeric HNO, valid directionals, valid postal code)
4. Parity consistency (left/right road parity)
5. Tiered Fix Token awards (Common, Rare, Epic, Ground-Truth Corroboration)
"""

import unittest
from typing import Dict, Any, Tuple

# Predefined valid NENA CLDXF directionals and street types
VALID_DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "NORTH", "SOUTH", "EAST", "WEST"}
VALID_STREET_TYPES = {"ST", "AVE", "BLVD", "RD", "LN", "DR", "WAY", "CT", "CIR", "PKWY", "PL"}

def calculate_fix_tokens(
    is_contained_now: bool,
    was_contained_before: bool,
    orig_offset: float,
    new_offset: float,
    is_unrouted_resolved: bool,
    has_subaddress_added: bool,
    has_ground_truth_corroborated: bool
) -> Tuple[int, str, list]:
    """
    Evaluates proposed edit and calculates Fix Tokens (FTs) and rank badge.
    """
    tokens = 0
    reasons = []

    # 1. Base Snap to Footprint (10 FTs)
    if is_contained_now and not was_contained_before:
        tokens += 10
        reasons.append("Base Fix: Snapped outside point into building footprint (+10 FTs)")

    # 2. Road Snapping Delta (+10 FTs if improved by > 15 meters)
    if new_offset < orig_offset and (orig_offset - new_offset) >= 15.0:
        tokens += 10
        reasons.append("Offset Improvement: Reduced road offset delta significantly (+10 FTs)")

    # 3. Unrouted Road Resolved (Rare: +50 FTs)
    if is_unrouted_resolved:
        tokens += 50
        reasons.append("Rare Fix: Resolved unrouted/orphaned address road snapping (+50 FTs)")

    # 4. Multi-Unit / Structural Sub-address Added (Epic: +100 FTs)
    if has_subaddress_added:
        tokens += 100
        reasons.append("Epic Fix: Provided structural 3D sub-address or unit specification (+100 FTs)")

    # 5. Ground-Truth Corroboration via Mapillary (Bonus: +25 FTs)
    if has_ground_truth_corroborated:
        tokens += 25
        reasons.append("Ground-Truth Bonus: Corroborated with Mapillary street-level detection (+25 FTs)")

    # Determine Tier Classification
    if tokens >= 100:
        tier = "EPIC"
    elif tokens >= 50:
        tier = "RARE"
    elif tokens >= 25:
        tier = "UNCOMMON"
    elif tokens > 0:
        tier = "COMMON"
    else:
        tier = "NONE"

    return tokens, tier, reasons


def validate_cldxf_schema(record: Dict[str, Any]) -> Tuple[bool, list]:
    """
    Validates civic address attributes against NENA-STA-006.3 / CLDXF.
    """
    errors = []
    
    # 1. House Number numeric check
    hno = str(record.get("HNO", "")).strip()
    if not hno:
        errors.append("House number (HNO) is required.")
    elif not hno.isdigit():
        digits = "".join(filter(str.isdigit, hno))
        if not digits:
            errors.append(f"Invalid house number '{hno}': must contain numeric digits.")

    # 2. Pre-Directional
    prd = record.get("PRD")
    if prd and prd.upper() not in VALID_DIRECTIONALS:
        errors.append(f"Invalid Pre-Directional '{prd}'. Must be one of {VALID_DIRECTIONALS}")

    # 3. Post-Directional
    pod = record.get("POD")
    if pod and pod.upper() not in VALID_DIRECTIONALS:
        errors.append(f"Invalid Post-Directional '{pod}'.")

    # 4. Street Name
    stn = record.get("STN")
    if not stn or len(stn.strip()) < 2:
        errors.append("Street Name (STN) must be at least 2 characters.")

    # 5. Postal Code
    postcode = str(record.get("PostCode", "")).strip()
    if postcode and (len(postcode) != 5 or not postcode.isdigit()):
        errors.append(f"Postal Code '{postcode}' must be a 5-digit number.")

    return len(errors) == 0, errors


def validate_road_parity(hno: int, side: str, parity_l: str, parity_r: str) -> bool:
    """
    Checks if house number parity matches the road segment side.
    side: 'L' or 'R'
    parity: 'O' (Odd), 'E' (Even), 'B' (Both), 'Z' (Zero/None)
    """
    expected = parity_l if side == "L" else parity_r
    if expected in ("B", "Z", None, ""):
        return True
    
    is_odd = (hno % 2 != 0)
    if is_odd and expected == "O":
        return True
    if not is_odd and expected == "E":
        return True
    return False


class TestNG911RemediationValidator(unittest.TestCase):

    def test_fix_token_calculation_base_snap(self):
        tokens, tier, reasons = calculate_fix_tokens(
            is_contained_now=True,
            was_contained_before=False,
            orig_offset=35.0,
            new_offset=28.0,
            is_unrouted_resolved=False,
            has_subaddress_added=False,
            has_ground_truth_corroborated=False
        )
        self.assertEqual(tokens, 10)
        self.assertEqual(tier, "COMMON")
        self.assertIn("Base Fix", reasons[0])

    def test_fix_token_calculation_unrouted_and_corroborated(self):
        tokens, tier, reasons = calculate_fix_tokens(
            is_contained_now=True,
            was_contained_before=False,
            orig_offset=250.0,
            new_offset=22.0,
            is_unrouted_resolved=True,
            has_subaddress_added=False,
            has_ground_truth_corroborated=True
        )
        self.assertEqual(tokens, 95)
        self.assertEqual(tier, "RARE")
        self.assertEqual(len(reasons), 4)

    def test_fix_token_calculation_epic_subaddress(self):
        tokens, tier, reasons = calculate_fix_tokens(
            is_contained_now=True,
            was_contained_before=True,
            orig_offset=15.0,
            new_offset=15.0,
            is_unrouted_resolved=False,
            has_subaddress_added=True,
            has_ground_truth_corroborated=False
        )
        self.assertEqual(tokens, 100)
        self.assertEqual(tier, "EPIC")

    def test_cldxf_schema_valid_record(self):
        valid_rec = {
            "HNO": "3715",
            "PRD": "N",
            "STN": "CORNELIA",
            "STS": "AVE",
            "PostCode": "93722"
        }
        is_valid, errors = validate_cldxf_schema(valid_rec)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_cldxf_schema_invalid_record(self):
        invalid_rec = {
            "HNO": "LOT 4A",
            "PRD": "NORTHWEST_WRONG",
            "STN": "",
            "PostCode": "9372"
        }
        is_valid, errors = validate_cldxf_schema(invalid_rec)
        self.assertFalse(is_valid)
        self.assertGreaterEqual(len(errors), 3)

    def test_road_parity_matching(self):
        self.assertTrue(validate_road_parity(3715, "L", "O", "E"))
        self.assertFalse(validate_road_parity(3715, "R", "O", "E"))
        self.assertTrue(validate_road_parity(3716, "R", "O", "E"))


if __name__ == "__main__":
    unittest.main()
