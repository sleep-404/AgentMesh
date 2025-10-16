"""
Setup demo data for testing the governance flow.

This script populates the PostgreSQL KB with sample customer data.
"""

import asyncio

from adapters.knowledge_base.postgres.adapter import PostgresAdapter


async def main():
    print("Setting up demo data...")

    # Connect to PostgreSQL
    adapter = PostgresAdapter("adapters/knowledge_base/postgres/config.yaml")
    await adapter.connect()

    # Check if customers table exists, create if not
    try:
        await adapter.execute_query(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                customer_email VARCHAR(255),
                customer_phone VARCHAR(20),
                ssn VARCHAR(20),
                credit_card VARCHAR(20),
                status VARCHAR(50)
            )
            """
        )
        print("✓ Customers table ready")

        # Insert sample data
        await adapter.execute_query(
            """
            INSERT INTO customers (name, customer_email, customer_phone, ssn, credit_card, status)
            VALUES
                ('John Doe', 'john.doe@example.com', '555-1234', '123-45-6789', '4111-1111-1111-1111', 'active'),
                ('Jane Smith', 'jane.smith@example.com', '555-5678', '987-65-4321', '5500-0000-0000-0004', 'active'),
                ('Bob Johnson', 'bob.j@example.com', '555-9012', '456-78-9012', '3400-0000-0000-009', 'inactive')
            ON CONFLICT DO NOTHING
            """
        )
        print("✓ Sample data inserted")

    except Exception as e:
        print(f"Error: {e}")

    await adapter.disconnect()
    print("Demo data setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
