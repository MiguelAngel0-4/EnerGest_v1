"""
Excepciones de la capa de acceso a datos.

Ruta: src/infrastructure/database/exceptions.py

Traducen los errores técnicos de sqlite3 a errores con significado,
para que las capas superiores no dependan de detalles de SQLite.
"""


class DatabaseError(Exception):
    """Error base de la capa de datos. Todas las demás heredan de esta."""


class DatabaseLockedError(DatabaseError):
    """La base de datos siguió bloqueada tras agotar el tiempo de espera."""


class DatabaseIntegrityError(DatabaseError):
    """Se violó una restricción: UNIQUE, FOREIGN KEY, CHECK o NOT NULL."""


class SchemaInitializationError(DatabaseError):
    """No se pudo crear o verificar el esquema de la base de datos."""
