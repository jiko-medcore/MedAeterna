import pytest

from uuid import UUID
from app.core.fhir.datatypes.codeable_concept import FHIRCodeableConcept
from app.core.fhir.mappings.base import FHIRMapper
from app.core.fhir.mappings.exceptions import (
    FHIRMappingInputError,
)
from app.core.fhir.mappings.healthcare_service import (
    HealthcareServiceMapper,
)
from app.core.fhir.resources.healthcare_service import (
    FHIRHealthcareService,
)
from app.core.fhir.datatypes.contact_point import FHIRContactPoint


# =========================================================================
#  MAPPER CONTRACT TESTS
# =========================================================================
def test_healthcare_service_mapper_implements_fhir_mapper_contract():
    mapper: FHIRMapper[
        dict,
        FHIRHealthcareService,
    ] = HealthcareServiceMapper()

    assert isinstance(mapper, HealthcareServiceMapper)


def test_healthcare_service_mapper_rejects_non_dict_input():
    mapper = HealthcareServiceMapper()

    with pytest.raises(FHIRMappingInputError):
        mapper.to_fhir("not a healthcare service")


def test_healthcare_service_mapper_rejects_none_input():
    mapper = HealthcareServiceMapper()

    with pytest.raises(FHIRMappingInputError):
        mapper.to_fhir(None)


def test_healthcare_service_mapper_rejects_list_input():
    mapper = HealthcareServiceMapper()

    with pytest.raises(FHIRMappingInputError):
        mapper.to_fhir([])


# =========================================================================
#  MAPPER SERVICE ID AND NAME TESTS
# =========================================================================
def test_healthcare_service_mapper_returns_fhir_healthcare_service():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert isinstance(result, FHIRHealthcareService)


def test_healthcare_service_mapper_maps_id_and_name():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.id == "service-123"
    assert result.name == "Outpatient Services"


def test_healthcare_service_mapper_maps_active_true():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.active is True


def test_healthcare_service_mapper_preserves_active_false():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
            "active": False,
        }
    )

    assert result.active is False
    assert result.to_dict()["active"] is False


def test_healthcare_service_mapper_converts_uuid_id_to_string():
    mapper = HealthcareServiceMapper()

    service_id = UUID("12345678-1234-5678-1234-567812345678")

    result = mapper.to_fhir(
        {
            "id": service_id,
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.id == str(service_id)


def test_healthcare_service_mapper_serializes_id_name_and_active():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.to_dict() == {
        "resourceType": "HealthcareService",
        "id": "service-123",
        "active": True,
        "name": "Outpatient Services",
    }


# =========================================================================
#  MAPPER ORGANIZATION REFERENCE TESTS
# =========================================================================
def test_healthcare_service_mapper_maps_organization_reference():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "organization_id": "org-456",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.provided_by is not None
    assert result.provided_by.reference == "Organization/org-456"


def test_healthcare_service_mapper_serializes_provided_by():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "organization_id": "org-456",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.to_dict()["providedBy"] == {
        "reference": "Organization/org-456",
    }


def test_healthcare_service_mapper_converts_organization_uuid_to_reference():
    mapper = HealthcareServiceMapper()

    organization_id = UUID(
        "12345678-1234-5678-1234-567812345678"
    )

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "organization_id": organization_id,
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.provided_by is not None
    assert result.provided_by.reference == (
        f"Organization/{organization_id}"
    )


def test_healthcare_service_mapper_omits_missing_organization_reference():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
            "active": True,
        }
    )

    assert result.provided_by is None
    assert "providedBy" not in result.to_dict()


# =========================================================================
#  MAPPER ORGANIZATION CLASSIFICAION TESTS
# =========================================================================
def test_healthcare_service_mapper_maps_category():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "category": "Outpatient",
        }
    )

    assert result.category == (
        FHIRCodeableConcept(text="Outpatient"),
    )
    

def test_healthcare_service_mapper_maps_type():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "type": "Consultation",
        }
    )

    assert result.service_type == (
        FHIRCodeableConcept(text="Consultation"),
    )
    

def test_healthcare_service_mapper_maps_specialty():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "specialty": "Cardiology",
        }
    )

    assert result.specialty == (
        FHIRCodeableConcept(text="Cardiology"),
    )


def test_healthcare_service_mapper_maps_all_classification_fields():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "category": "Outpatient",
            "type": "Consultation",
            "specialty": "Cardiology",
        }
    )

    assert result.to_dict()["category"] == [
        {"text": "Outpatient"},
    ]
    assert result.to_dict()["type"] == [
        {"text": "Consultation"},
    ]
    assert result.to_dict()["specialty"] == [
        {"text": "Cardiology"},
    ]
    

def test_healthcare_service_mapper_omits_missing_classification_fields():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
        }
    )

    resource = result.to_dict()

    assert result.category == ()
    assert result.service_type == ()
    assert result.specialty == ()

    assert "category" not in resource
    assert "type" not in resource
    assert "specialty" not in resource
    

def test_healthcare_service_mapper_omits_empty_classification_strings():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "category": "",
            "type": "",
            "specialty": "",
        }
    )

    resource = result.to_dict()

    assert result.category == ()
    assert result.service_type == ()
    assert result.specialty == ()

    assert "category" not in resource
    assert "type" not in resource
    assert "specialty" not in resource


# =========================================================================
#  MAPPER TELECOM TESTS
# =========================================================================
def test_healthcare_service_mapper_maps_phone():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "phone": "+2348012345678",
        }
    )

    assert result.telecom == (
        FHIRContactPoint(
            system="phone",
            value="+2348012345678",
        ),
    )


def test_healthcare_service_mapper_maps_email():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "email": "clinic@example.com",
        }
    )

    assert result.telecom == (
        FHIRContactPoint(
            system="email",
            value="clinic@example.com",
        ),
    )



def test_healthcare_service_mapper_maps_phone_and_email():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "phone": "+2348012345678",
            "email": "clinic@example.com",
        }
    )

    assert result.telecom == (
        FHIRContactPoint(
            system="phone",
            value="+2348012345678",
        ),
        FHIRContactPoint(
            system="email",
            value="clinic@example.com",
        ),
    )



def test_healthcare_service_mapper_omits_missing_contacts():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "Outpatient Services",
        }
    )

    assert result.telecom == ()
    assert "telecom" not in result.to_dict()


def test_healthcare_service_mapper_omits_empty_contacts():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "phone": "",
            "email": "",
        }
    )

    assert result.telecom == ()
    assert "telecom" not in result.to_dict()



def test_healthcare_service_mapper_serializes_telecom():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "phone": "+2348012345678",
            "email": "clinic@example.com",
        }
    )

    assert result.to_dict()["telecom"] == [
        {
            "system": "phone",
            "value": "+2348012345678",
        },
        {
            "system": "email",
            "value": "clinic@example.com",
        },
    ]



# =========================================================================
#  MAPPER DESCRIPTION TESTS
# =========================================================================
def test_maps_description_to_comment():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "description": "Consultation and general medical assessment.",
        }
    )

    assert result.comment == "Consultation and general medical assessment."


def test_serializes_description_under_fhir_comment_key():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "description": "Consultation and general medical assessment.",
        }
    )

    assert result.to_dict()["comment"] == (
        "Consultation and general medical assessment."
    )


def test_omits_comment_when_description_is_missing():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
        }
    )

    assert result.comment is None
    assert "comment" not in result.to_dict()


def test_omits_comment_when_description_is_empty():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "description": "",
        }
    )

    assert result.comment is None
    assert "comment" not in result.to_dict()



# =========================================================================
#  MAPPER APPOINTMENT REQUIRED TESTS
# =========================================================================
def test_healthcare_service_mapper_maps_appointment_required_true():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "appointment_required": True,
        }
    )

    assert result.appointment_required is True


def test_healthcare_service_mapper_preserves_appointment_required_false():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "appointment_required": False,
        }
    )

    assert result.appointment_required is False


def test_healthcare_service_mapper_serializes_appointment_required():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "appointment_required": True,
        }
    )

    assert result.to_dict()["appointmentRequired"] is True


def test_healthcare_service_mapper_omits_missing_appointment_required():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
        }
    )

    assert result.appointment_required is None
    assert "appointmentRequired" not in result.to_dict()


# =========================================================================
#  MAPPER WEBSITE TO TELECOM TESTS
# =========================================================================
def test_healthcare_service_mapper_maps_website_to_telecom():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "website": "https://clinic.example.com",
        }
    )

    assert len(result.telecom) == 1
    assert result.telecom[0].system == "url"
    assert result.telecom[0].value == "https://clinic.example.com"


def test_healthcare_service_mapper_omits_missing_website():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
        }
    )

    assert result.telecom == ()


def test_healthcare_service_mapper_omits_blank_website():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "website": "   ",
        }
    )

    assert result.telecom == ()


def test_healthcare_service_mapper_maps_phone_email_and_website():
    mapper = HealthcareServiceMapper()

    result = mapper.to_fhir(
        {
            "id": "service-123",
            "name": "General Consultation",
            "phone": "+2348012345678",
            "email": "clinic@example.com",
            "website": "https://clinic.example.com",
        }
    )

    assert len(result.telecom) == 3

    telecom_by_system = {
        contact.system: contact.value
        for contact in result.telecom
    }

    assert telecom_by_system == {
        "phone": "+2348012345678",
        "email": "clinic@example.com",
        "url": "https://clinic.example.com",
    }