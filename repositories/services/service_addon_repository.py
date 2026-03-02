"""
Repository dla operacji na powiązaniach usług dodatkowych (service_addons)
"""
from typing import Any, List, Optional
from datetime import datetime
from repositories.db_utils import parse_dt
from config.database import get_db_connection
from database.models import ServiceAddon


class ServiceAddonRepository:
    """Repository do zarządzania kompatybilnością mikrousług z usługami głównymi"""

    def row_to_service_addon(self, row: Any) -> Optional[ServiceAddon]:
        """Konwertuj Row na obiekt ServiceAddon"""
        if not row:
            return None

        return ServiceAddon(
            id=row['id'],
            addon_service_id=row['addon_service_id'],
            main_service_id=row['main_service_id'],
            created_at=parse_dt(row['created_at'])
        )

    def create(self, addon: ServiceAddon) -> int:
        """Utwórz powiązanie mikrousługi z usługą główną"""
        query = """
            INSERT INTO service_addons (addon_service_id, main_service_id)
            VALUES (%s, %s)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (addon.addon_service_id, addon.main_service_id))
            result_id = cursor.fetchone()["id"]
            conn.commit()
            return result_id

    def delete(self, addon_id: int) -> bool:
        """Usuń powiązanie"""
        query = "DELETE FROM service_addons WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (addon_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_explicitly_linked_addons(self, main_service_id: int) -> List[Any]:
        """Pobierz TYLKO mikrousługi z jawnym wpisem w service_addons dla tej usługi głównej.

        Używane w widoku konfiguracji — nie zwraca addons 'universal' (bez reguł).
        """
        query = """
            SELECT s.* FROM services s
            JOIN service_addons sa ON sa.addon_service_id = s.id
            WHERE s.service_type = 'addon' AND s.is_active = TRUE
              AND sa.main_service_id = %s
            ORDER BY s.category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (main_service_id,))
            return cursor.fetchall()

    def get_compatible_addons(self, main_service_id: int) -> List[Any]:
        """Pobierz mikrousługi kompatybilne z daną usługą główną.

        Zwraca usługi dodatkowe, które:
        - mają wpis w service_addons dla tej usługi głównej, LUB
        - nie mają żadnych wpisów (= kompatybilne ze wszystkimi)
        """
        query = """
            SELECT s.* FROM services s
            WHERE s.service_type = 'addon' AND s.is_active = TRUE
            AND (
                s.id IN (
                    SELECT sa.addon_service_id FROM service_addons sa
                    WHERE sa.main_service_id = %s
                )
                OR s.id NOT IN (
                    SELECT DISTINCT sa2.addon_service_id FROM service_addons sa2
                )
            )
            ORDER BY s.category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (main_service_id,))
            return cursor.fetchall()

    def get_compatible_addons_for_services(self, main_service_ids: List[int]) -> List[Any]:
        """Pobierz UNION mikrousług kompatybilnych z listą usług głównych.

        Reguła UNION: mikrousługa jest dostępna, jeśli jest kompatybilna
        z PRZYNAJMNIEJ JEDNĄ z podanych usług głównych.
        """
        if not main_service_ids:
            return []

        placeholders = ','.join('%s' * len(main_service_ids))
        query = f"""
            SELECT DISTINCT s.* FROM services s
            WHERE s.service_type = 'addon' AND s.is_active = TRUE
            AND (
                s.id IN (
                    SELECT sa.addon_service_id FROM service_addons sa
                    WHERE sa.main_service_id IN ({placeholders})
                )
                OR s.id NOT IN (
                    SELECT DISTINCT sa2.addon_service_id FROM service_addons sa2
                )
            )
            ORDER BY s.category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(main_service_ids))
            return cursor.fetchall()

    def get_compatible_mains(self, addon_service_id: int) -> List[Any]:
        """Pobierz usługi główne kompatybilne z daną mikrousługą"""
        query = """
            SELECT s.* FROM services s
            JOIN service_addons sa ON sa.main_service_id = s.id
            WHERE sa.addon_service_id = %s AND s.is_active = TRUE
            ORDER BY s.category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (addon_service_id,))
            return cursor.fetchall()

    def has_compatibility_rules(self, addon_service_id: int) -> bool:
        """Sprawdź czy mikrousługa ma zdefiniowane reguły kompatybilności"""
        query = "SELECT COUNT(*) as cnt FROM service_addons WHERE addon_service_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (addon_service_id,))
            return cursor.fetchone()['cnt'] > 0

    def bulk_set_compatibility(self, addon_service_id: int, main_service_ids: List[int]) -> None:
        """Ustaw reguły kompatybilności (zastępuje istniejące).

        Pusta lista main_service_ids = mikrousługa kompatybilna ze wszystkimi.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Usuń istniejące reguły
            cursor.execute(
                "DELETE FROM service_addons WHERE addon_service_id = %s",
                (addon_service_id,)
            )
            # Dodaj nowe
            for main_id in main_service_ids:
                cursor.execute(
                    "INSERT INTO service_addons (addon_service_id, main_service_id) VALUES (%s, %s)",
                    (addon_service_id, main_id)
                )
            conn.commit()

    def get_all_for_addon(self, addon_service_id: int) -> List[Any]:
        """Pobierz wszystkie reguły kompatybilności dla mikrousługi"""
        query = """
            SELECT sa.*, s.name as main_service_name
            FROM service_addons sa
            JOIN services s ON s.id = sa.main_service_id
            WHERE sa.addon_service_id = %s
            ORDER BY s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (addon_service_id,))
            return cursor.fetchall()
