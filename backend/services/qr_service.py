"""
Swiss QR code generation service.
Extracted from server.py during Phase 3 modularization.
"""
import tempfile
import base64
import logging

from qrbill import QRBill

logger = logging.getLogger("evohome.qr")

DEFAULT_IBAN = "CH9300762011623852957"
DEFAULT_COMPANY_NAME = "Evohome SA"
DEFAULT_COMPANY_ADDRESS = "Rue du Rhone 1"
DEFAULT_COMPANY_PCODE = "1204"
DEFAULT_COMPANY_CITY = "Geneve"
DEFAULT_COMPANY_COUNTRY = "CH"


def generate_swiss_qr_code(
    amount: float,
    reference: str,
    buyer_name: str = None,
    iban: str = None,
    creditor_name: str = None,
    creditor_address: str = None,
    creditor_pcode: str = None,
    creditor_city: str = None
) -> bytes:
    """Generate Swiss QR bill code as SVG bytes"""
    try:
        account_iban = iban or DEFAULT_IBAN
        creditor = {
            'name': creditor_name or DEFAULT_COMPANY_NAME,
            'street': creditor_address or DEFAULT_COMPANY_ADDRESS,
            'pcode': creditor_pcode or DEFAULT_COMPANY_PCODE,
            'city': creditor_city or DEFAULT_COMPANY_CITY,
            'country': DEFAULT_COMPANY_COUNTRY,
        }

        bill = QRBill(
            account=account_iban,
            creditor=creditor,
            amount=str(round(amount, 2)),
            currency='CHF',
            additional_information=f"Invoice {reference}" if reference else None
        )

        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as tmp:
            bill.as_svg(tmp.name)
            with open(tmp.name, 'rb') as f:
                return f.read()
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return None


def generate_swiss_qr_code_base64(
    amount: float,
    reference: str,
    buyer_name: str = None,
    iban: str = None,
    creditor_name: str = None,
    creditor_address: str = None,
    creditor_pcode: str = None,
    creditor_city: str = None
) -> str:
    """Generate Swiss QR bill code as base64 SVG string for frontend display"""
    svg_bytes = generate_swiss_qr_code(
        amount, reference, buyer_name,
        iban, creditor_name, creditor_address, creditor_pcode, creditor_city
    )
    if svg_bytes:
        return base64.b64encode(svg_bytes).decode('utf-8')
    return None
