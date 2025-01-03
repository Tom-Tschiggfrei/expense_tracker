from dataclasses import dataclass
import re
from datetime import datetime, date, time
from transaction_types import TransactionTypes
from typing import Optional


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
    def from_account_statement(cls, account_statement: str, account_holder: str, year: str) -> "Transaction":

        input_lines = account_statement.splitlines()

        date = datetime.strptime(input_lines[0] + year, "%d.%m.%Y").date()
        try:
            transaction_type = TransactionTypes.get_match(" ".join(input_lines[1].split()[:-2]))
        except ValueError:
            # If the transaction type is not recognized, return None
            return None
        amount = float(input_lines[1].split()[-2].replace(".", "").replace(",", "."))
        if input_lines[1].split()[-1] == "S":
            amount = -amount
            is_charge = True
        elif input_lines[1].split()[-1] == "H":
            is_charge = False
        transaction_data = TRANSACTION_PROCESSOR[transaction_type](input_lines[2:], is_charge)

        for key in ["recipient", "orderer"]:
            if transaction_data[key] == "account_holder":
                transaction_data[key] = account_holder

        return cls(
            raw_string=account_statement,
            date=date,
            time=transaction_data["time"],
            amount=amount,
            orderer=transaction_data["orderer"],
            recipient=transaction_data["recipient"],
            transaction_type=transaction_type,
            transaction_purpose=(
                transaction_data["transaction_purpose"]
                if "transaction_purpose" in transaction_data.keys()
                else None
            ),
            transaction_fee=(
                transaction_data["transaction_fee"] if "transaction_fee" in transaction_data.keys() else None
            ),
            bank_location=(
                transaction_data["bank_location"] if "bank_location" in transaction_data.keys() else None
            ),
        )

    @classmethod
    def to_transaction_entry(self):
        pass


def process_card_payment(transaction_lines: list[str], is_charge: bool) -> str:
    assert is_charge  # Card payments are always charges
    orderer = "account_holder"
    recipient = transaction_lines[1]
    try:
        time_ = time.fromisoformat(re.search(r"\b\d{2}:\d{2}:\d{2}\b", "".join(transaction_lines)).group(0))
    except AttributeError:
        time_ = None
    result_dict = {
        "time": time_,
        "orderer": orderer,
        "recipient": recipient,
    }
    return result_dict


def process_cash_withdrawal(transaction_lines: list[str], is_charge: bool) -> str:
    assert is_charge  # Cash withdrawals are always charges
    orderer = "account_holder"
    recipient = "account_holder"
    try:
        time_ = time.fromisoformat(re.search(r"\b\d{2}:\d{2}:\d{2}\b", "".join(transaction_lines)).group(0))
    except AttributeError:
        time_ = None
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
    result_dict = {
        "time": time_,
        "orderer": orderer,
        "recipient": recipient,
        "transaction_fee": transaction_fee,
        "bank_location": bank_location,
    }
    return result_dict


def process_transfer(transaction_lines: list[str], is_charge: bool) -> str:
    if is_charge:
        orderer = "account_holder"
        recipient = transaction_lines[0]
    else:
        orderer = transaction_lines[0]
        recipient = "account_holder"
    if "PayPal" in "".join((orderer, recipient)):
        return process_paypal_transaction(transaction_lines, is_charge)
    transaction_purpose = "".join(transaction_lines[1:])
    for keyword in ["SecureGo", "TAN", "IBAN", "EREF", "REF"]:
        if keyword in transaction_purpose:
            transaction_purpose = transaction_purpose.partition(keyword)[0]
            break
    try:
        time_ = time.fromisoformat(re.search(r"\b\d{2}:\d{2}:\d{2}\b", "".join(transaction_lines)).group(0))
    except AttributeError:
        time_ = None
    result_dict = {
        "time": time_,
        "orderer": orderer,
        "recipient": recipient,
        "transaction_purpose": transaction_purpose,
    }
    return result_dict


def process_paypal_transaction(transaction_lines: list[str], is_charge: bool) -> str:
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
    try:
        time_ = time.fromisoformat(re.search(r"\b\d{2}:\d{2}:\d{2}\b", "".join(transaction_lines)).group(0))
    except AttributeError:
        time_ = None
    return {
        "time": time_,
        "orderer": orderer,
        "recipient": recipient,
        "transaction_purpose": transaction_purpose,
    }


TRANSACTION_PROCESSOR = {
    TransactionTypes.SALARY_PAYOUT: process_transfer,
    TransactionTypes.CARD_PAYMENT: process_card_payment,
    TransactionTypes.CASH_WITHDRAWAL: process_cash_withdrawal,
    TransactionTypes.REALTIME_TRANSFER: process_transfer,
    TransactionTypes.STANDING_TRANSFER: process_transfer,
    TransactionTypes.COMPENSATION: process_transfer,
    TransactionTypes.DIRECT_DEBIT: process_transfer,
}
