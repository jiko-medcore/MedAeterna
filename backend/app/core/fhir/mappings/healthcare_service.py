from typing import Any

from app.core.fhir.mappings.base import FHIRMapper
from app.core.fhir.mappings.exceptions import FHIRMappingInputError
from app.core.fhir.datatypes.reference import FHIRReference
from app.core.fhir.resources.healthcare_service import (
    FHIRHealthcareService,
)
from app.core.fhir.datatypes.codeable_concept import (
    FHIRCodeableConcept,
)
from app.core.fhir.datatypes.contact_point import FHIRContactPoint



class HealthcareServiceMapper(
    FHIRMapper[dict[str, Any], FHIRHealthcareService]
):
    """
    Maps the MedCore HealthcareService representation
    to a FHIR R4 HealthcareService resource.
    """

    # Hwlper function to avoid repeating convertion
    @staticmethod
    def _to_codeable_concept(
        value: Any,
    ) -> tuple[FHIRCodeableConcept, ...]:
        if not isinstance(value, str) or not value.strip():
            return ()

        return (
            FHIRCodeableConcept(text=value),
        )
    

    def to_fhir(
        self,
        value: dict[str, Any],
    ) -> FHIRHealthcareService:
        if not isinstance(value, dict):
            raise FHIRMappingInputError(
                "HealthcareServiceMapper requires a "
                "healthcare service dictionary."
            )

        return FHIRHealthcareService(
            id=(
                str(value["id"])
                if value.get("id") is not None
                else None
            ),
            name=value.get("name"),
            active=value.get("active"),
            provided_by=(
                FHIRReference(
                    reference=f"Organization/{value['organization_id']}",
                )
                if value.get("organization_id") is not None
                else None
            ),
            category=self._to_codeable_concept(
                value.get("category"),
            ),
            service_type=self._to_codeable_concept(
                value.get("type"),
            ),
            specialty=self._to_codeable_concept(
                value.get("specialty"),
            ),
            telecom=self._to_telecom(
                phone=value.get("phone"),
                email=value.get("email"),
                website=value.get("website"),
            ),
            comment=(
                value.get("description")
                if isinstance(value.get("description"), str)
                and value.get("description").strip()
                else None
            ),
            appointment_required=value.get("appointment_required"),
        )

    @staticmethod
    def _to_telecom(
        phone: Any,
        email: Any,
    ) -> tuple[FHIRContactPoint, ...]:
        telecom = []

        if isinstance(phone, str) and phone.strip():
            telecom.append(
                FHIRContactPoint(
                    system="phone",
                    value=phone,
                )
            )

        if isinstance(email, str) and email.strip():
            telecom.append(
                FHIRContactPoint(
                    system="email",
                    value=email,
                )
            )

        return tuple(telecom)