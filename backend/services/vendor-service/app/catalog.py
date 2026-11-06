"""Fixed lists the API accepts. Changing a list needs a code change on purpose: Phase 6 matches RFQs to vendors by category."""

CATEGORIES: dict[str, str] = {
    "it_hardware": "IT hardware",
    "software": "Software and licences",
    "office_supplies": "Office supplies",
    "furniture": "Furniture",
    "facilities": "Facilities and maintenance",
    "logistics": "Logistics and freight",
    "professional_services": "Professional services",
    "marketing": "Marketing and print",
    "manufacturing": "Raw materials and manufacturing",
    "other": "Other",
}
MAX_CATEGORIES = 10
MAX_CONTACTS = 10
CURRENCIES = ("INR", "USD", "EUR", "GBP")
