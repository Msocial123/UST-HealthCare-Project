"""Patient domain values: administrative sex codes and medical record number generation."""

import secrets
from enum import StrEnum

# Crockford base32 (no I, L, O, U) keeps MRNs unambiguous when read aloud or typed.
MRN_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MRN_PREFIX = "MRN-"
MRN_RANDOM_LENGTH = 10
MRN_LENGTH = len(MRN_PREFIX) + MRN_RANDOM_LENGTH


class Sex(StrEnum):
    """Administrative sex/gender (aligned with HL7 FHIR AdministrativeGender)."""

    FEMALE = "FEMALE"
    MALE = "MALE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


def generate_mrn() -> str:
    return MRN_PREFIX + "".join(secrets.choice(MRN_ALPHABET) for _ in range(MRN_RANDOM_LENGTH))
