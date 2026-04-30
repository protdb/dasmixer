"""Project database schema migrations."""

import logging
from dasmixer.versions import PROJECT_VERSION, MIN_SUPPORTED_PROJECT_VERSION

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Ошибка при применении миграций проекта."""
    pass


def _version_lt(a: str, b: str) -> bool:
    """Возвращает True если версия a строго меньше b."""
    return tuple(int(x) for x in a.split('.')) < tuple(int(x) for x in b.split('.'))


def _version_gt(a: str, b: str) -> bool:
    """Возвращает True если версия a строго больше b."""
    return tuple(int(x) for x in a.split('.')) > tuple(int(x) for x in b.split('.'))


MIGRATIONS: list[dict] = [
    {
        "version": "0.2.0",
        "sql": """
            ALTER TABLE protein ADD COLUMN taxon_id INTEGER;
            ALTER TABLE protein ADD COLUMN organism_name TEXT;
        """,
    },
]


class MigrationMixin:
    """
    Mixin для системы миграций схемы проекта.
    Подмешивается в Project между ProjectLifecycle и остальными миксинами.
    """

    async def get_project_version(self) -> str:
        """Возвращает строку версии из project_metadata."""
        row = await self._fetchone(
            "SELECT value FROM project_metadata WHERE key = 'version'"
        )
        return row['value'] if row else "0.1.0"

    async def needs_migration(self) -> bool:
        """True, если версия проекта ниже PROJECT_VERSION."""
        project_version = await self.get_project_version()
        return _version_lt(project_version, PROJECT_VERSION)

    async def is_version_too_new(self) -> bool:
        """True, если версия проекта выше PROJECT_VERSION."""
        project_version = await self.get_project_version()
        return _version_gt(project_version, PROJECT_VERSION)

    async def apply_migrations(self) -> None:
        """
        Проверяет версию открытого проекта и применяет необходимые миграции.

        Алгоритм:
        1. Читает project_metadata.version
        2. Если version == PROJECT_VERSION — ничего не делает
        3. Если version < MIN_SUPPORTED_PROJECT_VERSION — поднимает MigrationError
        4. Итерирует MIGRATIONS, пропуская версии <= текущей версии проекта
        5. Применяет подходящие миграции через executescript внутри транзакции
        6. При ошибке — rollback, логирует logger.exception, поднимает MigrationError
        7. При успехе — обновляет project_metadata.version = PROJECT_VERSION и сохраняет

        Raises:
            MigrationError: при неподдерживаемой версии или ошибке выполнения SQL
        """
        project_version = await self.get_project_version()

        if project_version == PROJECT_VERSION:
            return  # уже актуальная версия

        if _version_lt(project_version, MIN_SUPPORTED_PROJECT_VERSION):
            raise MigrationError(
                f"Project version {project_version} is below minimum supported "
                f"{MIN_SUPPORTED_PROJECT_VERSION}. Migration is not possible."
            )

        # Фильтруем: берём только миграции, чья версия > project_version
        pending = [m for m in MIGRATIONS if _version_gt(m['version'], project_version)]

        if not pending:
            # Нечего применять, но версии не совпадают — обновляем метадату
            await self._execute(
                "INSERT OR REPLACE INTO project_metadata (key, value) VALUES ('version', ?)",
                (PROJECT_VERSION,)
            )
            await self._db.commit()
            return

        # Применяем последовательно, каждую в своей транзакции
        for migration in pending:
            try:
                await self._db.executescript(migration['sql'])
                await self._db.commit()
            except Exception as e:
                await self._db.rollback()
                logger.exception("Migration to %s failed: %s", migration['version'], e)
                raise MigrationError(
                    f"Migration to version {migration['version']} failed: {e}"
                ) from e

        # Все миграции применены — обновляем версию
        await self._execute(
            "INSERT OR REPLACE INTO project_metadata (key, value) VALUES ('version', ?)",
            (PROJECT_VERSION,)
        )
        await self._db.commit()
