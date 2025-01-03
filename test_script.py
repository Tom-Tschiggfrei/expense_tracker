from database_class import TransactionEntry, get_engine, create_tables, get_session
from transaction import Transaction


engine = get_engine()
create_tables(engine)
session = get_session(engine)

# Example of adding a new entry
new_entry = TransactionEntry(
    day_date="2023-10-01", payment_sum=100.50, payment_type="Credit", payment_receiver="John Doe"
)
session.add(new_entry)
session.commit()
