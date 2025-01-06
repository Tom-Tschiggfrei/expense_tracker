from dataclasses import dataclass
import re
from datetime import datetime, date, time
from transaction_types import TransactionTypes
from typing import Optional, Union, get_type_hints


@dataclass
class Transaction:
    raw_string: str
    date: date
    time: Optional[time]
    amount: float
    orderer: str
    recipient: str
    transaction_type: TransactionTypes
    transaction_purpose: Optional[str]
    transaction_fee: Optional[str]
    bank_location: Optional[str]

    @classmethod
    def from_transaction_dict(cls, transaction_data: dict) -> "Transaction":
        type_hints = get_type_hints(cls)
        required_fields = {
            field
            for field, hint in type_hints.items()
            if not (getattr(hint, "__origin__", None) is Optional or str(hint).startswith("typing.Optional"))
        }
        if missing := required_fields - transaction_data.keys():
            raise ValueError(f"Missing required fields: {missing}")

    @classmethod
    def to_transaction_entry(self):
        pass


def process_bank_statement(account_statement: str, acc_holder: str, year: str) -> Union[tuple[dict], None]:

    input_lines = account_statement.splitlines()

    date = datetime.strptime(input_lines[0] + year, "%d.%m.%Y").date()
    try:
        transaction_time = time.fromisoformat(re.search(r"\b\d{2}:\d{2}:\d{2}\b", account_statement).group(0))
    except AttributeError:
        transaction_time = None
    try:
        transaction_type = TransactionTypes.get_match(" ".join(input_lines[1].split()[:-2]))
    except ValueError:
        # If the transaction type is not recognized, return None
        return None
    # handle all card payments that can simultaneously also include cash withdrawals at shops or gas stations
    if transaction_type == TransactionTypes.CARD_PAYMENT:
        transaction_data = {
            "orderer": "account_holder",
            "date": date,
            "time": transaction_time,
            "raw_string": account_statement,
        }
        pattern = r"(Zahlung|Buchung\s*(\d+,\d{2}))\s*(Auszahlung\s*(\d+,\d{2}))"
        if re.search(pattern, "".join(input_lines)) is not None:
            card_payment_amount, withdrawal_amount = re.search(pattern, "".join(input_lines)).group(2, 4)
            card_payment_amount = float(card_payment_amount.replace(".", "").replace(",", "."))
            withdrawal_amount = float(withdrawal_amount.replace(".", "").replace(",", "."))
            card_payment_data = {
                **transaction_data,
                "recipient": input_lines[3],
                "amount": card_payment_amount,
                "transaction_type": transaction_type,
            }
            withdrawal_data = {
                **transaction_data,
                "recipient": "account_holder",
                "amount": withdrawal_amount,
                "transaction_type": TransactionTypes.CASH_WITHDRAWAL,
            }
            return (card_payment_data, withdrawal_data)
        else:
            return (
                {
                    **transaction_data,
                    "recipient": input_lines[3],
                    "amount": float(input_lines[1].split()[-2].replace(".", "").replace(",", ".")),
                    "transaction_type": transaction_type,
                },
            )
    # handle all other types of transactions
    else:
        amount = float(input_lines[1].split()[-2].replace(".", "").replace(",", "."))
    if input_lines[1].split()[-1] == "S":
        amount = -amount
        is_charge = True
    else:
        is_charge = False
    transaction_data = TRANSACTION_PROCESSOR[transaction_type](input_lines[2:], is_charge)
    transaction_data["date"] = date
    transaction_data["time"] = transaction_time
    transaction_data["amount"] = amount
    transaction_data["transaction_type"] = transaction_type
    transaction_data["raw_string"] = account_statement

    for key in ["recipient", "orderer"]:
        if transaction_data[key] == "account_holder":
            transaction_data[key] = acc_holder

    return (transaction_data,)


def handle_cash_withdrawal(transaction_lines: list[str], is_charge: bool) -> str:
    assert is_charge  # Cash withdrawals are always charges
    orderer = "account_holder"
    recipient = "account_holder"
    try:
        transaction_fee = re.search(
            r"(Gebühr|Gebühren|Gebührenübernahme|Entgelt)\s*(\d+,\d{2})",
            " ".join(transaction_lines),
            re.IGNORECASE,
        ).group(2)
        transaction_fee = float(transaction_fee.replace(".", "").replace(",", "."))
    except AttributeError:
        transaction_fee = 0.0
    bank_location_0 = transaction_lines[0]
    bank_location_1 = transaction_lines[1]
    if bank_location_0 in bank_location_1:
        bank_location = bank_location_1
    else:
        bank_location = bank_location_0 + ", " + bank_location_1
    return {
        "orderer": orderer,
        "recipient": recipient,
        "transaction_fee": transaction_fee,
        "bank_location": bank_location,
    }


def handle_bank_transfer(transaction_lines: list[str], is_charge: bool) -> str:
    if is_charge:
        orderer = "account_holder"
        recipient = transaction_lines[0]
    else:
        orderer = transaction_lines[0]
        recipient = "account_holder"
    if "PayPal" in "".join((orderer, recipient)):
        return handle_paypal_transaction(transaction_lines, is_charge)
    transaction_purpose = "".join(transaction_lines[1:])
    for keyword in ["SecureGo", "TAN", "IBAN", "EREF", "REF"]:
        if keyword in transaction_purpose:
            transaction_purpose = transaction_purpose.partition(keyword)[0]
            break
    return {
        "orderer": orderer,
        "recipient": recipient,
        "transaction_purpose": transaction_purpose,
    }


def handle_paypal_transaction(transaction_lines: list[str], is_charge: bool) -> str:
    if is_charge:
        recipient = re.search(
            r"(?<=/\.\s)(.*?)(?=(,\s*Ihr Einkauf bei|EREF))",
            "".join(transaction_lines[1:]),
            re.IGNORECASE,
        ).group(1)
        recipient = "Unbekannt" if recipient == "" else recipient
        orderer = "account_holder"
        transaction_purpose = "PayPal Abbuchung von " + recipient
    else:
        try:
            orderer = re.search(
                r"(.*?)(?=, Ihr Einkauf bei)",
                "".join(transaction_lines[1:]),
                re.IGNORECASE,
            ).group(0)
        except AttributeError:
            orderer = (
                "account_holder"  # If no information about orderer given, it is a withdrawal from PayPal
            )
        recipient = "account_holder"
        transaction_purpose = (
            "PayPal Gutschrift/Überweisung von " + orderer
            if orderer != recipient
            else "Abbuchung vom eigenen PayPal Konto"
        )
    return {
        "orderer": orderer,
        "recipient": recipient,
        "transaction_purpose": transaction_purpose,
    }


TRANSACTION_PROCESSOR = {
    TransactionTypes.SALARY_PAYOUT: handle_bank_transfer,
    TransactionTypes.CASH_WITHDRAWAL: handle_cash_withdrawal,
    TransactionTypes.REALTIME_TRANSFER: handle_bank_transfer,
    TransactionTypes.STANDING_TRANSFER: handle_bank_transfer,
    TransactionTypes.COMPENSATION: handle_bank_transfer,
    TransactionTypes.DIRECT_DEBIT: handle_bank_transfer,
}
