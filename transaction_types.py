from enum import Enum


class TransactionTypes(Enum):
    SALARY_PAYOUT = ("GEHALT/LOHN/RENTE",)
    CARD_PAYMENT = ("Kartenzahlung",)
    CASH_WITHDRAWAL = ("Auszahlung girocard",)
    REALTIME_TRANSFER = ("Überweisung", "ECHTZEIT ÜBERWEISUNG", "Echtzeitüberweisung", "EURO-ÜBERWEISUNG")
    STANDING_TRANSFER = ("Dauerauftrag",)
    COMPENSATION = ("Gutschrift", "VERGÜTUNG", "EURO-GUTSCHRIFT")
    DIRECT_DEBIT = ("Basislastschrift",)

    @classmethod
    def get_match(cls, str_input: str):
        for member in cls:
            if any(transaction_name.lower() in str_input.lower() for transaction_name in member.value):
                return member
        raise ValueError(f"Could not find a known Transaction type for: {str_input}")
