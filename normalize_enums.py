import asyncio
import logging
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Таблицы и колонки, которые содержат Enums
TABLES_TO_NORMALIZE = {
    "users": ["role"],
    "stores": ["store_type"],
    "orders": ["status"],
    "invite_codes": ["role"],
    "financial_transactions": ["type"],
    "stock_movements": ["movement_type"],
    "debt_ledgers": ["reason"]
}

async def normalize():
    logger.info("🚀 Starting database enum normalization...")
    
    async with async_session_factory() as session:
        try:
            for table, columns in TABLES_TO_NORMALIZE.items():
                for column in columns:
                    logger.info(f"Normalizing {table}.{column}...")
                    
                    # Переводим в нижний регистр все значения в колонке
                    query = text(f"UPDATE {table} SET {column} = LOWER({column})")
                    result = await session.execute(query)
                    
                    logger.info(f"✅ {table}.{column}: {result.rowcount} rows updated.")
            
            await session.commit()
            logger.info("✨ All data normalized successfully!")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Error during normalization: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(normalize())
