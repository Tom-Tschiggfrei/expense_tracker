from transaction import Transaction, process_bank_statement
from datetime import datetime
from pypdf import PdfReader
import yaml
import re
from pathlib import Path
import logging

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def process_monthly_transaction_pdf(pdf_pages):
    # Regex pattern to match transactions with their date and details
    pattern = r"(\d{2}\.\d{2}\.\s+\d{2}\.\d{2}\.)\s+((?!Abschluss|neuer Kontostand).+?)(?=\n\d{2}\.\d{2}\.|Übertrag|$)"
    monthly_transactions = []
    for page in pdf_pages:
        transactions = re.findall(pattern, page.extract_text(), re.DOTALL)
        for transaction_date, transaction_details in transactions:
            # Clean up the details: remove excessive indentation
            formatted_details = (
                transaction_date[:6].strip()
                + "\n"
                + "\n".join(line.strip() for line in transaction_details.splitlines())
            )
            monthly_transactions.append(formatted_details)
    return monthly_transactions


def get_month_year_from_pdf(pdf_pages):
    date_pattern = r"neuer\s+Kontostand\s+vom\s+(\d{2}\.\d{2}\.\d{4})"
    date_str = re.findall(date_pattern, pdf_pages[-1].extract_text())[0]
    date_object = datetime.strptime(date_str, "%d.%m.%Y").date()
    return date_object


def extract_transactions(config: dict, account_holder: str) -> list[Transaction]:

    transactions_folder = Path(config["transactions_folder"])
    account_holder = config["account_holder"]

    monthly_pdfs = [p for p in transactions_folder.iterdir() if p.suffix == ".pdf"]

    monthly_transactions = {}

    for pdf in monthly_pdfs:
        reader = PdfReader(transactions_folder / pdf)
        monthly_pages = [reader.pages[i] for i in range(reader.get_num_pages() - 1)]
        month_year = get_month_year_from_pdf(monthly_pages).strftime("%m.%Y")
        year = month_year[3:]
        monthly_transactions[month_year] = process_monthly_transaction_pdf(monthly_pages)

    monthly_transactions = dict(
        sorted(monthly_transactions.items(), key=lambda x: datetime.strptime(x[0], "%m.%Y"))
    )

    transactions = []
    for month_year, transaction_statements in monthly_transactions.items():
        for transaction_statement in transaction_statements:
            logger.info(f"Processing transaction:\n\n{transaction_statement}\n")
            transaction_data = process_bank_statement(transaction_statement, account_holder, year)
            for data in transaction_data:
                if data is not None:
                    transaction = Transaction.from_transaction_dict(data)
            transactions.append(transaction)

    return transactions


transactions = extract_transactions(config, "Tom T.")
print(transactions)

# TODO: Storno und bezahlung verrechnen
