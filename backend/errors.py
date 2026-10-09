"""Safe validation messages and diagnostics without exception payloads."""
import logging
import uuid

class ValidationError(ValueError):
    """A deliberately authored message safe for display to a user."""

def report_error(operation,exc):
    reference=uuid.uuid4().hex[:10].upper()
    # Database exceptions may contain SQL, hostnames, credentials or certificates.
    # Record only the operation, exception class and correlation reference.
    logging.error('VBAS event=%s operation=%s type=%s',reference,operation,type(exc).__name__)
    return f'We could not complete this request. Please try again. If it continues, contact your administrator with reference {reference}.'
